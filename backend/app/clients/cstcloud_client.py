from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.security import require_api_key
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CSTCloudAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class CSTCloudClient:
    """Async OpenAI-compatible client for all China Science and Technology Cloud calls."""

    def __init__(self) -> None:
        self.settings = get_settings()

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {require_api_key()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _client(self, *, stream: bool = False) -> httpx.AsyncClient:
        timeout = httpx.Timeout(self.settings.request_timeout, connect=20.0, read=None if stream else self.settings.request_timeout)
        return httpx.AsyncClient(base_url=self.settings.cstcloud_base_url.rstrip("/"), headers=self._headers(), timeout=timeout)

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(self.settings.request_retries + 1):
            try:
                async with self._client() as client:
                    response = await client.request(method, path, **kwargs)
                if response.status_code >= 400:
                    detail = self._safe_error(response)
                    if response.status_code < 500 and response.status_code != 429:
                        raise CSTCloudAPIError(detail, response.status_code)
                    raise httpx.HTTPStatusError(detail, request=response.request, response=response)
                return response.json()
            except CSTCloudAPIError:
                raise
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self.settings.request_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
        logger.warning("CSTCloud request failed: path=%s error_type=%s", path, type(last_error).__name__)
        raise CSTCloudAPIError(f"科技云 API 请求失败：{last_error}") from last_error

    @staticmethod
    def _safe_error(response: httpx.Response) -> str:
        try:
            body = response.json()
            message = body.get("error", body)
            if isinstance(message, dict):
                message = message.get("message") or message.get("detail") or str(message)
            return f"科技云 API 返回 {response.status_code}：{message}"
        except ValueError:
            return f"科技云 API 返回 {response.status_code}"

    async def list_models(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/models")
        data = payload.get("data", payload.get("models", []))
        return data if isinstance(data, list) else []

    @staticmethod
    def compatible_messages(model: str, messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
        if "deepseek-r1" not in model.lower():
            return list(messages)
        # Some hosted R1 variants accept only a user role. Preserve the intent in one turn.
        merged = "\n\n".join(f"{m['role'].upper()}:\n{m['content']}" for m in messages)
        return [{"role": "user", "content": merged}]

    @staticmethod
    def thinking_kwargs(model: str, enabled: bool) -> dict[str, Any]:
        normalized = model.lower()
        if "qwen3:235b" in normalized:
            return {"chat_template_kwargs": {"enable_thinking": enabled}}
        if "deepseek-v4-flash" in normalized:
            return {"chat_template_kwargs": {"thinking": enabled}}
        return {}

    def chat_payload(
        self,
        *,
        model: str,
        messages: Sequence[dict[str, str]],
        temperature: float,
        top_p: float,
        max_length: int,
        stream: bool,
        enable_thinking: bool = False,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "messages": self.compatible_messages(model, messages),
            "temperature": temperature,
            "top_p": top_p,
            "max_length": max_length,
            "stream": stream,
            **self.thinking_kwargs(model, enable_thinking),
        }

    async def chat_completion(self, **kwargs: Any) -> dict[str, Any]:
        return await self._request("POST", "/chat/completions", json=self.chat_payload(stream=False, **kwargs))

    async def stream_chat_completion(self, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        payload = self.chat_payload(stream=True, **kwargs)
        last_error: Exception | None = None
        emitted = False
        for attempt in range(self.settings.request_retries + 1):
            try:
                async with self._client(stream=True) as client:
                    async with client.stream("POST", "/chat/completions", json=payload) as response:
                        if response.status_code >= 400:
                            await response.aread()
                            raise CSTCloudAPIError(self._safe_error(response), response.status_code)
                        async for line in response.aiter_lines():
                            if not line or not line.startswith("data:"):
                                continue
                            data = line[5:].strip()
                            if data == "[DONE]":
                                return
                            try:
                                event = json.loads(data)
                            except json.JSONDecodeError:
                                continue
                            delta = (event.get("choices") or [{}])[0].get("delta", {})
                            emitted = True
                            yield {
                                "content": delta.get("content") or "",
                                "reasoning_content": delta.get("reasoning_content") or "",
                                "finish_reason": (event.get("choices") or [{}])[0].get("finish_reason"),
                            }
                return
            except CSTCloudAPIError:
                raise
            except httpx.HTTPError as exc:
                last_error = exc
                # Retrying after the first token would duplicate answer content.
                if emitted:
                    raise CSTCloudAPIError(f"科技云流式连接中断：{exc}") from exc
                if attempt < self.settings.request_retries:
                    await asyncio.sleep(0.5 * (2**attempt))
        raise CSTCloudAPIError(f"科技云流式请求失败：{last_error}") from last_error

    async def embeddings(self, model: str, texts: Sequence[str]) -> list[list[float]]:
        payload = await self._request("POST", "/embeddings", json={"model": model, "input": list(texts)})
        data = sorted(payload.get("data", []), key=lambda item: item.get("index", 0))
        vectors = [item.get("embedding", []) for item in data]
        if len(vectors) != len(texts):
            raise CSTCloudAPIError("Embedding 返回数量与输入不一致")
        return vectors

    async def rerank(self, model: str, query: str, documents: Sequence[str], top_n: int) -> list[dict[str, Any]]:
        payload = await self._request(
            "POST",
            "/rerank",
            json={"model": model, "query": query, "documents": list(documents), "top_n": top_n},
        )
        results = payload.get("results", payload.get("data", []))
        return results if isinstance(results, list) else []
