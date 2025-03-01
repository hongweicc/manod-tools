import json
from typing import List, Dict, Any
from loguru import logger
from pathlib import Path


def read_txt_file(file_name: str, file_path: str) -> List[str]:
    """
    从指定路径读取文本文件，返回去除空白的行列表。

    Args:
        file_name: 文件的描述性名称，用于日志记录。
        file_path: 文件的路径。

    Returns:
        包含文件各行的字符串列表。

    Raises:
        FileNotFoundError: 如果文件不存在。
        IOError: 如果读取文件时发生错误。
    """
    try:
        file_path = Path(file_path)
        with file_path.open("r", encoding="utf-8") as file:
            items = [line.strip() for line in file if line.strip()]
        logger.success(f"Successfully loaded {len(items)} {file_name} from {file_path}.")
        return items
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except IOError as e:
        logger.error(f"Error reading {file_name} from {file_path}: {e}")
        raise


def split_list(lst: List[Any], chunk_size: int = 90) -> List[List[Any]]:
    """
    将列表分割成指定大小的子列表。

    Args:
        lst: 要分割的列表。
        chunk_size: 每个子列表的大小，默认为 90。

    Returns:
        包含子列表的列表。
    """
    if not isinstance(chunk_size, int) or chunk_size <= 0:
        raise ValueError(f"chunk_size must be a positive integer, got {chunk_size}")
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def read_abi(path: str) -> List[Dict[str, Any]]:
    """
    从指定路径读取 JSON ABI 文件。

    Args:
        path: ABI 文件的路径。

    Returns:
        ABI 数据，通常为字典或列表格式。

    Raises:
        FileNotFoundError: 如果文件不存在。
        json.JSONDecodeError: 如果 JSON 格式错误。
    """
    try:
        file_path = Path(path)
        with file_path.open("r", encoding="utf-8") as f:
            abi = json.load(f)
        logger.debug(f"Loaded ABI from {file_path}")
        return abi
    except FileNotFoundError:
        logger.error(f"ABI file not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in ABI file {file_path}: {e}")
        raise