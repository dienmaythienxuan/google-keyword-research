# Google Ads Keyword Planning Notes

Use this reference when adapting the script, debugging requests, or explaining Google Ads API keyword-planning behavior.

Source: https://developers.google.com/google-ads/api/docs/keyword-planning/generate-keyword-ideas

## GenerateKeywordIdeas

`KeywordPlanIdeaService.GenerateKeywordIdeas` returns keyword ideas relevant to Google Search campaigns and includes historical metrics such as average monthly searches and competition.

No `KeywordPlan` resource is required to call this method. Results can be used later to build a keyword plan.

## Seeds

The request must set one seed path:

- `keyword_seed` for words or phrases describing the product, service, or business.
- `url_seed` for a specific page URL. If no results are found, Google may broaden to pages from the same domain.
- `keyword_and_url_seed` for keywords plus a URL.
- `site_seed` for a whole site/domain from public content.

`url_seed`, `keyword_seed`, and `keyword_and_url_seed` are mutually exclusive. Treat `site_seed` as its own mode as well.

## Targeting

Use these request fields to narrow results:

- `language`
- `geo_target_constants`
- `keyword_plan_network`
- `include_adult_keywords`
- `keyword_annotation`
- `historical_metrics_options`

Pass `--country` and `--language` to `scripts/generate_keyword_ideas.py`. The script resolves them to Google Ads IDs before calling `GenerateKeywordIdeas`:

- Country: ISO-2 code (`VN`, `US`, `TH`) via `geo_target_constant` search, or English name via `GeoTargetConstantService.SuggestGeoTargetConstants`.
- Language: ISO code (`vi`, `en`, `th`) or English name via `language_constant` search.

`--language-id` and `--location-ids` skip lookup and send resource IDs directly.

Do not hardcode Vietnam/Vietnamese or US/English. Official language criterion IDs: https://developers.google.com/google-ads/api/data/codes-formats#languages

The response supports pagination through the Google Ads client library.
