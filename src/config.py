"""配置管理模块"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """应用配置"""
    # AgentDesk
    agentdesk_host: str = os.getenv("AGENTDESK_HOST", "localhost")
    agentdesk_port: int = int(os.getenv("AGENTDESK_PORT", "9877"))
    agentdesk_token: str = os.getenv("AGENTDESK_TOKEN", "admin123")

    # UI-TARS 视觉模型
    vision_base_url: str = os.getenv("VISION_BASE_URL", "http://localhost:8000/v1")
    vision_api_key: str = os.getenv("VISION_API_KEY", "sk-dummy")
    vision_model: str = os.getenv("VISION_MODEL", "UI-TARS-1.5-7B")

    # LLM（可选，用于任务规划）
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:4000/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "sk-dummy")
    general_model: str = os.getenv("GENERAL_MODEL", "qwopus-35b")

    # 执行参数
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "25"))
    loop_interval_ms: int = int(os.getenv("LOOP_INTERVAL_MS", "500"))
    context_window_size: int = int(os.getenv("CONTEXT_WINDOW_SIZE", "5"))  # 保留最近 N 步的截图
    screenshot_quality: int = int(os.getenv("SCREENSHOT_QUALITY", "60"))
    screenshot_max_width: int = int(os.getenv("SCREENSHOT_MAX_WIDTH", "1366"))
    screenshot_max_height: int = int(os.getenv("SCREENSHOT_MAX_HEIGHT", "768"))

    # 日志
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # 调试模式
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"


def get_config() -> Config:
    """获取配置实例"""
    return Config()