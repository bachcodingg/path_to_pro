"""LLM access for the agents: Claude via the Anthropic SDK, plus an on-disk cache.

The LLM is used only where judgment or language is needed. Every call returns a
Pydantic model; callers handle `LLMError` by falling back to rules, so the system
works with no API key and the demo works offline from the cache.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

log = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("PATHTOPRO_MODEL", "claude-opus-5-5")
DEFAULT_EFFORT = os.environ.get("PATHTOPRO_EFFORT", "medium")
CACHE_DIR = Path(os.environ.get("PATHTOPRO_LLM_CACHE", Path(__file__).resolve().parent.parent / "llm_cache"))
MAX_TOOL_TURNS = 6

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Any failure that should send the caller to its rule-based fallback."""


@dataclass
class Tool:
    """A client tool the model may call. `fn` receives the validated input dict."""

    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[[dict[str, Any]], Any]

    def to_param(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "strict": True,
        }


@dataclass
class Call:
    """One structured request: system + user text, answered as `output` type."""

    agent: str
    system: str
    user: str
    output: type[BaseModel]
    tools: list[Tool] = field(default_factory=list)
    retry_feedback: str | None = None  # validation error from the previous attempt

    def cache_key(self, model: str) -> str:
        payload = json.dumps(
            {
                "model": model,
                "agent": self.agent,
                "system": self.system,
                "user": self.user,
                "output": self.output.__name__,
                "schema": self.output.model_json_schema(),
                "tools": [t.name for t in self.tools],
                "retry": self.retry_feedback,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:24]


class LLMBackend(Protocol):
    name: str

    def complete(self, call: Call) -> BaseModel: ...


# --------------------------------------------------------------------------- Claude


class ClaudeBackend:
    """Claude through `messages.parse` (structured output validated by Pydantic).

    With tools, runs a manual agent loop: tool calls are executed locally and the
    model's full content is appended unchanged each turn (append-only history).
    Server-side refusal fallbacks are enabled (`fallbacks: "default"`).
    """

    name = "claude"

    def __init__(self, model: str = DEFAULT_MODEL, effort: str = DEFAULT_EFFORT, client: Any = None):
        self.model, self.effort = model, effort
        if client is None:
            try:
                import anthropic
            except ImportError as e:  # pragma: no cover
                raise LLMError("anthropic SDK not installed") from e
            client = anthropic.Anthropic(max_retries=2, timeout=60.0)
        self.client = client

    def complete(self, call: Call) -> BaseModel:
        import anthropic

        user = call.user
        if call.retry_feedback:
            user += (
                "\n\nYour previous answer was rejected by the validator with this error. "
                f"Return a corrected answer.\n{call.retry_feedback}"
            )
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        tools = {t.name: t for t in call.tools}
        try:
            for _ in range(MAX_TOOL_TURNS):
                kwargs: dict[str, Any] = {}
                if tools:
                    kwargs["tools"] = [t.to_param() for t in tools.values()]
                response = self.client.beta.messages.parse(
                    model=self.model,
                    max_tokens=16000,
                    system=call.system,
                    messages=messages,
                    output_format=call.output,
                    output_config={"effort": self.effort},
                    betas=["server-side-fallback-2026-07-01"],
                    fallbacks="default",
                    **kwargs,
                )
                if response.stop_reason == "refusal":
                    raise LLMError(f"refusal: {getattr(response.stop_details, 'category', None)}")
                if response.stop_reason == "max_tokens":
                    raise LLMError("max_tokens reached")
                tool_uses = [b for b in response.content if b.type == "tool_use"]
                if response.stop_reason == "tool_use" and tool_uses:
                    messages.append({"role": "assistant", "content": response.content})
                    results = []
                    for tu in tool_uses:
                        tool = tools.get(tu.name)
                        try:
                            if tool is None:
                                raise KeyError(f"unknown tool {tu.name}")
                            out = tool.fn(dict(tu.input))
                            results.append(
                                {"type": "tool_result", "tool_use_id": tu.id, "content": json.dumps(out, default=str)}
                            )
                        except Exception as e:  # tool errors go back to the model
                            results.append(
                                {"type": "tool_result", "tool_use_id": tu.id, "content": str(e), "is_error": True}
                            )
                    messages.append({"role": "user", "content": results})
                    continue
                if response.parsed_output is None:
                    raise LLMError("no structured output returned")
                return response.parsed_output
            raise LLMError("tool loop did not finish")
        except ValidationError as e:
            raise LLMValidationError(str(e)) from e
        except anthropic.APIConnectionError as e:
            raise LLMError(f"connection: {e}") from e
        except anthropic.RateLimitError as e:
            raise LLMError("rate limited") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"api status {e.status_code}") from e


class LLMValidationError(LLMError):
    """The model answered, but the answer did not validate. Worth one retry."""


# --------------------------------------------------------------------------- cache


class CachedBackend:
    """Replays stored answers; on a miss, asks `inner` (if any) and stores the answer.

    Cache files are committed for the demo scenarios so the demo runs offline.
    """

    name = "cached"

    def __init__(self, inner: LLMBackend | None, cache_dir: Path = CACHE_DIR, model: str = DEFAULT_MODEL):
        self.inner, self.cache_dir, self.model = inner, cache_dir, model
        self.hits = self.misses = 0

    def _path(self, call: Call) -> Path:
        return self.cache_dir / call.agent / f"{call.cache_key(self.model)}.json"

    def complete(self, call: Call) -> BaseModel:
        path = self._path(call)
        if path.exists():
            self.hits += 1
            data = json.loads(path.read_text(encoding="utf-8"))
            try:
                return call.output.model_validate(data)
            except ValidationError as e:
                raise LLMValidationError(str(e)) from e
        self.misses += 1
        if self.inner is None:
            raise LLMError("cache miss and no live LLM configured")
        result = self.inner.complete(call)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
        return result


def default_backend() -> LLMBackend | None:
    """Claude behind the cache when credentials exist, else cache-only.

    PATHTOPRO_LLM=off disables the LLM entirely (pure rule-based mode).
    """
    mode = os.environ.get("PATHTOPRO_LLM", "auto")
    if mode == "off":
        return None
    inner: LLMBackend | None = None
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or mode == "live":
        try:
            inner = ClaudeBackend()
        except LLMError as e:
            log.warning("Claude unavailable: %s", e)
    return CachedBackend(inner)


def complete_with_retry(backend: LLMBackend | None, call: Call) -> tuple[BaseModel | None, str]:
    """Plan section 4 pipeline: one retry on invalid output, then give up.

    Returns (result, source) with source in {"llm", "llm_retry", "unavailable", "invalid"}.
    """
    if backend is None:
        return None, "unavailable"
    try:
        return backend.complete(call), "llm"
    except LLMValidationError as e:
        log.info("%s: invalid LLM output, retrying once: %s", call.agent, e)
        call.retry_feedback = str(e)[:1500]
        try:
            return backend.complete(call), "llm_retry"
        except LLMError as e2:
            log.info("%s: retry failed: %s", call.agent, e2)
            return None, "invalid"
    except LLMError as e:
        log.info("%s: LLM unavailable: %s", call.agent, e)
        return None, "unavailable"
