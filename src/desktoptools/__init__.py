"""DesktopTools - AgentDesk HTTP API 封装

提供：
- DesktopAtomicOps: 18 个 HTTP 原子操作
- DesktopActions: 6 个高层动作（鼠标5 + 键盘1）
"""

from .atomic_ops import DesktopAtomicOps
from .actions import DesktopActions

__all__ = ["DesktopAtomicOps", "DesktopActions"]
