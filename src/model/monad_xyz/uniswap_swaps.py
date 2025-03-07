from web3 import AsyncWeb3
from eth_account import Account
import json
import asyncio
from typing import Dict, Optional, List, Tuple
from decimal import Decimal
from loguru import logger
from src.utils.constants import TOKENS, ERC20_ABI, RPC_URL, EXPLORER_URL
from src.utils.client import create_client
from src.utils.config import get_config
import random


config = get_config()


class MonadSwap:
    """Class to handle swaps on Monad network"""

    def __init__(self, private_key: str, proxy: Optional[str] = None):
        """
        Initialize MonadSwap instance.
        
        Args:
            private_key: Private key for the wallet
            proxy: Optional proxy URL for API requests
        """
        self.web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))
        self.account = Account.from_key(private_key)
        self.proxy = proxy

    async def get_gas_params(self) -> Dict[str, int]:
        """Get current gas parameters from the network."""
        try:
            latest_block = await self.web3.eth.get_block('latest')
            base_fee = latest_block['baseFeePerGas']
            max_priority_fee = await self.web3.eth.max_priority_fee
            return {
                "maxFeePerGas": base_fee + max_priority_fee,
                "maxPriorityFeePerGas": max_priority_fee,
            }
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to fetch gas params: {e}")
            raise

    async def get_token_balance_ether(self, token: str) -> Decimal:
        """Get balance of specified token."""
        max_retries = 10  # Fixed number of retries

        for attempt in range(max_retries):
            try:
                if token == "native":
                    balance_wei = await self.web3.eth.get_balance(self.account.address)
                    return Decimal(self.web3.from_wei(balance_wei, 'ether'))
                else:
                    contract_address = self.web3.to_checksum_address(TOKENS[token])
                    contract = self.web3.eth.contract(address=contract_address, abi=ERC20_ABI)
                    balance_wei = await contract.functions.balanceOf(self.account.address).call()
                    balance_ether = Decimal(self.web3.from_wei(balance_wei, 'ether'))
                    logger.info(f"[{self.account.address}] Balance: {balance_ether:.4f} {token}")
                    return balance_ether
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"[{self.account.address}] Error getting balance after {max_retries} attempts: {str(e)}")
                    return Decimal(0)
                await asyncio.sleep(1)  # Fixed 1 second pause between retries

        return Decimal(0)

    async def get_tokens_with_balance(self) -> List[Tuple[str, Decimal]]:
        """Get list of tokens with non-zero balances."""
        tokens_with_balance = []
        try:
            for token in TOKENS:
                if token == "native":
                    continue
                balance = await self.get_token_balance_ether(token)
                if balance > 0:
                    tokens_with_balance.append((token, balance))
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to fetch token balances: {e}")
        return tokens_with_balance

    async def calculate_amount(self, percentage_to_swap: float, token_out: str) -> float:
        """Calculate the actual amount to swap based on balance if using percentages."""
        if not 0 < percentage_to_swap <= 100:
            raise ValueError("Percentage must be between 0 and 100")
        percentage = Decimal(percentage_to_swap) / Decimal(100)

        balance_token = "native" if token_out != "native" else token_out
        balance_ether = await self.get_token_balance_ether(balance_token)
        balance_wei = self.web3.to_wei(balance_ether, 'ether')
        balance_wei_percentage = int(balance_wei * percentage)
        balance_ether_percentage = float(round(self.web3.from_wei(balance_wei_percentage, 'ether'), random.randint(2, 8)))

        logger.info(f"[{self.account.address}] Balance: {balance_ether} {balance_token}")
        logger.info(f"[{self.account.address}] Swapping {percentage_to_swap}% = {balance_ether_percentage} {balance_token}")
        return balance_ether_percentage

    async def _generate_url_percentage(self, percentage_to_swap: float, token_out: str) -> str:
        """Generate URL for swapping tokens with percentage."""
        amount_after_percentage = await self.calculate_amount(percentage_to_swap, token_out)
        return f'https://uniswap.api.dial.to/swap/confirm?chain=monad-testnet&inputCurrency={TOKENS["native"]}&outputCurrency={TOKENS[token_out]}&inputSymbol=MON&outputSymbol={token_out}&inputDecimals=18&outputDecimals=18&amount={amount_after_percentage}'

    async def _generate_url_amount(self, amount: float, token_in: str) -> str:
        """Generate URL for swapping tokens with fixed amount."""
        return f'https://uniswap.api.dial.to/swap/confirm?chain=monad-testnet&inputCurrency={TOKENS[token_in]}&outputCurrency={TOKENS["native"]}&inputSymbol={token_in}&outputSymbol=MON&inputDecimals=18&outputDecimals=18&amount={amount}'

    async def get_swap_quote(self, percentage_to_swap_or_amount: float, token_out: str, token_in: str = None) -> Dict:
        """Get a quote for swapping tokens."""
        max_retries = 5
        json_data = {'account': self.account.address, 'type': 'transaction'}
        client = await create_client(self.proxy)

        if token_out == "native":
            url = await self._generate_url_amount(percentage_to_swap_or_amount, token_in)
        else:
            url = await self._generate_url_percentage(percentage_to_swap_or_amount, token_out)

        async with client:
            for attempt in range(max_retries):
                try:
                    response = await client.post(url=url, json=json_data)
                    response_data = response.json()

                    if isinstance(response_data, dict) and 'error' in response_data:
                        error_msg = str(response_data.get('error', '')).lower()
                        if 'number greater than' in error_msg:
                            logger.warning(f"[{self.account.address}] Balance too small for swap, skipping: {response_data['error']}")
                            return None

                    if not response_data.get('transaction'):
                        raise ValueError(f"No transaction data in response: {response_data}")

                    tx_data = json.loads(response_data['transaction'])
                    return {
                        "to": self.web3.to_checksum_address(tx_data['to']),
                        "value": int(tx_data['value'], 16),
                        "data": tx_data['data'],
                        "gas": tx_data['gas'],
                    }
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise Exception(f"[{self.account.address}] Failed to get quote after {max_retries} attempts: {str(e)}")
                    logger.error(f"[{self.account.address}] Attempt {attempt + 1} failed: {str(e)}")
                    await asyncio.sleep(random.randint(
                        config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[0],
                        config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS[1]
                    ))

    async def generate_approve_transaction(self, token: str, amount: float, swap_tx_data: Dict) -> Dict:
        """Generate an approve transaction for the token."""
        try:
            token_address = self.web3.to_checksum_address(TOKENS[token])
            token_contract = self.web3.eth.contract(address=token_address, abi=ERC20_ABI)
            spender_address = self.web3.to_checksum_address(swap_tx_data['to'])
            amount_wei = self.web3.to_wei(amount, 'ether')

            function_signature = self.web3.keccak(text="approve(address,uint256)")[0:4]
            padded_address = spender_address[2:].zfill(64)
            padded_amount = hex(amount_wei)[2:].zfill(64)
            approve_data = function_signature.hex() + padded_address + padded_amount

            gas_estimate = await self.web3.eth.estimate_gas({
                'to': token_address,
                'from': self.account.address,
                'data': '0x' + approve_data,
                'value': 0
            })
            gas_limit = int(gas_estimate * 1.1)

            tx_data = {
                "to": token_address,
                "data": '0x' + approve_data,
                "value": 0,
                "gas": gas_limit
            }
            logger.info(f"[{self.account.address}] Generated approve transaction for {amount} {token} to spender {spender_address} (Gas: {gas_limit})")
            return tx_data
        except Exception as e:
            logger.error(f"[{self.account.address}] Failed to generate approve transaction: {str(e)}")
            raise

    async def execute_transaction(self, tx_data: Dict) -> str:
        """Execute transaction and wait for confirmation."""
        try:
            nonce = await self.web3.eth.get_transaction_count(self.account.address)
            gas_params = await self.get_gas_params()
            transaction = {
                "from": self.account.address,
                "nonce": nonce,
                "type": 2,
                "chainId": 10143,
                **tx_data,
                **gas_params,
            }
            signed_txn = self.web3.eth.account.sign_transaction(transaction, self.account.key)
            tx_hash = await self.web3.eth.send_raw_transaction(signed_txn.raw_transaction)
            logger.info(f"[{self.account.address}] Transaction sent: {EXPLORER_URL}{tx_hash.hex()}")
            receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash, poll_latency=2)
            if receipt['status'] == 1:
                logger.success(f"[{self.account.address}] Transaction confirmed: {EXPLORER_URL}{tx_hash.hex()}")
                return tx_hash.hex()
            raise ValueError(f"Transaction failed: {EXPLORER_URL}{tx_hash.hex()}")
        except Exception as e:
            logger.error(f"[{self.account.address}] Transaction execution failed: {e}")
            raise

    async def swap(self, percentage_to_swap: float, type: str = "swap", token_out: Optional[str] = None) -> Optional[str]:
        """
        在 MonadSwap（Uniswap）上执行代币交换。

        Args:
            percentage_to_swap: 交换的余额百分比（0-100）。
            type: 操作类型（"swap" 或 "collect"）。
            token_out: 可选的目标代币符号。

        Returns:
            Optional[str]: 交易哈希或 "Collection complete"，失败时返回 None。
        """
        try:
            tokens_with_balance = await self.get_tokens_with_balance()
            native_balance = await self.get_token_balance_ether("native")
            if native_balance > Decimal("0"):
                tokens_with_balance.append(("native", native_balance))
            if not tokens_with_balance:
                logger.info(f"[{self.account.address}] No tokens with sufficient balance")
                return None

            if type == "collect":
                tokens_to_swap = [(t, b) for t, b in tokens_with_balance if t != "native"]
                if not tokens_to_swap:
                    logger.info(f"[{self.account.address}] No tokens to collect to native")
                    return None

                for token_in, balance in tokens_to_swap:
                    swap_tx_data = await self.get_swap_quote(balance, "native", token_in=token_in)
                    if not swap_tx_data:
                        continue
                    approve_tx_data = await self.generate_approve_transaction(token_in, balance, swap_tx_data)
                    await self.execute_transaction(approve_tx_data)
                    pause = random.randint(config.SETTINGS.PAUSE_BETWEEN_SWAPS[0], config.SETTINGS.PAUSE_BETWEEN_SWAPS[1])
                    logger.info(f"[{self.account.address}] Approved {token_in} for {balance}. Sleeping {pause}s")
                    await asyncio.sleep(pause)
                    await self.execute_transaction(swap_tx_data)
                logger.success(f"[{self.account.address}] Collection complete")
                return "Collection complete"

            token_in, balance = random.choice(tokens_with_balance)
            token_out = token_out or random.choice([t for t in TOKENS.keys() if t != "native"])
            if token_out == "native":
                swap_tx_data = await self.get_swap_quote(balance, "native", token_in=token_in)
                if not swap_tx_data:
                    logger.warning(f"[{self.account.address}] Insufficient balance or quote failed for {token_in} to native")
                    return None
                if token_in != "native":
                    approve_tx_data = await self.generate_approve_transaction(token_in, balance, swap_tx_data)
                    await self.execute_transaction(approve_tx_data)
                    await asyncio.sleep(random.randint(config.SETTINGS.PAUSE_BETWEEN_SWAPS[0], config.SETTINGS.PAUSE_BETWEEN_SWAPS[1]))
            else:
                swap_tx_data = await self.get_swap_quote(percentage_to_swap, token_out)
                if not swap_tx_data:
                    logger.warning(f"[{self.account.address}] Insufficient balance or quote failed for native to {token_out}")
                    return None

            logger.info(f"[{self.account.address}] Swapping {balance if token_in != 'native' else self.web3.from_wei(swap_tx_data['value'], 'ether')} {token_in} to {token_out}")
            return await self.execute_transaction(swap_tx_data)

        except ValueError as ve:
            logger.error(f"[{self.account.address}] Swap failed due to invalid input: {ve}")
            return None
        except Exception as e:
            logger.error(f"[{self.account.address}] Swap failed: {e}")
            raise