import os
from asyncio import Lock
from loguru import logger


async def report_success(
        lock: Lock, proxy: str, discord_token: str, account_index: int = None
) -> None:
    """
    Log successful operations to files in data/success_data directory without saving private keys.
    Uses asyncio lock to prevent race conditions.

    Args:
        lock: Asyncio lock for thread-safe file operations
        private_key: The private key (not saved, included for compatibility)
        proxy: The proxy to log
        discord_token: The Discord token to log
        account_index: The account index to log (optional, defaults to 'unknown')
    """
    base_dir = "data/success_data"
    async with lock:
        os.makedirs(base_dir, exist_ok=True)

        # Write non-sensitive data to respective files
        files_data = {
            "account_indices.txt": str(account_index) if account_index is not None else "unknown",
            "proxies.txt": proxy,
            "discord_tokens.txt": discord_token,
        }

        for filename, data in files_data.items():
            if data:  # Only write if data is not empty
                filepath = os.path.join(base_dir, filename)
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(f"{data}\n")
        logger.info(f"Success reported for account {account_index or 'unknown'} with proxy {proxy}")


async def report_error(
        lock: Lock, proxy: str, discord_token: str, account_index: int = None
) -> None:
    """
    Log failed operations to files in data/error_data directory without saving private keys.
    Uses asyncio lock to prevent race conditions.

    Args:
        lock: Asyncio lock for thread-safe file operations
        private_key: The private key (not saved, included for compatibility)
        proxy: The proxy to log
        discord_token: The Discord token to log
        account_index: The account index to log (optional, defaults to 'unknown')
    """
    base_dir = "data/error_data"
    async with lock:
        os.makedirs(base_dir, exist_ok=True)

        # Write non-sensitive data to respective files
        files_data = {
            "account_indices.txt": str(account_index) if account_index is not None else "unknown",
            "proxies.txt": proxy,
            "discord_tokens.txt": discord_token,
        }

        for filename, data in files_data.items():
            if data:  # Only write if data is not empty
                filepath = os.path.join(base_dir, filename)
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(f"{data}\n")
        logger.info(f"Error reported for account {account_index or 'unknown'} with proxy {proxy}")