"""日志配置模块

提供统一的日志配置和获取 logger 的方法。
支持控制台输出和可选的文件输出。
"""

import logging
import sys
from typing import Optional

# 日志格式
CONSOLE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s"
FILE_FORMAT = "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(message)s"


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    console_format: str = CONSOLE_FORMAT,
    file_format: str = FILE_FORMAT,
):
    """配置根日志记录器

    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 可选的日志文件路径
        console_format: 控制台输出格式
        file_format: 文件输出格式
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 清除已有的处理器（避免重复配置）
    root_logger.handlers.clear()

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(console_format))
    root_logger.addHandler(console_handler)

    # 可选的文件处理器
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter(file_format))
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger

    Args:
        name: logger 名称，通常使用 __name__

    Returns:
        配置好的 Logger 实例
    """
    return logging.getLogger(name)