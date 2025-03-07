from web3 import AsyncWeb3
from eth_account import Account
import asyncio
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from loguru import logger
from src.utils.constants import RPC_URL, EXPLORER_URL, ERC20_ABI
from src.model.monad_xyz.constants import (
    AMBIENT_ABI, AMBIENT_TOKENS, AMBIENT_CONTRACT, ZERO_ADDRESS,
    POOL_IDX, RESERVE_FLAGS, TIP, MAX_SQRT_PRICE, MIN_SQRT_PRICE
)
from eth_abi import abi
from src.utils.config import Config
import random


class AmbientDex:
    def __init__(self, private_key: str, proxy: Optional[str] = None, config: Optional[Config] = None):
        """
        初始化 Ambient DEX 客户端。

        Args:
            private_key: 以太坊账户私钥。
            proxy: 可选的代理 URL（如 "http://127.0.0.1:7890"）。
            config: 配置对象，默认为 None 时加载默认配置。
        """
        self.private_key = private_key
        self.proxy = f"http://{proxy}" if proxy and not proxy.startswith(("http://", "https://")) else proxy
        self.config = config or Config.load()
        self._w3: Optional[AsyncWeb3] = None
        self.account: Optional[Account] = None
        self.router_contract = None

    async def __aenter__(self):
        """异步初始化 Web3 客户端和账户。"""
        provider_kwargs = {"proxy": self.proxy} if self.proxy else {}
        self.provider = AsyncWeb3.AsyncHTTPProvider(RPC_URL, request_kwargs=provider_kwargs)
        self._w3 = AsyncWeb3(self.provider)
        self.account = Account.from_key(self.private_key)
        self.router_contract = self._w3.eth.contract(address=self._w3.to_checksum_address(AMBIENT_CONTRACT), abi=AMBIENT_ABI)
        try:
            chain_id = await self._w3.eth.chain_id
            logger.debug(f"[{self.account.address}] Connected to chain ID: {chain_id} via proxy: {self.proxy or 'None'}")
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to connect to RPC: {e}")
            raise
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """关闭 Web3 客户端会话。"""
        if hasattr(self.provider, 'session') and self.provider.session is not None:
            await self.provider.session.close()
            logger.debug(f"[{self.account.address}] Closed AmbientDex session")
        self._w3 = None
        self.account = None
        self.private_key = None  # 清理私钥

    async def get_gas_params(self) -> Dict[str, int]:
        """获取当前网络的 gas 参数。"""
        try:
            latest_block = await self._w3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            max_priority_fee = await self._w3.eth.max_priority_fee
            return {
                "maxFeePerGas": base_fee + max_priority_fee,
                "maxPriorityFeePerGas": max_priority_fee,
            }
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to fetch gas params: {e}")
            raise

    def convert_to_wei(self, amount: float, token: str) -> int:
        """将金额转换为 wei 单位。"""
        decimals = 18 if token == "native" else AMBIENT_TOKENS[token.lower()]["decimals"]
        return int(Decimal(str(amount)) * Decimal(10 ** decimals))

    def convert_from_wei(self, amount: int, token: str) -> float:
        """将 wei 金额转换回代币单位。"""
        decimals = 18 if token == "native" else AMBIENT_TOKENS[token.lower()]["decimals"]
        return float(Decimal(str(amount)) / Decimal(10 ** decimals))

    async def get_tokens_with_balance(self) -> List[Tuple[str, float]]:
        """获取账户中余额非零的代币列表。"""
        tokens_with_balance = []
        try:
            native_balance = await self._w3.eth.get_balance(self.account.address)
            if native_balance > 10**14:  # 超过 0.0001 MON
                tokens_with_balance.append(("native", self.convert_from_wei(native_balance, "native")))

            for token in AMBIENT_TOKENS:
                token_contract = self._w3.eth.contract(address=self._w3.to_checksum_address(AMBIENT_TOKENS[token]["address"]), abi=ERC20_ABI)
                balance = await token_contract.functions.balanceOf(self.account.address).call()
                if balance > 0:
                    amount = self.convert_from_wei(balance, token)
                    if token.lower() in ["seth", "weth"] and amount < 0.001:
                        continue
                    tokens_with_balance.append((token, amount))
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to fetch token balances: {e}")
        return tokens_with_balance

    async def approve_token(self, token: str, amount: int) -> Optional[str]:
        """批准 Ambient DEX 花费代币。"""
        if token == "native":
            return None
        token_contract = self._w3.eth.contract(address=self._w3.to_checksum_address(AMBIENT_TOKENS[token]["address"]), abi=ERC20_ABI)
        try:
            allowance = await token_contract.functions.allowance(self.account.address, AMBIENT_CONTRACT).call()
            if allowance >= amount:
                logger.info(f"[{self.account.address}] Allowance sufficient for {token}: {self.convert_from_wei(allowance, token)}")
                return None
            nonce = await self._w3.eth.get_transaction_count(self.account.address)
            gas_params = await self.get_gas_params()
            approve_tx = await token_contract.functions.approve(AMBIENT_CONTRACT, amount).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'type': 2,
                'chainId': 10143,
                **gas_params,
            })
            return await self.execute_transaction(approve_tx)
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to approve {token}: {e}")
            raise

    async def generate_swap_data(self, token_in: str, token_out: str, amount_in_wei: int) -> Dict:
        """生成 Ambient DEX 交换交易数据。"""
        try:
            is_native = token_in == "native"
            token_address = (
                AMBIENT_TOKENS[token_out.lower()]["address"] if is_native
                else AMBIENT_TOKENS[token_in.lower()]["address"]
            )
            encode_data = abi.encode(
                ['address', 'address', 'uint16', 'bool', 'bool', 'uint256', 'uint8', 'uint256', 'uint256', 'uint8'],
                [ZERO_ADDRESS, self._w3.to_checksum_address(token_address), POOL_IDX, is_native, is_native, amount_in_wei,
                 TIP, MAX_SQRT_PRICE if is_native else MIN_SQRT_PRICE, 0, RESERVE_FLAGS]
            )
            function_selector = self._w3.keccak(text="userCmd(uint16,bytes)")[:4]
            cmd_params = abi.encode(['uint16', 'bytes'], [1, encode_data])
            tx_data = function_selector.hex() + cmd_params.hex()

            gas_estimate = await self._w3.eth.estimate_gas({
                'to': AMBIENT_CONTRACT, 'from': self.account.address, 'data': '0x' + tx_data,
                'value': amount_in_wei if is_native else 0
            })
            return {
                "to": AMBIENT_CONTRACT,
                "data": '0x' + tx_data,
                "value": amount_in_wei if is_native else 0,
                "gas": int(gas_estimate * 1.1)
            }
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to generate swap data: {e}")
            raise

    async def execute_transaction(self, tx_data: Dict) -> str:
        """执行交易并等待确认。"""
        try:
            nonce = await self._w3.eth.get_transaction_count(self.account.address)
            gas_params = await self.get_gas_params()
            transaction = {
                "from": self.account.address,
                "nonce": nonce,
                "type": 2,
                "chainId": 10143,
                **tx_data,
                **gas_params,
            }
            signed_txn = self._w3.eth.account.sign_transaction(transaction, self.account.key)
            tx_hash = await self._w3.eth.send_raw_transaction(signed_txn.raw_transaction)
            logger.info(f"[{self.account.address}] Transaction sent: {EXPLORER_URL}{tx_hash.hex()}")
            receipt = await self._w3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=2)
            if receipt['status'] == 1:
                logger.success(f"[{self.account.address}] Transaction confirmed: {EXPLORER_URL}{tx_hash.hex()}")
                return tx_hash.hex()
            raise ValueError(f"Transaction failed: {EXPLORER_URL}{tx_hash.hex()}")
        except Exception as e:
            logger.error(f"[{self.account.address}] Transaction execution failed: {e}")
            raise

    async def swap(self, percentage_to_swap: float, type: str = "swap", token_out: Optional[str] = None) -> Optional[str]:
        """
        在 Ambient DEX 上执行代币交换。

        Args:
            percentage_to_swap: 交换的余额百分比（0-100）。
            type: 操作类型（"swap" 或 "collect"）。
            token_out: 可选的目标代币符号。

        Returns:
            Optional[str]: 交易哈希或 "Collection complete"，失败时返回 None。
        """
        async with self:
            try:
                tokens_with_balance = await self.get_tokens_with_balance()
                if not tokens_with_balance:
                    logger.info(f"[{self.account.address}] No tokens with sufficient balance")
                    return None

                if type == "collect":
                    tokens_to_swap = [(t, b) for t, b in tokens_with_balance if t != "native"]
                    if not tokens_to_swap:
                        logger.info(f"[{self.account.address}] No tokens to collect to native")
                        return None

                    for token_in, balance in tokens_to_swap:
                        amount_wei = self.convert_to_wei(
                            balance if token_in.lower() != "seth" else max(0, balance - random.uniform(0.00001, 0.0001)),
                            token_in
                        )
                        await self.approve_token(token_in, amount_wei)
                        pause = random.randint(self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0], self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1])
                        logger.info(f"[{self.account.address}] Approved {token_in} for {self.convert_from_wei(amount_wei, token_in)}. Sleeping {pause}s")
                        await asyncio.sleep(pause)
                        tx_data = await self.generate_swap_data(token_in, "native", amount_wei)
                        await self.execute_transaction(tx_data)
                        if token_in != tokens_to_swap[-1][0]:
                            await asyncio.sleep(random.randint(5, 10))
                    logger.success(f"[{self.account.address}] Collection complete")
                    return "Collection complete"

                token_in, balance = random.choice(tokens_with_balance)
                token_out = token_out or random.choice([t for t in list(AMBIENT_TOKENS.keys()) + ["native"] if t != token_in])
                amount_wei = (
                    int(self.convert_to_wei(balance, token_in) * Decimal(percentage_to_swap) / Decimal(100))
                    if token_in == "native" else
                    self.convert_to_wei(max(0, balance - (random.uniform(0.00001, 0.0001) if token_in.lower() == "seth" else 0)), token_in)
                )
                if token_in != "native":
                    await self.approve_token(token_in, amount_wei)
                    await asyncio.sleep(random.randint(5, 10))

                logger.info(f"[{self.account.address}] Swapping {self.convert_from_wei(amount_wei, token_in)} {token_in} to {token_out}")
                tx_data = await self.generate_swap_data(token_in, token_out, amount_wei)
                return await self.execute_transaction(tx_data)

            except ValueError as ve:
                logger.error(f"[{self.account.address}] Swap failed due to invalid input: {ve}")
                return None
            except Exception as e:
                logger.error(f"[{self.account.address}] Swap failed: {e}")
                raise