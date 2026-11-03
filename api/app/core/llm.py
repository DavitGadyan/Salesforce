"""Thin wrapper around the Anthropic SDK used by every agent.

Two entry points:
  * `structured()` – one request whose answer must match a Pydantic schema
    (structured outputs), used for code review, mapping and refresh planning.
  * `tool_loop()` – a manual agentic loop over our own tools, used by the
    revenue agent. Write-type tools are expected to create approvals, never to
    mutate the CRM directly.

Every call is written to the audit log with model and token usage.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Callable, TypeVar

import anthropic
from pydantic import BaseModel

from . import db
from .config import AGENT_MODEL

T = TypeVar("T", bound=BaseModel)

PRICES = {  # $ per 1M tokens (input, output)
    "claude-opus-5-5": (4.0, 20.0),
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.0, 10.0),
}

# Server-side refusal fallback (Claude API). Haiku has no server-side fallback.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}

_client: anthropic.Anthropic | None = None


class LLMError(RuntimeError):
    pass


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=3, timeout=300)
    return _client


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    pin, pout = PRICES.get(model, (4.0, 20.0))
    return round(tokens_in / 1e6 * pin + tokens_out / 1e6 * pout, 5)


def strict_schema(model: type[BaseModel]) -> dict:
    """Pydantic JSON schema -> structured-outputs schema (no extra keys, all required)."""
    schema = copy.deepcopy(model.model_json_schema())

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object" and "properties" in node:
                node["additionalProperties"] = False
                node["required"] = list(node["properties"].keys())
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(schema)
    return schema


def _request_kwargs(model: str) -> dict:
    if model in FALLBACK_MODELS:
        return {"betas": [FALLBACK_BETA], "fallbacks": "default"}
    return {}


def _check(response: Any) -> None:
    if response.stop_reason == "refusal":
        category = getattr(getattr(response, "stop_details", None), "category", None)
        raise LLMError(f"Claude declined this request (category: {category}).")
    if response.stop_reason == "max_tokens":
        raise LLMError("Response hit max_tokens before finishing; retry with a smaller input.")


def _usage(response: Any) -> tuple[int, int]:
    u = response.usage
    tokens_in = (u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) + (
        getattr(u, "cache_creation_input_tokens", 0) or 0)
    return tokens_in, u.output_tokens or 0


def _call(**kwargs: Any) -> Any:
    try:
        return client().beta.messages.create(**kwargs)
    except anthropic.AuthenticationError as e:
        raise LLMError("Anthropic API key is invalid.") from e
    except anthropic.RateLimitError as e:
        raise LLMError("Rate limited by the Anthropic API; try again shortly.") from e
    except anthropic.BadRequestError as e:
        raise LLMError(f"Bad request to Claude: {e.message}") from e
    except anthropic.APIStatusError as e:
        raise LLMError(f"Claude API error {e.status_code}: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise LLMError("Could not reach the Anthropic API.") from e


def structured(*, system: str, prompt: str, schema: type[T], run_id: str | None, actor: str,
               model: str = AGENT_MODEL, effort: str = "high", max_tokens: int = 16000) -> T:
    response = _call(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": strict_schema(schema)}},
        **_request_kwargs(model),
    )
    _check(response)
    tokens_in, tokens_out = _usage(response)
    text = "".join(b.text for b in response.content if b.type == "text")
    try:
        parsed = schema.model_validate_json(text)
    except ValueError as e:
        raise LLMError(f"Claude returned output that does not match the schema: {e}") from e
    db.audit(actor, "llm_call", f"{schema.__name__} via {response.model}", {"cost_usd": cost_usd(model, tokens_in, tokens_out)},
             run_id=run_id, model=response.model, input_tokens=tokens_in, output_tokens=tokens_out)
    return parsed


ToolHandler = Callable[[dict], Any]


def tool_loop(*, system: str, prompt: str, tools: list[dict], handlers: dict[str, ToolHandler],
              run_id: str, actor: str, model: str = AGENT_MODEL, effort: str = "medium",
              max_turns: int = 40, on_progress: Callable[[str], None] | None = None) -> str:
    """Manual agentic loop. History is append-only (required for preserved thinking)."""
    messages: list[dict] = [{"role": "user", "content": prompt}]
    tools = [{**t, "strict": True} for t in tools]
    for turn in range(max_turns):
        response = _call(
            model=model,
            max_tokens=16000,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=tools,
            messages=messages,
            output_config={"effort": effort},
            **_request_kwargs(model),
        )
        tokens_in, tokens_out = _usage(response)
        db.audit(actor, "llm_turn", f"turn {turn + 1}: stop={response.stop_reason}",
                 {"cost_usd": cost_usd(model, tokens_in, tokens_out)}, run_id=run_id,
                 model=response.model, input_tokens=tokens_in, output_tokens=tokens_out)
        if response.stop_reason == "refusal":
            _check(response)
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "pause_turn":
            continue
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            return "".join(b.text for b in response.content if b.type == "text")
        results = []
        for block in tool_uses:
            handler = handlers.get(block.name)
            try:
                if handler is None:
                    raise ValueError(f"unknown tool {block.name}")
                output = handler(dict(block.input))
                is_error = False
            except Exception as e:  # tool errors go back to Claude, not up the stack
                output, is_error = f"Error: {e}", True
            db.audit(actor, "tool_call", f"{block.name}", {"input": block.input, "error": is_error},
                     run_id=run_id)
            if on_progress:
                on_progress(f"{block.name}({_short(block.input)})")
            results.append({"type": "tool_result", "tool_use_id": block.id,
                            "content": output if isinstance(output, str) else json.dumps(output, default=str),
                            "is_error": is_error})
        messages.append({"role": "user", "content": results})
    raise LLMError(f"Agent did not finish within {max_turns} turns.")


def _short(data: dict) -> str:
    s = json.dumps(data, default=str)
    return s if len(s) < 80 else s[:77] + "..."
