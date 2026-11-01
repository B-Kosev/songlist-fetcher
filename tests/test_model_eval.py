from worship_song_selector.model_eval import (
    DEFAULT_EVAL_THEMES,
    extrapolate_analysis_import_tokens,
    extrapolate_recommendation_prompt_tokens,
    format_eval_report,
)
from worship_song_selector.openai_metrics import (
    OpenAIUsageRecord,
    approximate_input_tokens,
    summarize_usage_records,
)


def test_approximate_input_tokens_uses_cyrillic_heuristic():
    messages = [{"role": "user", "content": "абвгд"}]
    assert approximate_input_tokens(messages) == 3


def test_extrapolate_analysis_import_tokens_scales_mean_per_song():
    records = [
        OpenAIUsageRecord(prompt_tokens=1000, completion_tokens=50, latency_seconds=1.0),
        OpenAIUsageRecord(prompt_tokens=1200, completion_tokens=60, latency_seconds=1.2),
    ]
    total = extrapolate_analysis_import_tokens(records, target_songs=400)
    assert total == 440_000


def test_extrapolate_recommendation_prompt_tokens_scales_with_catalog():
    assert extrapolate_recommendation_prompt_tokens(
        prompt_tokens=10_000,
        catalogue_size=20,
        target_catalogue=400,
    ) == 200_000


def test_summarize_usage_records():
    records = [
        OpenAIUsageRecord(prompt_tokens=100, completion_tokens=10, latency_seconds=2.0),
        OpenAIUsageRecord(prompt_tokens=300, completion_tokens=30, latency_seconds=4.0),
    ]
    summary = summarize_usage_records(records)
    assert summary.count == 2
    assert summary.mean_prompt_tokens == 200
    assert summary.mean_latency_seconds == 3.0


def test_format_eval_report_includes_model_and_extrapolation():
    theme = DEFAULT_EVAL_THEMES[0]
    report = format_eval_report(
        model="gpt-4o-mini",
        analysis_records=[],
        recommendation_by_theme=[
            (
                theme,
                [
                    OpenAIUsageRecord(
                        prompt_tokens=8000,
                        completion_tokens=200,
                        latency_seconds=6.5,
                    ),
                ],
            ),
        ],
        catalogue_size=20,
    )
    assert "gpt-4o-mini" in report
    assert "8000" in report
    assert "400" in report
    assert theme[:20] in report
