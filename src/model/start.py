from loguru import logger
import primp
import random
import asyncio
from typing import Optional
from src.model.monad_xyz.instance import MonadXYZ
from src.utils.client import create_client
from src.utils.config import Config


class Start:
    def __init__(
            self,
            account_index: int,
            proxy: str,
            private_key: str,
            discord_token: Optional[str] = None,
            email: Optional[str] = None,
            config: Config = None,
    ):
        """
        初始化 Start 类，用于执行 Monad 测试网任务。

        Args:
            account_index: 账户索引。
            proxy: 代理字符串。
            private_key: 账户私钥。
            discord_token: 可选的 Discord 令牌。
            email: 可选的电子邮件地址。
            config: 配置对象。
        """
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.discord_token = discord_token
        self.email = email
        self.config = config or Config.load()
        self.session: Optional[primp.AsyncClient] = None

    async def initialize(self) -> bool:
        """
        初始化 HTTP 客户端。

        Returns:
            是否成功初始化。
        """
        try:
            self.session = await create_client(self.proxy)
            logger.info(f"[{self.account_index}] HTTP client initialized successfully.")
            return True
        except Exception as e:
            logger.error(f"[{self.account_index}] Initialization failed: {e}")
            return False

    async def flow(self) -> bool:
        """
        执行任务流程，根据配置执行指定任务。

        Returns:
            是否所有任务成功执行。
        """
        try:
            if not self.session:
                logger.error(f"[{self.account_index}] Session not initialized.")
                return False

            monad = MonadXYZ(
                self.account_index, self.proxy, self.private_key, self.discord_token, self.config, self.session
            )

            # 规划任务
            planned_tasks = []
            task_plan_msg = []
            for i, task_item in enumerate(self.config.FLOW.TASKS, 1):
                if isinstance(task_item, list):
                    # 如果task配置了多个任务就会自动随机选择一个
                    selected_task = random.choice(task_item)
                    planned_tasks.append((i, selected_task))
                    task_plan_msg.append(f"{i}. {selected_task}")
                else:
                    planned_tasks.append((i, task_item))
                    task_plan_msg.append(f"{i}. {task_item}")

            logger.info(f"[{self.account_index}] Task execution plan: {' | '.join(task_plan_msg)}")

            # 执行任务
            for _, task in planned_tasks:
                task = task.lower()
                await self._execute_task(task, monad)
                await self._sleep(task)

            return True
        except Exception as e:
            logger.error(f"[{self.account_index}] Flow execution failed: {e}")
            return False

    async def _execute_task(self, task: str, monad: MonadXYZ) -> None:
        """
        执行单个任务。

        Args:
            task: 任务名称。
            monad: MonadXYZ 实例。
        """
        task_handlers = {
            "izumi": lambda: monad.swaps(type="izumi"),
            "logs": self._logs_task,
        }

        handler = task_handlers.get(task)
        if handler:
            await handler()
        else:
            logger.warning(f"[{self.account_index}] Unknown task: {task}")

    async def _logs_task(self):
        """处理 'logs' 任务，记录钱包统计信息。"""
        from src.model.help.stats import WalletStats
        try:
            wallet_stats = WalletStats(self.config)
            await wallet_stats.get_wallet_stats(self.private_key, self.account_index)
            logger.info(f"[{self.account_index}] Wallet statistics logged successfully")
        except Exception as e:
            logger.error(f"[{self.account_index}] Failed to log wallet statistics: {e}")
            raise

    async def _sleep(self, task_name: str) -> None:
        """
        在任务间执行随机暂停。

        Args:
            task_name: 任务名称，用于日志记录。
        """
        pause = random.randint(
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[0],
            self.config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACTIONS[1],
        )
        logger.info(f"[{self.account_index}] Sleeping {pause} seconds after {task_name}")
        await asyncio.sleep(pause)