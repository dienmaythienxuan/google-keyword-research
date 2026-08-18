#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
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
ISO2_RE = re.compile(r"^[A-Za-z]{2}$")
COUNTRY_ALIASES = {
    "uk": "GB",
    "great britain": "GB",
    "britain": "GB",
    "usa": "US",
    "united states of america": "US",
    "viet nam": "VN",
    "korea": "KR",
    "south korea": "KR",
    "republic of korea": "KR",
    "north korea": "KP",
}
LANGUAGE_ALIASES = {
    "zh": "zh_CN",
    "chinese": "zh_CN",
    "simplified chinese": "zh_CN",
    "traditional chinese": "zh_TW",
    "tieng viet": "vi",
    "hebrew": "iw",
    "filipino": "tl",
    "tagalog": "tl",
}


def parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def normalize_customer_id(value: str) -> str:
    return value.replace("-", "").strip()


def normalize_token(value: str) -> str:
    stripped = unicodedata.normalize("NFKD", value.strip())
    without_marks = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    return " ".join(without_marks.lower().replace("_", " ").replace("-", " ").split())


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


@dataclass(frozen=True)
class ResolvedTargeting:
    language_id: str
    language_label: str
    location_ids: list[str]
    location_labels: list[str]

    def summary(self) -> str:
        locations = "; ".join(self.location_labels) if self.location_labels else "(none)"
        return (
            f"Resolved targeting: language={self.language_label}; "
            f"locations={locations}"
        )


def _enum_name(value: Any) -> str:
    return value.name if hasattr(value, "name") else str(value)


def _search_rows(client: Any, customer_id: str, query: str) -> list[Any]:
    google_ads_service = client.get_service("GoogleAdsService")
    return list(google_ads_service.search(customer_id=customer_id, query=query))


