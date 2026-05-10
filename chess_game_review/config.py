from __future__ import annotations

import importlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Type


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    analysis_profile: str = "balanced"
    analyze_color: str = "all"
    external_api_mode: str = "mock"
    offline_mode: bool = True
    use_mock_apis: bool = True
    ai_provider: str = "mock"
    ai_provider_class: str | None = None
    gemini_api_url: str = "https://generativelanguage.googleapis.com/v1beta/models"
    gemini_api_key: str | None = None
    gemini_model: str = "gemma-3-27b-it"
    stockfish_path: str | None = None
    opening_db_path: str = str(Path(__file__).resolve().parent / "data" / "openings.tsv")

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls(
            analysis_profile=os.getenv("ANALYSIS_PROFILE", "balanced"),
            analyze_color=os.getenv("ANALYZE_COLOR", "all"),
            external_api_mode=os.getenv("EXTERNAL_API_MODE", "mock"),
            offline_mode=_as_bool(os.getenv("OFFLINE_MODE"), True),
            use_mock_apis=_as_bool(os.getenv("USE_MOCK_APIS"), True),
            ai_provider=os.getenv("AI_PROVIDER", "mock"),
            ai_provider_class=os.getenv("AI_PROVIDER_CLASS"),
            gemini_api_url=os.getenv(
                "GEMINI_API_URL",
                "https://generativelanguage.googleapis.com/v1beta/models",
            ),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemma-3-27b-it"),
            stockfish_path=os.getenv("STOCKFISH_PATH"),
            opening_db_path=os.getenv(
                "OPENING_DB_PATH",
                str(Path(__file__).resolve().parent / "data" / "openings.tsv"),
            ),
        )

    @property
    def search_depth(self) -> int:
        profile = self.analysis_profile.lower()
        return {"fast": 8, "balanced": 14, "deep": 20}.get(profile, 14)


def load_class(path: str, base_type: Type[Any]) -> Type[Any]:
    module_name, class_name = path.rsplit(".", 1)
    cls = getattr(importlib.import_module(module_name), class_name)
    if not issubclass(cls, base_type):
        raise TypeError(f"{path} must inherit from {base_type.__name__}")
    return cls
