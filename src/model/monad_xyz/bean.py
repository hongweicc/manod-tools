from web3 import AsyncWeb3
from eth_account import Account
import asyncio
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
from loguru import logger
from src.utils.constants import RPC_URL, EXPLORER_URL, ERC20_ABI
from src.model.monad_xyz.constants import BEAN_CONTRACT, BEAN_ABI, BEAN_TOKENS
from src.utils.config import Config
import random

class BeanDex:
    def __init__(self, private_key: str, proxy: Optional[str] = None, config: Optional[Config] = None):
        """
        初始化 Bean DEX 客户端。

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
        self.router_contract = self._w3.eth.contract(address=self._w3.to_checksum_address(BEAN_CONTRACT), abi=BEAN_ABI)
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
            logger.debug(f"[{self.account.address}] Closed BeanDex session")
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
        decimals = 18 if token == "native" else BEAN_TOKENS[token.lower()]["decimals"]
        return int(Decimal(str(amount)) * Decimal(10 ** decimals))

    def convert_from_wei(self, amount: int, token: str) -> float:
        """将 wei 金额转换回代币单位。"""
        decimals = 18 if token == "native" else BEAN_TOKENS[token.lower()]["decimals"]
        return float(Decimal(str(amount)) / Decimal(10 ** decimals))

    async def get_token_balance(self, token: str) -> float:
        """获取指定代币的余额。"""
        try:
            if token == "native":
                balance_wei = await self._w3.eth.get_balance(self.account.address)
                return self.convert_from_wei(balance_wei, "native")
            token_contract = self._w3.eth.contract(address=self._w3.to_checksum_address(BEAN_TOKENS[token]["address"]), abi=ERC20_ABI)
            balance = await token_contract.functions.balanceOf(self.account.address).call()
            return self.convert_from_wei(balance, token)
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to get {token} balance: {e}")
            return 0.0

    async def get_tokens_with_balance(self) -> List[Tuple[str, float]]:
        """获取账户中余额非零的代币列表。"""
        tokens_with_balance = []
        try:
            native_balance = await self._w3.eth.get_balance(self.account.address)
            if native_balance > 10**14:  # 超过 0.0001 MON
                tokens_with_balance.append(("native", self.convert_from_wei(native_balance, "native")))

            for token in BEAN_TOKENS:
                balance = await self.get_token_balance(token)
                if balance > 0:
                    tokens_with_balance.append((token, balance))
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to fetch token balances: {e}")
        return tokens_with_balance

    async def approve_token(self, token: str, amount: int) -> Optional[str]:
        """批准 Bean DEX 花费代币。"""
        if token == "native":
            return None
        token_contract = self._w3.eth.contract(address=self._w3.to_checksum_address(BEAN_TOKENS[token]["address"]), abi=ERC20_ABI)
        try:
            allowance = await token_contract.functions.allowance(self.account.address, BEAN_CONTRACT).call()
            if allowance >= amount:
                logger.info(f"[{self.account.address}] Allowance sufficient for {token}: {self.convert_from_wei(allowance, token)}")
                return None
            nonce = await self._w3.eth.get_transaction_count(self.account.address)
            gas_params = await self.get_gas_params()
            approve_tx = await token_contract.functions.approve(BEAN_CONTRACT, amount).build_transaction({
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
        try:
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

    async def generate_swap_data(self, token_in: str, token_out: str, amount_in: int, min_amount_out: int) -> Dict:
        """生成 Bean DEX 交换交易数据。"""
        try:
            deadline = int(time.time()) + 1800  # 30 分钟后
            logger.debug(f"[{self.account.address}] Swap deadline: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(deadline))}")
            path = (
                [BEAN_TOKENS["wmon"]["address"], BEAN_TOKENS[token_out]["address"]] if token_in == "native" else
                [BEAN_TOKENS[token_in]["address"], BEAN_TOKENS["wmon"]["address"]] if token_out == "native" else
                [BEAN_TOKENS[token_in]["address"], BEAN_TOKENS["wmon"]["address"], BEAN_TOKENS[token_out]["address"]]
            )
            method = (
                self.router_contract.functions.swapExactETHForTokens(min_amount_out, path, self.account.address, deadline)
                if token_in == "native" else
                self.router_contract.functions.swapExactTokensForETH(amount_in, min_amount_out, path, self.account.address, deadline)
                if token_out == "native" else
                self.router_contract.functions.swapExactTokensForTokens(amount_in, min_amount_out, path, self.account.address, deadline)
            )
            value = amount_in if token_in == "native" else 0
            gas_estimate = await method.estimate_gas({'from': self.account.address, 'value': value})
            return await method.build_transaction({
                'from': self.account.address,
                'value': value,
                'gas': int(gas_estimate * 1.1),
                'nonce': await self._w3.eth.get_transaction_count(self.account.address),
                **await self.get_gas_params(),
            })
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to generate swap data: {e}")
            raise

    async def swap(self, percentage_to_swap: float, type: str) -> Optional[str]:
        """
        在 Bean DEX 上执行代币交换。

        Args:
            percentage_to_swap: 交换的余额百分比（0-100）。
            type: 操作类型（"swap" 或 "collect"）。

        Returns:
            Optional[str]: 交易哈希或 "Collection complete"，失败时返回 None。
        """
        try:
            tokens_with_balance = await self.get_tokens_with_balance()
            if not tokens_with_balance:
                logger.info(f"[{self.account.address}] No tokens with sufficient balance")
                return None

            if type == "collect":
                tokens_to_swap = [(t, b) for t, b in tokens_with_balance if t not in ["native", "wmon", "bean"]]
                if not tokens_to_swap:
                    logger.info(f"[{self.account.address}] No tokens to collect to native")
                    return None

                logger.info(f"[{self.account.address}] Tokens to collect: {[t[0] for t in tokens_to_swap]}")
                for token_in, balance in tokens_to_swap:
                    amount_wei = self.convert_to_wei(balance, token_in)
                    await self.approve_token(token_in, amount_wei)
                    pause = random.randint(self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[0], self.config.SETTINGS.PAUSE_BETWEEN_SWAPS[1])
                    logger.info(f"[{self.account.address}] Approved {token_in} for {balance}. Sleeping {pause}s")
                    await asyncio.sleep(pause)
                    tx_data = await self.generate_swap_data(token_in, "native", amount_wei, 0)
                    await self.execute_transaction(tx_data)
                    if token_in != tokens_to_swap[-1][0]:
                        await asyncio.sleep(random.randint(5, 10))
                return "Collection complete"

            token_in, balance = random.choice(tokens_with_balance)
            available_out_tokens = ["native"] + [t for t in BEAN_TOKENS if t not in [token_in, "wmon"]] if token_in != "native" else [t for t in BEAN_TOKENS if t != "wmon"]
            token_out = random.choice(available_out_tokens)
            amount_wei = self.convert_to_wei(balance * (percentage_to_swap / 100), token_in)
            amount_token = self.convert_from_wei(amount_wei, token_in)
            if token_in != "native":
                await self.approve_token(token_in, amount_wei)
                await asyncio.sleep(random.randint(5, 10))

            logger.info(f"[{self.account.address}] Swapping {amount_token} {token_in} to {token_out}")
            tx_data = await self.generate_swap_data(token_in, token_out, amount_wei, 0)  # 可添加滑点计算
            return await self.execute_transaction(tx_data)

        except ValueError as ve:
            logger.error(f"[{self.account.address}] Swap failed due to invalid input: {ve}")
            return None
        except Exception as e:
            logger.error(f"[{self.account.address}] Swap failed: {e}")
            raise
