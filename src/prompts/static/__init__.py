"""静态提示词模块

静态提示词在系统启动时构建，运行时保持不变，可以缓存复用。
"""

from .system import SYSTEM_ROLE
from .actions import AVAILABLE_ACTIONS
from .rules import EXECUTION_RULES
from .output_format import OUTPUT_FORMAT
from .verification import VERIFICATION_METHODS
from .shortcuts import get_shortcuts, WINDOWS_SHORTCUTS, MACOS_SHORTCUTS, LINUX_SHORTCUTS


__all__ = [
    "SYSTEM_ROLE",
    "AVAILABLE_ACTIONS",
    "EXECUTION_RULES",
    "OUTPUT_FORMAT",
    "VERIFICATION_METHODS",
    "get_shortcuts",
    "WINDOWS_SHORTCUTS",
    "MACOS_SHORTCUTS",
    "LINUX_SHORTCUTS",
]