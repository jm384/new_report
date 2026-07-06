from __future__ import annotations

import json
import re
from typing import Any

from config import AppSettings


class LLMError(RuntimeError):
    """Base error for LLM calls."""


class LLMQuotaExceededError(LLMError):
    """Raised when the provider reports insufficient quota."""


class LLMClient:
    def __init__(self, settings: AppSettings, logger: Any) -> None:
        self.settings = settings
        self.logger = logger
        self._client = None

    @property
    def is_configured(self) -> bool:
        return self.settings.llm.configured

    def _get_client(self):
        if self._client is not None:
            return self._client
        if not self.is_configured:
            return None
        if self.settings.llm.provider.lower() != "openai":
            raise LLMError(
                f"当前仅实现 openai provider，收到：{self.settings.llm.provider}"
            )
        try:
            from openai import OpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise LLMError(
                "缺少 openai 依赖，无法调用 LLM。请执行 pip install -r requirements.txt。"
            ) from exc
        kwargs = {"api_key": self.settings.llm.api_key}
        if self.settings.llm.base_url:
            kwargs["base_url"] = self.settings.llm.base_url
        self._client = OpenAI(**kwargs)
        return self._client

    def is_quota_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        markers = [
            "insufficient_quota",
            "quota exceeded",
            "quota failed",
            "pre-consumed quota failed",
            "user quota",
            "need quota",
            "local:insufficient_quota",
        ]
        return any(marker in message for marker in markers)

    def _normalize_exception(self, exc: Exception) -> Exception:
        if self.is_quota_error(exc):
            return LLMQuotaExceededError(str(exc))
        return exc

    def generate_text(
        self,
        *,
        phase: str,
        purpose: str,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.4,
    ) -> str:
        client = self._get_client()
        if client is None:
            raise LLMError("LLM 未配置。")
        self.logger.info(phase, f"正在调用 LLM：{purpose}")
        try:
            response = client.responses.create(
                model=self.settings.llm.model,
                input=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
            text = getattr(response, "output_text", "")
            if text:
                return text.strip()
        except Exception as first_exc:
            normalized = self._normalize_exception(first_exc)
            if isinstance(normalized, LLMQuotaExceededError):
                raise normalized
            self.logger.warning(
                phase,
                f"responses 接口调用失败，尝试兼容 chat.completions：{first_exc}",
            )

        try:
            response = client.chat.completions.create(
                model=self.settings.llm.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
            )
        except Exception as exc:
            normalized = self._normalize_exception(exc)
            if isinstance(normalized, Exception):
                raise normalized
            raise

        text = response.choices[0].message.content if response.choices else ""
        if not text:
            raise LLMError(f"LLM 未返回有效文本：{purpose}")
        return text.strip()

    def generate_json(
        self,
        *,
        phase: str,
        purpose: str,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.2,
    ) -> Any:
        text = self.generate_text(
            phase=phase,
            purpose=purpose,
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )
        return json.loads(self._extract_json(text))

    def _extract_json(self, text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
            stripped = re.sub(r"\s*```$", "", stripped)
        match = re.search(r"(\{.*\}|\[.*\])", stripped, re.DOTALL)
        if match:
            return match.group(1)
        return stripped
