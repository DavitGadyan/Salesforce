"""Model providers behind the hybrid router.

Salesforce is the data source; these are the places a request can be answered:
  * native     – Salesforce itself (SOQL/aggregation), no model at all
  * claude     – Anthropic Claude (frontier quality, high-stakes drafts)
  * claude-fast– Claude Haiku (cheap, fast, bulk)
  * openai     – OpenAI ChatGPT models (optional, needs OPENAI_API_KEY)
  * private    – a self-hosted model behind the firewall (Ollama/vLLM, OpenAI-compatible)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import anthropic
import httpx

from ..core import config, llm


@dataclass
class Completion:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    cost_usd: float


class ProviderUnavailable(RuntimeError):
    pass


class Provider:
    id: str
    label: str
    kind: str  # native | external | private
    data_leaves_network: bool
    price_in: float = 0.0  # $ per 1M tokens
    price_out: float = 0.0

    def model(self) -> str: ...
    def available(self) -> tuple[bool, str]: ...
    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion: ...

    def info(self) -> dict:
        ok, note = self.available()
        return {"id": self.id, "label": self.label, "kind": self.kind, "model": self.model(), "available": ok, "note": note,
                "data_leaves_network": self.data_leaves_network, "price_in": self.price_in, "price_out": self.price_out}


class ClaudeProvider(Provider):
    kind, data_leaves_network = "external", True

    def __init__(self, pid: str, label: str, model: str, effort: str):
        self.id, self.label, self._model, self.effort = pid, label, model, effort
        self.price_in, self.price_out = llm.PRICES.get(model, (4.0, 20.0))

    def model(self) -> str:
        return self._model

    def available(self) -> tuple[bool, str]:
        return (True, "Anthropic API") if config.claude_configured() else (False, "Add ANTHROPIC_API_KEY")

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:
        t = time.time()
        kwargs = {"betas": [llm.FALLBACK_BETA], "fallbacks": "default"} if self._model in llm.FALLBACK_MODELS else {}
        try:
            r = llm.client().beta.messages.create(
                # Thinking is always on for these models and counts toward max_tokens: leave headroom.
                model=self._model, max_tokens=max_tokens + 8000, system=system, output_config={"effort": self.effort},
                messages=[{"role": "user", "content": prompt}], **kwargs)
        except anthropic.APIError as e:
            raise ProviderUnavailable(f"Claude error: {getattr(e, 'message', e)}") from e
        if r.stop_reason == "refusal":
            raise ProviderUnavailable("Claude declined the request")
        if r.stop_reason == "max_tokens":
            raise ProviderUnavailable("Claude's answer was cut off (max_tokens)")
        tin, tout = r.usage.input_tokens, r.usage.output_tokens
        return Completion("".join(b.text for b in r.content if b.type == "text"), r.model, tin, tout,
                          int((time.time() - t) * 1000), llm.cost_usd(self._model, tin, tout))


class OpenAICompatibleProvider(Provider):
    """OpenAI itself, or any OpenAI-compatible server (Ollama, vLLM, LM Studio, Azure OpenAI proxy)."""

    def __init__(self, pid: str, label: str, kind: str, model: str, base_url: str | None, api_key: str | None,
                 leaves: bool, price: tuple[float, float], timeout: float):
        self.id, self.label, self.kind, self._model = pid, label, kind, model
        self.base_url, self.api_key, self.data_leaves_network = base_url, api_key, leaves
        self.price_in, self.price_out = price
        self.timeout = timeout
        self._client = None

    def model(self) -> str:
        return self._model

    def available(self) -> tuple[bool, str]:
        if not self.api_key:
            return False, "Add OPENAI_API_KEY"
        if self.kind == "private":
            try:
                tags = httpx.get(self.base_url.replace("/v1", "") + "/api/tags", timeout=1.5).json()
                names = [m["name"] for m in tags.get("models", [])]
                if names and self._model not in names:
                    return False, f"Model {self._model} not pulled"
                return True, "Self-hosted, inside your network"
            except (httpx.HTTPError, ValueError):
                try:
                    httpx.get(self.base_url + "/models", timeout=1.5).raise_for_status()
                    return True, "Self-hosted, inside your network"
                except httpx.HTTPError:
                    return False, f"No server at {self.base_url}"
        return True, "OpenAI API"

    def _get(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout, max_retries=1)
        return self._client

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:
        from openai import OpenAIError
        t = time.time()
        try:
            r = self._get().chat.completions.create(
                model=self._model, max_completion_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}])
        except OpenAIError as e:
            raise ProviderUnavailable(f"{self.label} error: {e}") from e
        if r.choices[0].finish_reason == "length":
            raise ProviderUnavailable(f"{self.label}'s answer was cut off (max tokens)")
        u = r.usage
        tin, tout = (u.prompt_tokens, u.completion_tokens) if u else (0, 0)
        cost = round(tin / 1e6 * self.price_in + tout / 1e6 * self.price_out, 6)
        return Completion(r.choices[0].message.content or "", r.model or self._model, tin, tout, int((time.time() - t) * 1000), cost)


class NativeProvider(Provider):
    id, label, kind, data_leaves_network = "native", "Salesforce native", "native", False

    def model(self) -> str:
        return "SOQL / Flow"

    def available(self) -> tuple[bool, str]:
        return True, "No model needed"

    def complete(self, system: str, prompt: str, max_tokens: int) -> Completion:  # answered by workflows directly
        raise NotImplementedError


def registry() -> dict[str, Provider]:
    return {
        "native": NativeProvider(),
        "claude": ClaudeProvider("claude", "Claude Opus", config.AGENT_MODEL, "medium"),
        "claude-fast": ClaudeProvider("claude-fast", "Claude Haiku", config.BULK_MODEL, "low"),
        "openai": OpenAICompatibleProvider("openai", "ChatGPT", "external", config.OPENAI_MODEL, None,
                                           os.getenv("OPENAI_API_KEY"), True, (0.25, 2.0), 120),
        "private": OpenAICompatibleProvider("private", "Private LLM", "private", config.PRIVATE_LLM_MODEL,
                                            config.PRIVATE_LLM_BASE_URL, config.PRIVATE_LLM_API_KEY, False, (0.0, 0.0), 300),
    }
