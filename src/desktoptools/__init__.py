"""DesktopTools - AgentDesk HTTP API 封装

提供：
- DesktopClient: 统一客户端，封装原子操作和屏幕信息缓存
- DesktopAtomicOps: 18 个 HTTP 原子操作
"""

from .client import DesktopClient
from .atomic_ops import DesktopAtomicOps

__all__ = ["DesktopClient", "DesktopAtomicOps"]
