#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable


REPO_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_DIR / "google-ads.yaml"
CONFIG_ENV_VAR = "GOOGLE_ADS_CONFIGURATION_FILE_PATH"
PLACEHOLDER_MARKERS = (
    "PASTE_GOOGLE_ADS_DEVELOPER_TOKEN_HERE",
    "PASTE_GOOGLE_CLIENT_ID_HERE",
    "PASTE_GOOGLE_CLIENT_SECRET_HERE",
    "PASTE_GOOGLE_ADS_REFRESH_TOKEN_HERE",
    "PASTE_MANAGER_CUSTOMER_ID_WITHOUT_DASHES_OR_REMOVE_THIS_LINE",
)


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def micros_to_float(value: int | None) -> float | None:
    if value is None:
        return None
    return value / 1_000_000


def metric_to_row(idea: Any) -> dict[str, Any]:
    metrics = idea.keyword_idea_metrics
    monthly = [
        {
            "year": item.year.name if hasattr(item.year, "name") else str(item.year),
            "month": item.month.name if hasattr(item.month, "name") else str(item.month),
            "searches": item.monthly_searches,
        }
        for item in metrics.monthly_search_volumes
    ]
    return {
        "keyword": idea.text,
        "avg_monthly_searches": metrics.avg_monthly_searches,
        "competition": metrics.competition.name,
        "competition_index": metrics.competition_index,
        "low_top_of_page_bid": micros_to_float(metrics.low_top_of_page_bid_micros),
        "high_top_of_page_bid": micros_to_float(metrics.high_top_of_page_bid_micros),
        "low_top_of_page_bid_micros": metrics.low_top_of_page_bid_micros,
        "high_top_of_page_bid_micros": metrics.high_top_of_page_bid_micros,
        "monthly_search_volumes": monthly,
    }


def write_csv(rows: list[dict[str, Any]], output: Path | None) -> None:
    fieldnames = [
        "keyword",
        "avg_monthly_searches",
        "competition",
        "competition_index",
        "low_top_of_page_bid",
        "high_top_of_page_bid",
        "low_top_of_page_bid_micros",
        "high_top_of_page_bid_micros",
        "monthly_search_volumes",
    ]
    handle = output.open("w", newline="", encoding="utf-8") if output else sys.stdout
    with handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            csv_row = dict(row)
            csv_row["monthly_search_volumes"] = json.dumps(
                row["monthly_search_volumes"], ensure_ascii=False
            )
            writer.writerow(csv_row)


def write_json(rows: list[dict[str, Any]], output: Path | None) -> None:
    text = json.dumps(rows, ensure_ascii=False, indent=2)
    if output:
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def iter_limited(items: Iterable[Any], limit: int | None) -> Iterable[Any]:
    for index, item in enumerate(items):
        if limit is not None and index >= limit:
            break
        yield item


def resolve_config_path(explicit_path: Path | None) -> Path | None:
    candidates = [
        explicit_path,
        Path(os.environ[CONFIG_ENV_VAR]).expanduser()
        if os.environ.get(CONFIG_ENV_VAR)
        else None,
        Path.cwd() / "google-ads.yaml",
        DEFAULT_CONFIG,
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate.resolve()
    return None


def validate_config_path(config_path: Path | None) -> Path:
    if config_path is None:
        raise FileNotFoundError(
            "Could not find google-ads.yaml. Copy google-ads.yaml.example to "
            f"google-ads.yaml, fill in credentials, or set {CONFIG_ENV_VAR}."
        )

    text = config_path.read_text(encoding="utf-8")
    placeholders = [marker for marker in PLACEHOLDER_MARKERS if marker in text]
    if placeholders:
        raise ValueError(
            f"{config_path} still contains placeholder values: "
            + ", ".join(placeholders)
        )

    return config_path


def build_request(client: Any, args: argparse.Namespace) -> Any:
    google_ads_service = client.get_service("GoogleAdsService")
    request = client.get_type("GenerateKeywordIdeasRequest")
    request.customer_id = args.customer_id
    request.language = google_ads_service.language_constant_path(args.language_id)
    request.geo_target_constants.extend(
        google_ads_service.geo_target_constant_path(location_id)
        for location_id in args.location_ids
    )
    request.include_adult_keywords = args.include_adult_keywords
    request.keyword_plan_network = getattr(
        client.enums.KeywordPlanNetworkEnum, args.network
    )

    keywords = parse_csv(args.keywords)
    if args.site:
        if keywords or args.url:
            raise ValueError("--site cannot be combined with --keywords or --url")
        request.site_seed.site = args.site
    elif keywords and args.url:
        request.keyword_and_url_seed.url = args.url
        request.keyword_and_url_seed.keywords.extend(keywords)
    elif keywords:
        request.keyword_seed.keywords.extend(keywords)
    elif args.url:
        request.url_seed.url = args.url
    else:
        raise ValueError("Provide at least one of --keywords, --url, or --site")

    return request


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate keyword ideas with Google Ads KeywordPlanIdeaService."
    )
    parser.add_argument("--customer-id", required=True, help="Google Ads customer ID.")
    parser.add_argument(
        "--keywords",
        help="Comma-separated seed keywords, for example 'crm,crm software'.",
    )
    parser.add_argument("--url", help="Page URL seed.")
    parser.add_argument("--site", help="Domain/site seed, for example 'example.com'.")
    parser.add_argument("--language-id", default="1019", help="Language constant ID.")
    parser.add_argument(
        "--location-ids",
        default="2704",
        type=parse_csv,
        help="Comma-separated geo target constant IDs.",
    )
    parser.add_argument(
        "--network",
        default="GOOGLE_SEARCH_AND_PARTNERS",
        choices=["GOOGLE_SEARCH", "GOOGLE_SEARCH_AND_PARTNERS"],
    )
    parser.add_argument("--include-adult-keywords", action="store_true")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--format", choices=["csv", "json"], default="csv")
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to google-ads.yaml. Defaults to env, cwd, then repo root.",
    )
    args = parser.parse_args()

    try:
        config_path = validate_config_path(resolve_config_path(args.config))
    except Exception as exc:
        print(f"Google Ads configuration is not ready: {exc}", file=sys.stderr)
        return 2

    try:
        from google.ads.googleads.client import GoogleAdsClient
    except ImportError:
        print(
            "Missing dependency: install with "
            "`python -m pip install -r requirements.txt`.",
            file=sys.stderr,
        )
        return 2

    try:
        client = GoogleAdsClient.load_from_storage(path=str(config_path))
        service = client.get_service("KeywordPlanIdeaService")
        request = build_request(client, args)
        response = service.generate_keyword_ideas(request=request)
        rows = [metric_to_row(idea) for idea in iter_limited(response, args.limit)]
    except Exception as exc:
        print(f"Google Ads keyword idea request failed: {exc}", file=sys.stderr)
        return 1

    if args.format == "json":
        write_json(rows, args.output)
    else:
        write_csv(rows, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
