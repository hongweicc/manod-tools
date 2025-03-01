from loguru import logger
import urllib3
import sys
import asyncio
import platform

# 常量定义
CONSOLE_LOG_FORMAT = (
    "<light-cyan>{time:HH:mm:ss}</light-cyan> | "
    "<level>{level: <8}</level> | "
    "<fg #ffffff>{name}:{line}</fg #ffffff> - <bold>{message}</bold>"
)
FILE_LOG_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} - {message}"
)
LOG_FILE = "logs/app.log"

def setup_event_loop():
    """根据操作系统设置适当的事件循环策略。"""
    if platform.system() == "Windows":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def configure_logging():
    """配置日志系统，包含控制台和文件输出。"""
    urllib3.disable_warnings()  # 禁用 urllib3 的警告
    logger.remove()  # 移除默认处理器

    # 配置控制台日志
    logger.add(
        sys.stdout,
        colorize=True,
        format=CONSOLE_LOG_FORMAT,
        level="INFO"
    )

    # 配置文件日志
    logger.add(
        LOG_FILE,
        rotation="10 MB",
        retention="1 month",
        format=FILE_LOG_FORMAT,
        level="INFO"
    )

async def main():
    """主函数：配置环境并启动程序。"""
    try:
        configure_logging()
        from process import start  # 延迟导入，优化启动速度
        await start()
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        raise

if __name__ == "__main__":
    setup_event_loop()  # 设置事件循环策略
    asyncio.run(main())