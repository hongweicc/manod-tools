from typing import List
from loguru import logger
from tabulate import tabulate
from rich.console import Console
from rich.table import Table as RichTable
from rich import box

from src.utils.config import Config, WalletInfo


def print_wallets_stats(config: Config) -> None:
    """
    输出所有钱包的统计信息，以彩色表格形式展示，并计算总额和平均值。

    Args:
        config: 配置对象，包含钱包信息。
    """
    console = Console()
    try:
        wallets = sorted(config.WALLETS.wallets, key=lambda x: x.account_index)
        if not wallets:
            logger.info("\nNo wallet statistics available")
            return

        # 准备表格数据（无私钥）
        table_data = _prepare_table_data(wallets)
        total_balance, total_transactions = _calculate_totals(wallets)

        # 使用 tabulate 生成纯文本表格
        headers = ["№ Account", "Wallet Address", "Balance (MON)", "Total Txs"]
        plain_table = tabulate(
            table_data,
            headers=headers,
            tablefmt="double_grid",
            stralign="center",
            numalign="center",
            colalign=("center", "left", "right", "right"),  # 动态对齐
        )

        # 使用 rich 生成彩色表格
        rich_table = RichTable(
            box=box.DOUBLE,
            border_style="bright_cyan",
            header_style="bold bright_cyan",
        )
        for header in headers:
            rich_table.add_column(header, justify="center" if header == "№ Account" else "left" if header == "Wallet Address" else "right")
        for row in table_data:
            rich_table.add_row(*row)

        # 计算统计信息
        wallets_count = len(wallets)
        avg_balance = total_balance / wallets_count
        avg_transactions = total_transactions / wallets_count

        # 输出彩色表格和统计信息
        stats_message = (
            f"\n{'=' * 50}\n"
            f"         Wallets Statistics ({wallets_count} wallets)\n"
            f"{'=' * 50}\n"
        )
        console.print(stats_message, style="bright_cyan")
        console.print(rich_table)
        console.print(f"{'=' * 50}", style="bright_cyan")
        console.print(f"Total balance: {total_balance:.4f} MON", style="green")
        console.print(f"Total transactions: {total_transactions:,}", style="green")
        console.print(f"Average balance: {avg_balance:.4f} MON", style="yellow")
        console.print(f"Average transactions: {avg_transactions:.1f}", style="yellow")
        console.print(f"{'=' * 50}", style="bright_cyan")

    except Exception as e:
        logger.error(f"Error while printing wallet statistics: {e}")


def _prepare_table_data(wallets: List[WalletInfo]) -> List[List[str]]:
    """
    准备钱包数据的表格格式，不包含私钥。

    Args:
        wallets: 已排序的钱包信息列表。

    Returns:
        表格数据，每行包含账户索引、地址、余额和交易总数。
    """
    return [
        [
            str(wallet.account_index),
            wallet.address,
            f"{wallet.balance:.4f} MON",
            f"{wallet.transactions:,}",
        ]
        for wallet in wallets
    ]


def _calculate_totals(wallets: List[WalletInfo]) -> tuple[float, int]:
    """
    计算所有钱包的总余额和总交易数。

    Args:
        wallets: 钱包信息列表。

    Returns:
        元组 (total_balance, total_transactions)。
    """
    total_balance = sum(wallet.balance for wallet in wallets)
    total_transactions = sum(wallet.transactions for wallet in wallets)
    return total_balance, total_transactions


if __name__ == "__main__":
    # 示例测试代码
    from dataclasses import dataclass

    @dataclass
    class WalletInfo:
        account_index: int
        private_key: str
        address: str
        balance: float
        transactions: int

    class Wallets:
        wallets = [
            WalletInfo(1, "0xabcdef123456789", "addr1_long_address_here", 10.5, 100),
            WalletInfo(2, "0x987654321fedcba", "addr2_even_longer_address", 20.75, 250),
        ]

    class Config:
        WALLETS = Wallets()

    config = Config()
    print_wallets_stats(config)