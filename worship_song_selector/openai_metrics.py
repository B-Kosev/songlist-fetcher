from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class OpenAIUsageRecord:
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float


@dataclass(frozen=True)
class UsageSummary:
    count: int
    mean_prompt_tokens: float
    mean_completion_tokens: float
    mean_latency_seconds: float
    total_prompt_tokens: int
    total_latency_seconds: float


UsageCallback = Callable[[OpenAIUsageRecord], None]


def approximate_input_tokens(messages: list[dict[str, str]]) -> int:
    text = "".join(str(message.get("content", "")) for message in messages)
    # PRD: Cyrillic is ~2× English tokens; ~1 token per two UTF-8 chars is a rough lower bound.
    return max(1, (len(text) + 1) // 2)


def summarize_usage_records(records: list[OpenAIUsageRecord]) -> UsageSummary:
    if not records:
        return UsageSummary(
            count=0,
            mean_prompt_tokens=0.0,
            mean_completion_tokens=0.0,
            mean_latency_seconds=0.0,
            total_prompt_tokens=0,
            total_latency_seconds=0.0,
        )
    count = len(records)
    total_prompt = sum(record.prompt_tokens for record in records)
    total_completion = sum(record.completion_tokens for record in records)
    total_latency = sum(record.latency_seconds for record in records)
    return UsageSummary(
        count=count,
        mean_prompt_tokens=total_prompt / count,
        mean_completion_tokens=total_completion / count,
        mean_latency_seconds=total_latency / count,
        total_prompt_tokens=total_prompt,
        total_latency_seconds=total_latency,
    )
