from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from .config import AppConfig, load_class


@dataclass(frozen=True)
class NarrativeResult:
    narrative: str
    tips: list[str]
    complex_move_notes: list[str]


class BaseNarrativeProvider:
    def generate(self, summary: dict[str, Any]) -> NarrativeResult:
        raise NotImplementedError


class MockNarrativeProvider(BaseNarrativeProvider):
    def generate(self, summary: dict[str, Any]) -> NarrativeResult:
        opening = summary.get("opening", {}).get("name", "Unknown opening")
        return NarrativeResult(
            narrative=f"Mock summary: game analyzed in {opening}.",
            tips=[
                "Review the largest evaluation swings first.",
                "Compare your move choices to the best engine line in critical moments.",
            ],
            complex_move_notes=[],
        )


class DisabledNarrativeProvider(BaseNarrativeProvider):
    def generate(self, summary: dict[str, Any]) -> NarrativeResult:
        return NarrativeResult(
            narrative="AI narrative disabled (offline mode).",
            tips=[],
            complex_move_notes=[],
        )


class GeminiNarrativeProvider(BaseNarrativeProvider):
    def __init__(self, api_url: str, api_key: str, model: str) -> None:
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def generate(self, summary: dict[str, Any]) -> NarrativeResult:
        endpoint = f"{self.api_url}/{self.model}:generateContent?key={self.api_key}"
        prompt = (
            "You are a chess coach. Given this JSON summary, produce: "
            "(1) 3-5 paragraph narrative, (2) 2-3 tips, (3) complex move notes.\n"
            f"JSON:\n{json.dumps(summary)}"
        )
        response = requests.post(
            endpoint,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=20,
        )
        response.raise_for_status()
        text = (
            response.json()
            .get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        return NarrativeResult(narrative=text, tips=[], complex_move_notes=[])


def create_narrative_provider(config: AppConfig) -> BaseNarrativeProvider:
    if config.ai_provider_class:
        cls = load_class(config.ai_provider_class, BaseNarrativeProvider)
        return cls()

    mode = config.external_api_mode.lower()
    provider = config.ai_provider.lower()

    if config.offline_mode or config.use_mock_apis or mode == "mock" or provider == "mock":
        return MockNarrativeProvider()
    if mode == "off" or provider == "disabled":
        return DisabledNarrativeProvider()
    if provider == "gemini":
        if not config.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when AI_PROVIDER=gemini")
        return GeminiNarrativeProvider(config.gemini_api_url, config.gemini_api_key, config.gemini_model)

    return MockNarrativeProvider()