def resolve_language(client: Any, customer_id: str, language: str) -> tuple[str, str]:
    requested = language.strip()
    alias = LANGUAGE_ALIASES.get(normalize_token(requested), requested)
    token = alias.strip().lower().replace(" ", "_")
    query = """
        SELECT
          language_constant.id,
          language_constant.code,
          language_constant.name
        FROM language_constant
        WHERE language_constant.targetable = TRUE
    """
    scored: list[tuple[int, str, str]] = []
    for row in _search_rows(client, customer_id, query):
        constant = row.language_constant
        code = (constant.code or "").lower()
        name = (constant.name or "").lower()
        label = f"{constant.name} ({constant.code}, {constant.id})"
        language_id = str(constant.id)
        score = 0
        if code == token:
            score = 100
        elif name == token.replace("_", " "):
            score = 90
        elif code.startswith(f"{token}_"):
            score = 70
        elif name.startswith(token.replace("_", " ")):
            score = 50
        if score:
            scored.append((score, language_id, label))

    if not scored:
        raise ValueError(
            f"Could not resolve language '{language}'. "
            "Use an ISO code or English name, for example vi, Vietnamese, en, English."
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    best_score = scored[0][0]
    top = [item for item in scored if item[0] == best_score]
    unique = {item[1]: item for item in top}
    if len(unique) > 1:
        options = ", ".join(item[2] for item in unique.values())
        raise ValueError(
            f"Language '{language}' is ambiguous. Specify one of: {options}"
        )
    _, language_id, label = next(iter(unique.values()))
    return language_id, label


def _country_lookup_value(country: str) -> str:
    token = normalize_token(country)
    aliased = COUNTRY_ALIASES.get(token)
    if aliased:
        return aliased
    if ISO2_RE.fullmatch(country.strip()):
        return country.strip().upper()
    return country.strip()


def _resolve_country_by_code(
    client: Any, customer_id: str, country_code: str
) -> tuple[str, str] | None:
    query = f"""
        SELECT
          geo_target_constant.id,
          geo_target_constant.name,
          geo_target_constant.country_code,
          geo_target_constant.target_type
        FROM geo_target_constant
        WHERE geo_target_constant.country_code = '{country_code}'
          AND geo_target_constant.target_type = 'Country'
          AND geo_target_constant.status = 'ENABLED'
    """
    rows = _search_rows(client, customer_id, query)
    if not rows:
        return None
    geo = rows[0].geo_target_constant
    return str(geo.id), f"{geo.name} ({geo.country_code}, {geo.id})"


def _resolve_country_by_name(client: Any, country: str) -> tuple[str, str]:
    geo_service = client.get_service("GeoTargetConstantService")
    request = client.get_type("SuggestGeoTargetConstantsRequest")
    request.locale = "en"
    request.location_names.names.append(country)
    response = geo_service.suggest_geo_target_constants(request=request)

    suggestions = []
    for suggestion in response.geo_target_constant_suggestions:
        geo = suggestion.geo_target_constant
        if _enum_name(geo.status) != "ENABLED":
            continue
        suggestions.append(geo)

    if not suggestions:
        raise ValueError(
            f"Could not resolve country '{country}'. "
            "Use an ISO-2 code or English country name, for example VN or Vietnam."
        )

    normalized = normalize_token(country)

    def is_country(geo: Any) -> bool:
        return geo.target_type == "Country"

    def name_matches(geo: Any) -> bool:
        return normalize_token(geo.name or "") == normalized

    def code_matches(geo: Any) -> bool:
        return (geo.country_code or "").upper() == country.strip().upper()

    for predicate in (
        lambda geo: is_country(geo) and (name_matches(geo) or code_matches(geo)),
        is_country,
        name_matches,
    ):
        matches = [geo for geo in suggestions if predicate(geo)]
        unique = {str(geo.id): geo for geo in matches}
        if len(unique) == 1:
            geo = next(iter(unique.values()))
            return str(geo.id), f"{geo.name} ({geo.country_code}, {geo.id})"
        if len(unique) > 1:
            options = ", ".join(
                f"{geo.name} ({geo.country_code}, {geo.id}, {geo.target_type})"
                for geo in unique.values()
            )
            raise ValueError(
                f"Country '{country}' is ambiguous. Specify one of: {options}"
            )

    options = ", ".join(
        f"{geo.name} ({geo.country_code}, {geo.id}, {geo.target_type})"
        for geo in suggestions[:8]
    )
    raise ValueError(
        f"Could not uniquely resolve country '{country}'. Closest matches: {options}"
    )


def resolve_country(
    client: Any, customer_id: str, country: str
) -> tuple[str, str]:
    lookup = _country_lookup_value(country)
    if ISO2_RE.fullmatch(lookup):
        resolved = _resolve_country_by_code(client, customer_id, lookup.upper())
        if resolved:
            return resolved
    return _resolve_country_by_name(client, lookup)


def resolve_targeting(client: Any, args: argparse.Namespace) -> ResolvedTargeting:
    customer_id = args.customer_id
    if args.language_id:
        language_id = str(args.language_id)
        language_label = f"language ID {language_id}"
    else:
        language_id, language_label = resolve_language(
            client, customer_id, args.language
        )

    if args.location_ids:
        location_ids = list(args.location_ids)
        location_labels = [f"geo ID {location_id}" for location_id in location_ids]
    else:
        location_ids = []
        location_labels = []
        for country in args.countries:
            location_id, label = resolve_country(client, customer_id, country)
            location_ids.append(location_id)
            location_labels.append(label)

    return ResolvedTargeting(
        language_id=language_id,
        language_label=language_label,
        location_ids=location_ids,
        location_labels=location_labels,
    )


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


def parse_args() -> argparse.Namespace:
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
    parser.add_argument(
        "--country",
        dest="countries",
        type=parse_csv,
        default=None,
        help="Comma-separated country names or ISO-2 codes, for example VN or 'Vietnam,Thailand'.",
    )
    parser.add_argument(
        "--language",
        help="Language name or ISO code, for example vi or Vietnamese.",
    )
    parser.add_argument(
        "--language-id",
        default=None,
        help="Language constant ID. Overrides --language.",
    )
    parser.add_argument(
        "--location-ids",
        default=None,
        type=parse_csv,
        help="Comma-separated geo target constant IDs. Overrides --country.",
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
    args.customer_id = normalize_customer_id(args.customer_id)

    if not args.language and not args.language_id:
        parser.error("Provide --language (name or code) or --language-id.")
    if not args.countries and not args.location_ids:
        parser.error("Provide --country (name or ISO-2 code) or --location-ids.")
    return args


def main() -> int:
    args = parse_args()

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
        targeting = resolve_targeting(client, args)
        args.language_id = targeting.language_id
        args.location_ids = targeting.location_ids
        print(targeting.summary(), file=sys.stderr)
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
