# Google Keyword Research

Repo nghiên cứu từ khóa SEO/SEM qua Google Ads API (`KeywordPlanIdeaService.GenerateKeywordIdeas`).

## Yêu cầu

- Python 3.10+
- Tài khoản Google Ads có quyền Keyword Planner / API
- File cấu hình `google-ads.yaml` (không commit lên git)

## Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp google-ads.yaml.example google-ads.yaml
```

Điền credentials vào `google-ads.yaml`, rồi lấy refresh token nếu chưa có:

```bash
python scripts/get_refresh_token.py
```

## Chạy nghiên cứu từ khóa

Truyền quốc gia (`--country`, mã ISO-2 hoặc tên tiếng Anh) và ngôn ngữ (`--language`, mã ISO hoặc tên tiếng Anh). Script tự resolve sang ID Google Ads. Mạng mặc định: `GOOGLE_SEARCH_AND_PARTNERS`.

```bash
python scripts/generate_keyword_ideas.py \
  --customer-id YOUR_CUSTOMER_ID \
  --keywords "quạt điện,quạt cây" \
  --country VN \
  --language vi \
  --output keyword-research/quat-dien.csv
```

Ví dụ thị trường khác:

```bash
python scripts/generate_keyword_ideas.py \
  --customer-id YOUR_CUSTOMER_ID \
  --keywords "air conditioner,inverter ac" \
  --country "United States" \
  --language en \
  --output keyword-research/us-ac.csv
```

Seed theo URL hoặc site:

```bash
python scripts/generate_keyword_ideas.py \
  --customer-id YOUR_CUSTOMER_ID \
  --url https://example.com/quat-dien \
  --country VN \
  --language vi \
  --output keyword-research/from-url.csv

python scripts/generate_keyword_ideas.py \
  --customer-id YOUR_CUSTOMER_ID \
  --site example.com \
  --country VN \
  --language vi \
  --limit 500 \
  --output keyword-research/from-site.csv
```

Kết hợp keyword + URL:

```bash
python scripts/generate_keyword_ideas.py \
  --customer-id YOUR_CUSTOMER_ID \
  --keywords "quạt điều hòa" \
  --url https://example.com/quat-dieu-hoa \
  --country VN \
  --language vi \
  --format json \
  --output keyword-research/combo.json
```

## Cấu trúc (portable skill)

Repo này là một bộ skill trọn vẹn — có thể dùng với bất kỳ agent nào hỗ trợ `SKILL.md`:

```
.
├── SKILL.md
├── agents/
│   └── openai.yaml
├── scripts/
│   ├── generate_keyword_ideas.py
│   └── get_refresh_token.py
├── references/
│   └── google-ads-keyword-planning.md
├── keyword-research/
├── google-ads.yaml.example
├── requirements.txt
└── LICENSE
```

Cài skill vào thư mục skills của agent (symlink hoặc clone), rồi trỏ credentials qua `google-ads.yaml` hoặc `GOOGLE_ADS_CONFIGURATION_FILE_PATH`.

## Bảo mật

- `google-ads.yaml` đã được gitignore — không commit token/secret.
- Không dán credentials vào chat, CSV, hoặc README.
