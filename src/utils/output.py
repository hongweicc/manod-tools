import os
from rich.console import Console
from rich.table import Table
from rich import box


def show_dev_info(console: Console = None) -> None:
    """显示开发者信息和版本号。

    Args:
        console: 可选的 rich.console.Console 实例，默认创建新实例。
    """
    console = console or Console()

    # 开发者信息配置（可从外部配置文件读取）
    dev_info = {
        "title": "✨ StarLabs Monad Bot 1.8 ✨",
        "github": "https://github.com/0xStarLabs",
        "dev_telegram": "https://t.me/StarLabsTech",
        "chat_telegram": "https://t.me/StarLabsChat",
    }

    table = Table(
        show_header=False,
        box=box.DOUBLE,
        border_style="bright_cyan",
        pad_edge=False,
        width=49,
    )
    table.add_column("Content", style="bright_cyan", justify="center")

    table.add_row(dev_info["title"])
    table.add_row("─" * 43)
    table.add_row("")
    table.add_row(f"⚡ GitHub: [link={dev_info['github']}]{dev_info['github']}[/link]")
    table.add_row(f"👤 Dev: [link={dev_info['dev_telegram']}]{dev_info['dev_telegram']}[/link]")
    table.add_row(f"💬 Chat: [link={dev_info['chat_telegram']}]{dev_info['chat_telegram']}[/link]")
    table.add_row("")

    console.print(table, justify="center")


if __name__ == "__main__":
    show_dev_info()