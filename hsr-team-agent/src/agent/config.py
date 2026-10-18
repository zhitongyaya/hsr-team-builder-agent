"""配置模块。

集中从环境变量读取运行配置，避免在代码里散落魔法值。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """智能体运行配置。

    Attributes:
        model: 大模型名称。
        temperature: 采样温度。
        api_key: 大模型 API Key。
    """

    model: str = field(default_factory=lambda: os.getenv("AGENT_MODEL", "deepseek-chat"))
    temperature: float = field(
        default_factory=lambda: float(os.getenv("AGENT_TEMPERATURE", "0"))
    )
    api_key: str | None = field(default_factory=lambda: os.getenv("DEEPSEEK_API_KEY"))


settings = Settings()
