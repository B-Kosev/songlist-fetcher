#!/usr/bin/env python3
"""Measure OpenAI input tokens and latency for ticket 13 model evaluation."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from worship_song_selector.config import OpenAIConfig, SupabaseConfig
from worship_song_selector.model_eval import format_eval_report
from worship_song_selector.model_eval_run import (
    default_eval_themes,
    measure_analysis_samples,
    measure_recommendation_queries,
)
from worship_song_selector.songs import create_supabase_client


def _load_openai_config() -> OpenAIConfig:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    if not api_key:
        secrets_path = Path(".streamlit/secrets.toml")
        if secrets_path.is_file():
            import tomllib

            data = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
            openai_raw = data.get("openai", {})
            api_key = str(openai_raw.get("api_key", "")).strip()
            model = str(openai_raw.get("model", model)).strip() or model
    return OpenAIConfig(api_key=api_key, model=model)


def _load_supabase_config() -> SupabaseConfig:
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = os.environ.get("SUPABASE_KEY", "").strip()
    if url and key:
        return SupabaseConfig(url=url, key=key)
    secrets_path = Path(".streamlit/secrets.toml")
    if secrets_path.is_file():
        import tomllib

        data = tomllib.loads(secrets_path.read_text(encoding="utf-8"))
        supabase_raw = data.get("supabase", {})
        return SupabaseConfig(
            url=str(supabase_raw.get("url", "")).strip(),
            key=str(supabase_raw.get("key", "")).strip(),
        )
    return SupabaseConfig(url=url, key=key)


def _read_themes_file(path: Path) -> list[str]:
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not lines:
        raise ValueError(f"No themes found in {path}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--themes-file",
        type=Path,
        help="Text file with one theme per line (overrides built-in sample themes).",
    )
    parser.add_argument(
        "--max-themes",
        type=int,
        default=len(default_eval_themes()),
        help="Use the first N built-in sample themes (ignored with --themes-file).",
    )
    parser.add_argument(
        "--skip-recommendations",
        action="store_true",
        help="Only run analysis sampling (if enabled).",
    )
    parser.add_argument(
        "--analysis-sample",
        type=int,
        default=0,
        help="Call the analysis API for the first N songs with lyrics (does not save).",
    )
    parser.add_argument(
        "--compare-model",
        metavar="MODEL",
        help="Run recommendations twice: current OPENAI_MODEL, then this model, "
        "and print both reports (same themes).",
    )
    args = parser.parse_args()

    openai_config = _load_openai_config()
    if not openai_config.api_key:
        print("Set OPENAI_API_KEY or [openai].api_key in .streamlit/secrets.toml", file=sys.stderr)
        return 1

    supabase_config = _load_supabase_config()
    if not supabase_config.url or not supabase_config.key:
        print(
            "Set SUPABASE_URL/SUPABASE_KEY or [supabase] in .streamlit/secrets.toml",
            file=sys.stderr,
        )
        return 1

    if args.themes_file:
        themes = _read_themes_file(args.themes_file)
    else:
        themes = default_eval_themes(max_themes=args.max_themes)

    client = create_supabase_client(supabase_config)
    analysis_records: list = []
    recommendation_by_theme: list = []
    catalogue_size = 0

    try:
        if args.analysis_sample:
            analysis_records = measure_analysis_samples(
                client,
                openai_config=openai_config,
                sample_size=args.analysis_sample,
            )
        if not args.skip_recommendations:
            recommendation_by_theme, catalogue_size = measure_recommendation_queries(
                client,
                openai_config=openai_config,
                themes=themes,
            )
        elif catalogue_size == 0:
            from worship_song_selector.songs import list_analysed_songs_for_recommendation

            catalogue_size = len(list_analysed_songs_for_recommendation(client))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Evaluation run failed: {exc}", file=sys.stderr)
        return 1

    report = format_eval_report(
        model=openai_config.model,
        analysis_records=analysis_records,
        recommendation_by_theme=recommendation_by_theme,
        catalogue_size=catalogue_size,
    )
    print(report)

    if args.compare_model:
        alt_config = OpenAIConfig(api_key=openai_config.api_key, model=args.compare_model)
        alt_by_theme, alt_catalogue = measure_recommendation_queries(
            client,
            openai_config=alt_config,
            themes=themes,
        )
        print("\n---\n")
        print(
            format_eval_report(
                model=alt_config.model,
                analysis_records=[],
                recommendation_by_theme=alt_by_theme,
                catalogue_size=alt_catalogue,
            ),
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
