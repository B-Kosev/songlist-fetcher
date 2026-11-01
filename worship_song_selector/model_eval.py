from __future__ import annotations

from worship_song_selector.openai_metrics import OpenAIUsageRecord, summarize_usage_records

DEFAULT_EVAL_THEMES: tuple[str, ...] = (
    "Благодарност и радост в Бога след трудна година",
    "Покаяние и обновление — пророк Илия на Кармил",
    "Божията вярност в изпитания — книга на Даниил",
    "Кръстът и възкресението — Великден",
    "Молитва за единство в църквата",
    "Божията любов и приемане — притча за блудния син",
    "Изпращане и мисия — Велико поръчание",
    "Тихо поклонение — Бог е близо в страдание",
)


def extrapolate_analysis_import_tokens(
    records: list[OpenAIUsageRecord],
    *,
    target_songs: int = 400,
) -> int:
    summary = summarize_usage_records(records)
    if summary.count == 0:
        return 0
    return int(round(summary.mean_prompt_tokens * target_songs))


def extrapolate_analysis_import_latency_seconds(
    records: list[OpenAIUsageRecord],
    *,
    target_songs: int = 400,
) -> float:
    summary = summarize_usage_records(records)
    if summary.count == 0:
        return 0.0
    return summary.mean_latency_seconds * target_songs


def extrapolate_recommendation_prompt_tokens(
    *,
    prompt_tokens: int,
    catalogue_size: int,
    target_catalogue: int = 400,
) -> int:
    if catalogue_size <= 0:
        return prompt_tokens
    return int(round(prompt_tokens * target_catalogue / catalogue_size))


def extrapolate_recommendation_latency_seconds(
    *,
    mean_latency_seconds: float,
    prompt_tokens: int,
    catalogue_size: int,
    target_catalogue: int = 400,
) -> float:
    if catalogue_size <= 0 or prompt_tokens <= 0:
        return mean_latency_seconds
    scaled_tokens = extrapolate_recommendation_prompt_tokens(
        prompt_tokens=prompt_tokens,
        catalogue_size=catalogue_size,
        target_catalogue=target_catalogue,
    )
    return mean_latency_seconds * (scaled_tokens / prompt_tokens)


def format_eval_report(
    *,
    model: str,
    analysis_records: list[OpenAIUsageRecord],
    recommendation_by_theme: list[tuple[str, list[OpenAIUsageRecord]]],
    catalogue_size: int,
    target_catalogue: int = 400,
) -> str:
    analysis_summary = summarize_usage_records(analysis_records)
    recommendation_records = [
        record for _, theme_records in recommendation_by_theme for record in theme_records
    ]
    recommendation_summary = summarize_usage_records(recommendation_records)

    analysis_extrap = extrapolate_analysis_import_tokens(
        analysis_records,
        target_songs=target_catalogue,
    )
    analysis_latency_extrap = extrapolate_analysis_import_latency_seconds(
        analysis_records,
        target_songs=target_catalogue,
    )
    lines: list[str] = [
        "# Model quality evaluation (ticket 13)",
        "",
        f"- Model: `{model}`",
        f"- Analysed songs in library: {catalogue_size}",
        "",
        "## Analysis calls (per song)",
    ]
    if analysis_summary.count:
        lines.extend(
            [
                f"- Calls recorded: {analysis_summary.count}",
                f"- Mean input tokens: {analysis_summary.mean_prompt_tokens:.0f}",
                f"- Mean latency (s): {analysis_summary.mean_latency_seconds:.2f}",
                f"- Extrapolated input tokens for ~{target_catalogue} songs: "
                f"**{analysis_extrap:,}**",
                f"- Extrapolated wall time (sequential, ~{target_catalogue} songs): "
                f"**{analysis_latency_extrap / 60:.1f} min**",
            ],
        )
        lines.append("")
        lines.append("| # | input tokens | latency (s) |")
        lines.append("|---|--------------|-------------|")
        for index, record in enumerate(analysis_records, start=1):
            lines.append(
                f"| {index} | {record.prompt_tokens} | {record.latency_seconds:.2f} |",
            )
    else:
        lines.append("- No analysis API calls in this run.")

    lines.extend(["", "## Recommendation calls (per theme query)"])
    if recommendation_summary.count:
        mean_prompt = recommendation_summary.mean_prompt_tokens
        mean_latency = recommendation_summary.mean_latency_seconds
        extrap_prompt = extrapolate_recommendation_prompt_tokens(
            prompt_tokens=int(round(mean_prompt)),
            catalogue_size=catalogue_size,
            target_catalogue=target_catalogue,
        )
        extrap_latency = extrapolate_recommendation_latency_seconds(
            mean_latency_seconds=mean_latency,
            prompt_tokens=int(round(mean_prompt)),
            catalogue_size=catalogue_size,
            target_catalogue=target_catalogue,
        )
        lines.extend(
            [
                f"- Themes run: {len(recommendation_by_theme)}",
                f"- API calls recorded: {recommendation_summary.count} "
                f"(includes retries)",
                f"- Mean input tokens: {mean_prompt:.0f}",
                f"- Mean latency (s): {mean_latency:.2f}",
                f"- Extrapolated mean input tokens at ~{target_catalogue} songs: "
                f"**{extrap_prompt:,}**",
                f"- Extrapolated mean latency at ~{target_catalogue} songs: "
                f"**{extrap_latency:.1f} s** (scales with prompt size)",
            ],
        )
        lines.append("")
        lines.append("| Theme | calls | input tokens (sum) | latency (s, sum) |")
        lines.append("|-------|-------|----------------------|--------------------|")
        for theme, theme_records in recommendation_by_theme:
            theme_summary = summarize_usage_records(theme_records)
            short_theme = theme if len(theme) <= 48 else f"{theme[:45]}…"
            lines.append(
                f"| {short_theme} | {theme_summary.count} | "
                f"{theme_summary.total_prompt_tokens} | "
                f"{theme_summary.total_latency_seconds:.2f} |",
            )
    else:
        lines.append("- No recommendation API calls in this run.")

    lines.extend(
        [
            "",
            "## Human verdict (fill in)",
            "",
            "- Analysis accuracy (e.g. 17/20 correct energy): …",
            "- Set quality for themes: …",
            "- Input tokens / latency notes: …",
            "- Decision: keep model / switch to …",
            "- Follow-up tickets: …",
        ],
    )
    return "\n".join(lines)
