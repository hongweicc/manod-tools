import asyncio
import random
from typing import List, Optional, Tuple

from loguru import logger

import src.utils
from src.utils.logs import report_error, report_success
from src.utils.output import show_dev_info
import src.model
from src.utils.statistics import print_wallets_stats


async def start(config_file: str = "config.yaml"):
    """程序入口，初始化配置并启动异步任务。"""
    show_dev_info()
    config = src.utils.get_config(config_file)

    # 读取必要数据
    proxies = _load_file("proxies", "data/proxies.txt")
    if not proxies:
        logger.error("No proxies found. Please provide valid proxies.")
        return

    # 默认任务模式
    key_file = "data/keys_for_faucet.txt" if "farm_faucet" in config.FLOW.TASKS else "data/private_keys.txt"
    private_keys = _load_file("private keys", key_file)
    if not private_keys:
        logger.error(f"No private keys found in {key_file}")
        return

    # 账户范围处理
    accounts_info = _get_accounts_to_process(config, private_keys)
    if not accounts_info.accounts:
        logger.error("No accounts selected for processing.")
        return

    # 准备并发数据
    cycled_proxies = _cycle_list(proxies, len(accounts_info.accounts))
    discord_tokens = _load_file("discord tokens", "data/discord_tokens.txt", optional=True) or [""] * len(accounts_info.accounts)
    emails = _load_file("emails", "data/emails.txt", optional=True) or [""] * len(accounts_info.accounts)

    # 创建并运行任务
    semaphore = asyncio.Semaphore(config.SETTINGS.THREADS)
    lock = asyncio.Lock()
    tasks = [
        asyncio.create_task(
            _launch_account(
                index=accounts_info.start_index + idx,
                proxy=cycled_proxies[idx],
                private_key=acc,
                discord_token=discord_tokens[idx],
                email=emails[idx],
                config=config,
                semaphore=semaphore,
                lock=lock,
            )
        )
        for idx, acc in enumerate(accounts_info.accounts)
    ]

    logger.info(f"Starting {len(tasks)} accounts in random order: {accounts_info.order}")
    await asyncio.gather(*tasks)

    logger.success("All tasks completed successfully.")
    print_wallets_stats(config)


async def _launch_account(index: int, proxy: str, private_key: str, discord_token: str, email: str,
                          config: src.utils.config.Config, semaphore: asyncio.Semaphore, lock: asyncio.Lock):
    """包装器函数，限制并发并调用账户处理逻辑。"""
    async with semaphore:
        await account_flow(index, proxy, private_key, discord_token, email, config, lock)


async def account_flow(account_index: int, proxy: str, private_key: str, discord_token: str, email: str,
                       config: src.utils.config.Config, lock: asyncio.Lock):
    """处理单个账户的逻辑，包括初始化和流程执行。"""
    try:
        await _random_sleep(config.SETTINGS.RANDOM_INITIALIZATION_PAUSE, f"[{account_index}] Starting")

        instance = src.model.Start(account_index, proxy, private_key, discord_token, email, config)
        success = await _execute_with_retries(instance.initialize, config, f"[{account_index}] Initialization")
        success &= await _execute_with_retries(instance.flow, config, f"[{account_index}] Flow")

        await (report_success if success else report_error)(lock, proxy, discord_token, account_index)
        await _random_sleep(config.SETTINGS.RANDOM_PAUSE_BETWEEN_ACCOUNTS, f"[{account_index}] Next account")

    except Exception as err:
        logger.exception(f"[{account_index}] Account flow failed: {err}")
        logger.error(f"[{account_index}] Account flow failed: {str(err)}") # 不使用 logger.exception
        await report_error(lock, proxy, discord_token, account_index)


async def _execute_with_retries(function, config: src.utils.config.Config, log_prefix: str) -> bool:
    """执行带重试机制的异步函数。"""
    for attempt in range(config.SETTINGS.ATTEMPTS):
        result = await function()
        if isinstance(result, tuple) and result[0] is True:
            return True
        elif isinstance(result, bool) and result:
            return True

        if attempt < config.SETTINGS.ATTEMPTS - 1:
            pause = random.randint(*config.SETTINGS.PAUSE_BETWEEN_ATTEMPTS)
            logger.info(f"{log_prefix} | Attempt {attempt + 1}/{config.SETTINGS.ATTEMPTS} failed, sleeping {pause}s")
            await asyncio.sleep(pause)
    return False


def _load_file(file_type: str, file_path: str, optional: bool = False) -> List[str]:
    """读取文本文件并返回内容列表，带错误处理。"""
    try:
        content = src.utils.read_txt_file(file_type, file_path)
        return content if content else [] if optional else []
    except Exception as e:
        logger.error(f"Failed to load {file_type} from {file_path}: {e}")
        return [] if optional else []


def _get_accounts_to_process(config, private_keys: List[str]) -> Tuple[List[str], int, int, str]:
    """根据配置选择要处理的账户范围和顺序。"""
    start_idx, end_idx = config.SETTINGS.ACCOUNTS_RANGE
    if start_idx == 0 and end_idx == 0:
        if config.SETTINGS.EXACT_ACCOUNTS_TO_USE:
            indices = [i - 1 for i in config.SETTINGS.EXACT_ACCOUNTS_TO_USE]
            accounts = [private_keys[i] for i in indices if 0 <= i < len(private_keys)]
            start_idx, end_idx = min(config.SETTINGS.EXACT_ACCOUNTS_TO_USE), max(config.SETTINGS.EXACT_ACCOUNTS_TO_USE)
        else:
            accounts = private_keys
            start_idx, end_idx = 1, len(private_keys)
    else:
        accounts = private_keys[max(0, start_idx - 1):end_idx]

    indices = list(range(len(accounts)))
    random.shuffle(indices)
    order = " ".join(str(start_idx + i) for i in indices)
    return type('AccountsInfo', (), {'accounts': [accounts[i] for i in indices],
                                     'start_index': start_idx, 'end_index': end_idx, 'order': order})()


def _cycle_list(items: List[str], length: int) -> List[str]:
    """循环扩展列表到指定长度。"""
    return [items[i % len(items)] for i in range(length)]


async def _random_sleep(range_seconds: Tuple[int, int], log_msg: str):
    """在指定范围内随机暂停并记录日志。"""
    pause = random.randint(*range_seconds)
    logger.info(f"{log_msg} | Sleeping for {pause} seconds...")
    await asyncio.sleep(pause)