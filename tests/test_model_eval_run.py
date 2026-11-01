from unittest.mock import MagicMock, patch

from worship_song_selector.config import OpenAIConfig
from worship_song_selector.model_eval_run import measure_recommendation_queries
from worship_song_selector.openai_metrics import OpenAIUsageRecord


@patch("worship_song_selector.model_eval_run.recommend_set_with_completion")
@patch("worship_song_selector.model_eval_run.make_openai_completion_fn")
@patch("worship_song_selector.model_eval_run.fetch_flow_template")
@patch("worship_song_selector.model_eval_run.list_analysed_songs_for_recommendation")
def test_measure_recommendation_queries_collects_usage_per_theme(
    mock_list_songs,
    mock_fetch_flow,
    mock_make_completion,
    mock_recommend,
):
    mock_list_songs.return_value = [
        {"id": str(i), "title": f"Song {i}"} for i in range(5)
    ]
    mock_fetch_flow.return_value = []
    captured: list = []

    def fake_make_completion(**kwargs):
        on_usage = kwargs["on_usage"]

        def complete(_messages):
            on_usage(
                OpenAIUsageRecord(
                    prompt_tokens=100,
                    completion_tokens=10,
                    latency_seconds=0.5,
                ),
            )
            return "{}"

        captured.append(on_usage)
        return complete

    mock_make_completion.side_effect = fake_make_completion

    def fake_recommend(completion, **_kwargs):
        completion([{"role": "user", "content": "test"}])
        return None

    mock_recommend.side_effect = fake_recommend

    client = MagicMock()
    by_theme, catalogue_size = measure_recommendation_queries(
        client,
        openai_config=OpenAIConfig(api_key="test-key"),
        themes=["тема 1", "тема 2"],
    )

    assert catalogue_size == 5
    assert len(by_theme) == 2
    assert sum(len(records) for _, records in by_theme) == 2
    assert mock_recommend.call_count == 2
