"""DeskAgent - UI-TARS 驱动的桌面自动化 Agent"""

__version__ = "1.1.0"

from .accessibility_parser import AccessibilityParser, create_info_table, GlobalInfo

__all__ = [
    "AgentDeskClient",
    "DeskAgent",
    "ActionExecutor",
    "AccessibilityParser",
    "create_info_table",
    "GlobalInfo",
]
