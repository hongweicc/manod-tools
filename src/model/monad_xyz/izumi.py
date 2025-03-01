from web3 import AsyncWeb3
from eth_account import Account
import asyncio
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
import random
from loguru import logger
from src.utils.constants import RPC_URL, EXPLORER_URL, ERC20_ABI
from src.model.monad_xyz.constants import IZUMI_ABI, IZUMI_TOKENS, IZUMI_CONTRACT
import time
from src.utils.config import Config


class IzumiDex:
    def __init__(self, private_key: str, proxy: Optional[str] = None, config: Optional[Config] = None):
        """
        初始化 Izumi DEX 客户端。

        Args:
            private_key: 以太坊账户私钥。
            proxy: 可选的代理字符串。
            config: 配置对象。
        """
        # 使用代理配置 RPC（如果需要）
        provider = AsyncWeb3.AsyncHTTPProvider(RPC_URL, request_kwargs={"proxy": proxy} if proxy else {})
        self.web3 = AsyncWeb3(provider)
        self.account = Account.from_key(private_key)
        self.proxy = proxy
        self.router_contract = self.web3.eth.contract(address=self.web3.to_checksum_address(IZUMI_CONTRACT), abi=IZUMI_ABI)
        self.FEE_TIER = 10000  # 1% 手续费
        self.config = config or Config.load()

    async def get_gas_params(self) -> Dict[str, int]:
        """获取当前网络的 gas 参数。"""
        latest_block = await self.web3.eth.get_block('latest')
        base_fee = latest_block['baseFeePerGas']
        max_priority_fee = await self.web3.eth.max_priority_fee
        return {
            "maxFeePerGas": base_fee + max_priority_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

    def convert_to_wei(self, amount: float, token: str) -> int:
        """将金额转换为 wei 单位。"""
        decimals = 18 if token == "native" else IZUMI_TOKENS[token.lower()]["decimals"]
        return int(Decimal(str(amount)) * Decimal(10 ** decimals))

    def convert_from_wei(self, amount: int, token: str) -> float:
        """将 wei 金额转换回代币单位。"""
        decimals = 18 if token == "native" else IZUMI_TOKENS[token.lower()]["decimals"]
        return float(Decimal(str(amount)) / Decimal(10 ** decimals))

    async def get_tokens_with_balance(self) -> List[Tuple[str, float]]:
        """获取账户中余额非零的代币列表。"""
        tokens_with_balance = []
        try:
            native_balance = await self.web3.eth.get_balance(self.account.address)
            if native_balance > 10**14:
                tokens_with_balance.append(("native", self.convert_from_wei(native_balance, "native")))

            for token in IZUMI_TOKENS:
                if token == "wmon":
                    continue
                token_contract = self.web3.eth.contract(address=self.web3.to_checksum_address(IZUMI_TOKENS[token]["address"]), abi=ERC20_ABI)
                balance = await token_contract.functions.balanceOf(self.account.address).call()
                min_amount = 10 ** (IZUMI_TOKENS[token]["decimals"] - 4)
                if balance >= min_amount:
                    tokens_with_balance.append((token, self.convert_from_wei(balance, token)))
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to fetch balances: {e}")
        return tokens_with_balance

    async def approve_token(self, token: str, amount: int) -> Optional[str]:
        """批准 Izumi 路由器花费代币。"""
        if token == "native":
            return None
        token_contract = self.web3.eth.contract(address=self.web3.to_checksum_address(IZUMI_TOKENS[token]["address"]), abi=ERC20_ABI)
        try:
            allowance = await token_contract.functions.allowance(self.account.address, IZUMI_CONTRACT).call()
            if allowance >= amount:
                logger.info(f"[{self.account.address}] Allowance sufficient for {token}")
                return None
            nonce = await self.web3.eth.get_transaction_count(self.account.address)
            gas_params = await self.get_gas_params()
            approve_tx = await token_contract.functions.approve(IZUMI_CONTRACT, amount).build_transaction({
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

    async def execute_transaction(self, transaction: Dict) -> str:
        """执行交易并等待确认。"""
        signed_txn = self.web3.eth.account.sign_transaction(transaction, self.account.key)
        tx_hash = await self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
        logger.info(f"[{self.account.address}] Transaction sent: {EXPLORER_URL}{tx_hash.hex()}")
        receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=2)
        if receipt['status'] == 1:
            logger.success(f"[{self.account.address}] Transaction confirmed: {EXPLORER_URL}{tx_hash.hex()}")
            return tx_hash.hex()
        raise Exception(f"[{self.account.address}] Transaction failed: {EXPLORER_URL}{tx_hash.hex()}")

    async def swap(self, percentage_to_swap: float, type: str = "swap") -> Optional[str]:
        """在 Izumi DEX 上执行代币交换。"""
        try:
            tokens_with_balance = await self.get_tokens_with_balance()
            if not tokens_with_balance:
                logger.info(f"[{self.account.address}] No tokens with sufficient balance")
                return None

            if type == "collect":
                tokens_to_swap = [(t, b) for t, b in tokens_with_balance if t != "native"]
                if not tokens_to_swap:
                    logger.info(f"[{self.account.address}] No tokens to collect")
                    return None
                for token_in, _ in tokens_to_swap:
                    token_contract = self.web3.eth.contract(address=self.web3.to_checksum_address(IZUMI_TOKENS[token_in]["address"]), abi=ERC20_ABI)
                    amount_wei = await token_contract.functions.balanceOf(self.account.address).call()
                    await self.approve_token(token_in, amount_wei)
                    await asyncio.sleep(random.randint(*self.config.SETTINGS.PAUSE_BETWEEN_SWAPS))
                    logger.info(f"[{self.account.address}] Collecting {self.convert_from_wei(amount_wei, token_in)} {token_in} to native")
                    tx_data = await self.generate_swap_data(token_in, "native", amount_wei)
                    await self.execute_transaction(tx_data)
                return "Collection complete"

            token_in, balance = random.choice(tokens_with_balance)
            token_out = random.choice([t for t in IZUMI_TOKENS.keys() if t != "wmon"]) if token_in == "native" else "native"
            amount_wei = int(await self.web3.eth.get_balance(self.account.address) * percentage_to_swap / 100) if token_in == "native" else await self.web3.eth.contract(address=self.web3.to_checksum_address(IZUMI_TOKENS[token_in]["address"]), abi=ERC20_ABI).functions.balanceOf(self.account.address).call()
            if token_in != "native":
                await self.approve_token(token_in, amount_wei)
                await asyncio.sleep(random.randint(*self.config.SETTINGS.PAUSE_BETWEEN_SWAPS))

            logger.info(f"[{self.account.address}] Swapping {self.convert_from_wei(amount_wei, token_in)} {token_in} to {token_out}")
            tx_data = await self.generate_swap_data(token_in, token_out, amount_wei)
            return await self.execute_transaction(tx_data)
        except Exception as e:
            logger.error(f"[{self.account.address}] Swap failed: {e}")
            raise

    async def estimate_gas(self, tx_params: Dict) -> int:
        """估算交易 gas 并添加安全裕度。"""
        try:
            estimated_gas = await self.web3.eth.estimate_gas({k: v for k, v in tx_params.items() if k != 'gas'})
            return int(estimated_gas * 1.2)
        except Exception:
            logger.warning(f"[{self.account.address}] Gas estimation failed, using default")
            return 200_000

    async def generate_swap_data(self, token_in: str, token_out: str, amount_in: int) -> Dict:
        """生成交换交易数据。"""
        token_in_address = IZUMI_TOKENS["wmon"]["address"] if token_in == "native" else IZUMI_TOKENS[token_in]["address"]
        token_out_address = IZUMI_TOKENS["wmon"]["address"] if token_out == "native" else IZUMI_TOKENS[token_out]["address"]
        path = bytes.fromhex(self.web3.to_checksum_address(token_in_address)[2:] + format(self.FEE_TIER, '06x') + self.web3.to_checksum_address(token_out_address)[2:])
        deadline = int(time.time() + 3600 * 6)
        min_acquired = 0
        recipient = IZUMI_CONTRACT if token_out == "native" else self.account.address

        swap_data = self.router_contract.encode_abi("swapAmount", [(path, recipient, amount_in, min_acquired, deadline)])
        multicall_array = [swap_data]
        if token_out == "native":
            multicall_array.append(self.router_contract.encode_abi("unwrapWETH9", [min_acquired, self.account.address]))
        multicall_array.append(self.router_contract.encode_abi("refundETH"))

        nonce = await self.web3.eth.get_transaction_count(self.account.address)
        gas_params = await self.get_gas_params()
        tx_data = {
            'from': self.account.address,
            'to': self.web3.to_checksum_address(IZUMI_CONTRACT),
            'value': amount_in if token_in == "native" else 0,
            'data': self.router_contract.encode_abi("multicall", [multicall_array]),
            'nonce': nonce,
            'chainId': 10143,
            **gas_params,
            'gas': await self.estimate_gas({
                'from': self.account.address,
                'to': IZUMI_CONTRACT,
                'value': amount_in if token_in == "native" else 0,
                'data': self.router_contract.encode_abi("multicall", [multicall_array]),
            }),
        }
        return tx_data

    def __del__(self):
        """清理敏感数据。"""
        self.account = None
        import gc
        gc.collect()