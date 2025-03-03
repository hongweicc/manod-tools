import asyncio
import random
from loguru import logger
from eth_account import Account
import primp
from typing import Optional

from src.model.monad_xyz.izumi import IzumiDex
from src.model.monad_xyz.uniswap_swaps import MonadSwap
from src.utils.config import Config


class MonadXYZ:
    def __init__(
            self,
            account_index: int,
            proxy: str,
            private_key: str,
            discord_token: Optional[str] = None,
            config: Config = None,
            session: Optional[primp.AsyncClient] = None,
    ):
        """
        初始化 MonadXYZ 类，用于 Monad 测试网操作。

        Args:
            account_index: 账户索引。
            proxy: 代理字符串。
            private_key: 账户私钥。
            discord_token: 可选的 Discord 令牌。
            config: 配置对象，默认为 None 时加载默认配置。
            session: HTTP 客户端会话。
        """
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.discord_token = discord_token
        self.config = config or Config.load()
        self.session = session
        self.wallet = Account.from_key(private_key)

    async def swaps(self, type: str) -> bool:
        """
        执行代币交换操作。

        Args:
            type: 交换类型 ("swaps", "ambient", "bean", "izumi", "collect_all_to_monad")。

        Returns:
            是否成功完成所有交换。
        """
        swap_handlers = {
            "swaps": self._uniswap_swaps,
            "ambient": self._ambient_swaps,
            "bean": self._bean_swaps,
            "izumi": self._izumi_swaps,
            "collect_all_to_monad": self._collect_all_to_monad,
        }

        handler = swap_handlers.get(type)
        if not handler:
            logger.error(f"[{self.account_index}] Unsupported swap type: {type}")
            return False

        try:
            return await handler()
        except Exception as e:
            logger.error(f"[{self.account_index}] Swaps failed for type {type}: {e}")
            return False

    async def _uniswap_swaps(self) -> bool:
        """处理 UniSwap 类型的交换。"""
        number_of_swaps = random.randint(*self.config.FLOW.NUMBER_OF_SWAPS)
        logger.info(f"[{self.account_index}] Will perform {number_of_swaps} UniSwap swaps")

        for swap_num in range(number_of_swaps):
            success = await self._retry_swap(
                MonadSwap(self.private_key, self.proxy),
                random.randint(*self.config.FLOW.PERCENT_OF_BALANCE_TO_SWAP),
                random.choice(["DAK", "YAKI", "CHOG"]),
                "Uniswap",
                swap_num + 1,
                number_of_swaps,
                )
            if not success:
                return False
        return True

    async def _ambient_swaps(self) -> bool:
        """处理 Ambient 类型的交换。"""
        number_of_swaps = random.randint(*self.config.FLOW.NUMBER_OF_SWAPS)
        logger.info(f"[{self.account_index}] Will perform {number_of_swaps} Ambient swaps")

        for swap_num in range(number_of_swaps):
            success = await self._retry_swap(
                AmbientDex(self.private_key, self.proxy, self.config),
                random.randint(*self.config.FLOW.PERCENT_OF_BALANCE_TO_SWAP),
                None,
                "Ambient",
                swap_num + 1,
                number_of_swaps,
                swap_type="swap",
                )
            if not success:
                return False
        return True

    async def _bean_swaps(self) -> bool:
        """处理 Bean 类型的交换。"""
        number_of_swaps = random.randint(*self.config.FLOW.NUMBER_OF_SWAPS)
        logger.info(f"[{self.account_index}] Will perform {number_of_swaps} Bean swaps")

        for swap_num in range(number_of_swaps):
            success = await self._retry_swap(
                BeanDex(self.private_key, self.proxy, self.config),
                random.randint(*self.config.FLOW.PERCENT_OF_BALANCE_TO_SWAP),
                None,
                "Bean",
                swap_num + 1,
                number_of_swaps,
                swap_type="swap",
                )
            if not success:
                return False
        return True

    async def _izumi_swaps(self) -> bool:
        """处理 Izumi 类型的交换。"""
        number_of_swaps = random.randint(*self.config.FLOW.NUMBER_OF_SWAPS)
        logger.info(f"[{self.account_index}] Will perform {number_of_swaps} Izumi swaps")

        for swap_num in range(number_of_swaps):
            success = await self._retry_swap(
                IzumiDex(self.private_key, self.proxy, self.config),
                random.randint(*self.config.FLOW.PERCENT_OF_BALANCE_TO_SWAP),
                None,  # token_out
                "Izumi",  # swap_type 用于日志
                swap_num + 1,
                number_of_swaps,
                swap_type_param="swap"  # 用于 swap 方法的 type 参数
            )
            if not success:
                return False
        return True

    async def _collect_all_to_monad(self) -> bool:
        """收集所有代币到 Monad 原生代币。"""
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                for swapper_cls, label, swap_type in [
                    (MonadSwap, "Uniswap", "swap"),
                    (AmbientDex, "Ambient", "collect"),
                    (BeanDex, "Bean", "collect"),
                    (IzumiDex, "Izumi", "collect"),
                ]:
                    swapper = swapper_cls(self.private_key, self.proxy, self.config)
                    await swapper.swap(percentage_to_swap=100, token_out="native" if swap_type == "swap" else None, type=swap_type)
                    pause = random.randint(*self.config.SETTINGS.PAUSE_BETWEEN_SWAPS)
                    logger.success(f"[{self.account_index}] Collected via {label}. Next in {pause}s")
                    await asyncio.sleep(pause)
                return True
            except Exception as e:
                pause = random.randint(*self.config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS)
                logger.error(f"[{self.account_index}] Collect failed ({retry + 1}/{self.config.SETTINGS.ATTEMPTS}): {e}. Retry in {pause}s")
                await asyncio.sleep(pause)
        return False

    async def _retry_swap(self, swapper, amount: int, token_out: Optional[str], swap_type: str, current: int, total: int, swap_type_param: str = "swap") -> bool:
        """重试机制执行单个交换。"""
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                kwargs = {"percentage_to_swap": amount, "type": swap_type_param}
                if token_out:
                    kwargs["token_out"] = token_out
                await swapper.swap(**kwargs)
                pause = random.randint(*self.config.SETTINGS.PAUSE_BETWEEN_SWAPS)
                logger.success(f"[{self.account_index}] {swap_type} swap {current}/{total} completed. Next in {pause}s")
                await asyncio.sleep(pause)
                return True
            except Exception as e:
                logger.error(f"[{self.account_index}] {swap_type} swap failed ({retry + 1}/{self.config.SETTINGS.ATTEMPTS}): {e}")
                if retry == self.config.SETTINGS.ATTEMPTS - 1:
                    return False
        return False

    async def faucet(self) -> bool:
        """从水龙头领取代币。"""
        try:
            result = await faucet(self.session, self.account_index, self.config, self.wallet, self.proxy)
            if result:
                logger.success(f"[{self.account_index}] Faucet claimed successfully.")
            return result
        except Exception as e:
            logger.error(f"[{self.account_index}] Faucet claim failed: {e}")
            return False

    async def connect_discord(self) -> bool:
        """连接 Discord 账户到 Monad 测试网。"""
        for retry in range(self.config.SETTINGS.ATTEMPTS):
            try:
                csrf_headers = {
                    "accept": "*/*",
                    "content-type": "application/json",
                    "sec-fetch-dest": "empty",
                    "sec-fetch-mode": "cors",
                    "sec-fetch-site": "same-origin",
                    "referer": "https://testnet.monad.xyz/",
                }
                csrf_response = await self.session.get("https://testnet.monad.xyz/api/auth/csrf", headers=csrf_headers)
                csrf_response.raise_for_status()
                csrf_token = csrf_response.json().get("csrfToken")

                signin_headers = csrf_headers | {
                    "content-type": "application/x-www-form-urlencoded",
                    "origin": "https://testnet.monad.xyz",
                }
                signin_data = {"csrfToken": csrf_token, "callbackUrl": "https://testnet.monad.xyz/", "json": "true"}
                signin_response = await self.session.post(
                    "https://testnet.monad.xyz/api/auth/signin/discord", headers=signin_headers, data=signin_data
                )
                signin_response.raise_for_status()
                url = signin_response.json().get("url")
                state = url.split("state=")[1].strip()

                oauth_headers = {
                    "accept": "*/*",
                    "authorization": self.discord_token,
                    "content-type": "application/json",
                    "origin": "https://discord.com",
                    "referer": f"https://discord.com/oauth2/authorize?client_id=1330973073914069084&scope=identify%20email%20guilds%20guilds.members.read&response_type=code&redirect_uri=https%3A%2F%2Ftestnet.monad.xyz%2Fapi%2Fauth%2Fcallback%2Fdiscord&state={state}",
                }
                oauth_params = {
                    "client_id": "1330973073914069084",
                    "response_type": "code",
                    "redirect_uri": "https://testnet.monad.xyz/api/auth/callback/discord",
                    "scope": "identify email guilds guilds.members.read",
                    "state": state,
                }
                oauth_data = {
                    "permissions": "0",
                    "authorize": True,
                    "integration_type": 0,
                    "location_context": {"guild_id": "10000", "channel_id": "10000", "channel_type": 10000},
                }
                oauth_response = await self.session.post(
                    "https://discord.com/api/v9/oauth2/authorize", params=oauth_params, headers=oauth_headers, json=oauth_data
                )
                oauth_response.raise_for_status()
                code = oauth_response.json().get("location").split("code=")[1].split("&")[0]

                callback_headers = {
                    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "sec-fetch-dest": "document",
                    "sec-fetch-mode": "navigate",
                    "sec-fetch-site": "cross-site",
                    "referer": "https://discord.com/",
                }
                callback_params = {"code": code, "state": state}
                callback_response = await self.session.get(
                    "https://testnet.monad.xyz/api/auth/callback/discord", params=callback_params, headers=callback_headers
                )
                callback_response.raise_for_status()
                logger.success(f"[{self.account_index}] Discord connected successfully!")
                return True

            except Exception as e:
                pause = random.randint(*self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS)
                logger.error(f"[{self.account_index}] Discord connect failed ({retry + 1}/{self.config.SETTINGS.ATTEMPTS}): {e}. Retry in {pause}s")
                await asyncio.sleep(pause)
        return False