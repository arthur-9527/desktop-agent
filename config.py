"""
AgentDesk Remote Desktop Agent 配置
"""
import os

# AgentDesk 远程桌面连接配置
AGENTDESK_HOST = os.getenv("AGENTDESK_HOST", "localhost")
AGENTDESK_PORT = int(os.getenv("AGENTDESK_PORT", "9877"))
AGENTDESK_TOKEN = os.getenv("AGENTDESK_TOKEN", "admin123")

# LLM 配置
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://121.41.171.73:4000/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "sk-dummy")
GENERAL_MODEL = os.getenv("GENERAL_MODEL", "qwopus-27b")
VISION_MODEL = os.getenv("VISION_MODEL", "ui-tars")

# 执行参数
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
LOOP_INTERVAL_MS = int(os.getenv("LOOP_INTERVAL_MS", "500"))
SCREENSHOT_QUALITY = int(os.getenv("SCREENSHOT_QUALITY", "20"))
SCREENSHOT_MAX_WIDTH = int(os.getenv("SCREENSHOT_MAX_WIDTH", "1024"))
SCREENSHOT_MAX_HEIGHT = int(os.getenv("SCREENSHOT_MAX_HEIGHT", "768"))

# 日志级别
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")