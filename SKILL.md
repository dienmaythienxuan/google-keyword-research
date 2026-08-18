---
name: google-keyword-research
description: Research keyword ideas, search volume, competition, and keyword-planning metrics with the Google Ads API KeywordPlanIdeaService. Use for Google Ads keyword research, SEO/SEM keyword discovery, Keyword Planner-style keyword ideas, or generating keyword CSV/JSON reports from seed keywords, URLs, countries, languages, and Google Search network settings.
---

# Google Keyword Research

Use Google Ads API `KeywordPlanIdeaService.GenerateKeywordIdeas` to get keyword ideas and historical metrics. Do not invent search volume, CPC, or competition data; if credentials or API access are unavailable, explain what is missing and provide a request template the user can run later.

Official reference: https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas

Skill API notes: `references/google-ads-keyword-planning.md`

## Workflow

1. Collect inputs: customer ID, seed keywords and/or URL/site, **country**, **language**, network, adult keyword setting, and desired output format.
2. Confirm Google Ads API credentials are available. Prefer `GOOGLE_ADS_CONFIGURATION_FILE_PATH`; otherwise use `google-ads.yaml` next to this skill. Do not paste secrets into prompts or generated reports.
3. Use `scripts/generate_keyword_ideas.py` for repeatable API calls and CSV/JSON output. Prefer writing outputs under `keyword-research/` when working from this repo.
4. Summarize results by intent clusters, demand, competition, and notable gaps. Keep raw metrics attached or saved when the user needs auditability.
5. Mention the resolved country/language targeting, plus any limits or missing inputs.

## Seed Selection

Use exactly one request seed type:

- Keywords only: use `KeywordSeed`.
- URL only: use `UrlSeed`.
- Keywords plus URL: use `KeywordAndUrlSeed`; prefer this when the user provides both because it can produce more ideas than URL alone.
- Whole site/domain: use `SiteSeed` when the user asks to research an entire domain from public site content.

At least one seed keyword, URL, or site is required. URL seed ignores hyperlink text on the page. For a top-level domain/site seed, expect large result sets and apply `--limit`.

## Country and Language

Always pass country and language. Do not assume Vietnam, Vietnamese, US, or English.

If the user does not specify them, ask. Accept human-readable values; the script resolves Google Ads IDs:

- Country: ISO-2 code or English name, for example `VN`, `Vietnam`, `US`, `Thailand`. Comma-separate multiple countries.
- Language: ISO code or English name, for example `vi`, `Vietnamese`, `en`, `English`.

```bash
python scripts/generate_keyword_ideas.py \
  --customer-id 1234567890 \
  --keywords "air conditioner,inverter ac" \
  --country VN \
  --language vi \
  --output keyword-research/keyword-ideas.csv
```

`--language-id` and `--location-ids` override name/code lookup only when the user already has Google Ads resource IDs.

Other targeting defaults:

- Network: `GOOGLE_SEARCH_AND_PARTNERS` unless the user asks for Google Search only.
- Adult keywords: exclude by default.

State the resolved IDs from the script stderr line (`Resolved targeting: ...`) in the summary.

## Script Usage

Resolve paths relative to this skill root (the directory that contains `SKILL.md`):

```bash
python scripts/generate_keyword_ideas.py \
  --customer-id 1234567890 \
  --keywords "máy lạnh,điều hòa inverter" \
  --country VN \
  --language vi \
  --output keyword-research/keyword-ideas.csv
```

The script requires a Google Ads client configuration file with these fields:

```yaml
developer_token: "..."
client_id: "..."
client_secret: "..."
refresh_token: "..."
login_customer_id: "..."
use_proto_plus: true
```

Copy `google-ads.yaml.example` to `google-ads.yaml` and fill credentials. Use `--config /path/to/google-ads.yaml` for an explicit config file. If no path is provided, the script checks `GOOGLE_ADS_CONFIGURATION_FILE_PATH`, `./google-ads.yaml`, and `google-ads.yaml` in this skill root.

If `google.ads.googleads` cannot be imported, install dependencies with:

```bash
python -m pip install -r requirements.txt
```

To obtain a refresh token:

```bash
python scripts/get_refresh_token.py
```

Useful options:

- `--country VN` or `--country "Vietnam,Thailand"` for geo targeting.
- `--language vi` or `--language Vietnamese` for language targeting.
- `--url https://example.com/page` to use a URL seed or combine it with keywords.
- `--site example.com` to use a site seed.
- `--network GOOGLE_SEARCH` to restrict to Google Search.
- `--limit 500` to cap rows.
- `--format json` for JSON output.
- `--include-adult-keywords` only when explicitly appropriate.

## Output Review

Prioritize these fields:

- `keyword`
- `avg_monthly_searches`
- `competition`
- `competition_index`
- `low_top_of_page_bid_micros`
- `high_top_of_page_bid_micros`
- `monthly_search_volumes`

When presenting findings, group keywords into commercial, informational, brand, local, and long-tail themes when useful. Avoid overclaiming precision: historical metrics are directional and depend on Google Ads account access, targeting, and API response availability.
