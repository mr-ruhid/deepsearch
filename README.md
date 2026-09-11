# RJ DEEP SEARCH - Light Crawler

A lightweight, asynchronous web crawler built for low-resource systems.
Combines **SearXNG metasearch**, **Common Crawl index**, and **custom platform crawling** to discover useful resources, score them by keyword relevance, and export results to JSON.

---

## Features

- **Async crawling** with `aiohttp` and `selectolax` (no heavy browsers)
- **Three search modes**:
  - Pre-defined platforms (GitHub, Stack Overflow, Reddit, etc.)
  - Common Crawl index
  - SearXNG local metasearch (Google, Bing, DuckDuckGo aggregated)
- **SQLite storage** — no server required, runs on disk
- **Keyword-based scoring** to filter out junk and keep useful resources
- **JSON export** grouped per search session with an `is_new` flag for new links
- **Auto Docker management** for SearXNG (starts container automatically)
- **Resource-friendly** — only HTML is fetched, all images/CSS/JS are blocked
- **Repeat search without restart** — run multiple queries in one session

---

## Requirements

- Python 3.10+
- Docker Desktop (only for SearXNG mode)
- Windows / Linux / macOS

---

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/deepsearch.git
cd deepsearch

# Install dependencies
pip install aiohttp selectolax aiosqlite
```

---

## Usage

```bash
python main.py
```

You will be prompted to choose a mode:

```
Choose a mode:
1. Crawl a pre-defined platform
2. Search Common Crawl index
3. Search via SearXNG (local metasearch)
q. Quit
```

### Mode 1 — Platform Crawl

Select from GitHub, Stack Overflow, Reddit, Hacker News, Dev.to, Medium.
The crawler starts from seed URLs and follows links up to `MAX_DEPTH`.

### Mode 2 — Common Crawl

Enter a keyword and optional domain filter.
Fetches URLs from the Common Crawl index and crawls them.

### Mode 3 — SearXNG (recommended)

Enter a keyword (e.g., `free course`), set a result limit and page count.
SearXNG aggregates results from multiple search engines.
The Docker container is started automatically if it is not running.

After each search, results can be exported to the `exports/` folder as JSON.

---

## Project Structure

```
deepsearch/
├── main.py              # Entry point & user interface
├── config.py             # Configuration (timeout, depth, score threshold, etc.)
├── platforms.py          # Pre-defined platforms with seed URLs
├── crawler.py             # Core crawling logic
├── database.py            # SQLite storage & search session tracking
├── searxng_search.py      # SearXNG integration + Docker management
├── common_crawl.py        # Common Crawl index integration
├── exporter.py            # JSON export
├── exports/                # Generated JSON files
└── crawler.db              # Local SQLite database (auto-created)
```

---

## JSON Output Format

```json
[
  {
    "id": "a1b2c3d4e5f6...",
    "title": "Free Python Course",
    "description": "A complete beginner-friendly Python course.",
    "url": "https://example.com/free-python-course",
    "image_url": "https://example.com/thumb.png",
    "tags": ["free course", "python"],
    "is_new": true
  }
]
```

- `is_new: true` → link was discovered for the first time
- `is_new: false` → link already existed in the database from a previous search

---

## Configuration (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `REQUEST_TIMEOUT` | `5` | Seconds per HTTP request |
| `MAX_CONCURRENT` | `5` | Simultaneous connections |
| `MAX_DEPTH` | `2` | Crawl depth from seed URLs |
| `SCORE_THRESHOLD` | `5.0` | Minimum score to keep a page |
| `BLOCKED_EXTENSIONS` | (set) | File types never fetched |
| `ACCEPTED_CONTENT_TYPES` | `text/html` | Only HTML is parsed |
| `DB_PATH` | `crawler.db` | SQLite database file |

---

## SearXNG Setup

SearXNG runs locally in a Docker container. The crawler handles it automatically:

1. Checks if Docker is running
2. Creates the container if missing
3. Starts it if stopped
4. Waits until it's ready

You can also run it manually:

```bash
docker run -d -p 8888:8080 --name searxng searxng/searxng
```

---

## Notes

- Only HTML content is fetched — images, CSS, JS, and videos are blocked for speed and low resource usage.
- All URLs are stored in a local SQLite database (`crawler.db`), never uploaded anywhere.
- `crawler.db` and `exports/` are excluded via `.gitignore`.

---

## License

MIT License — free to use, modify, and distribute.

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## Support the Project

If this project has been useful to you, consider supporting its continued development and maintenance.

<div align="center">

<a href="https://kofe.al/@ruhidjavadoff">
  <img src="https://kofe.al/assets/images/kofeal-logo.svg" height="36" alt="Support on Kofe.al" style="background-color:#ffffff; padding:6px; border-radius:6px;">
</a>
&nbsp;&nbsp;
<a href="https://www.paypal.com/paypalme/ruhidjavadoff">
  <img src="https://img.shields.io/badge/Donate-PayPal-00457C?style=for-the-badge&logo=paypal&logoColor=white" alt="Donate via PayPal" height="36">
</a>

</div>

<br>

| Method | Details |
|---|---|
| Kofe.al | [@ruhidjavadoff](https://kofe.al/@ruhidjavadoff) |
| Çayvoy | [ruhid4715](https://cayvoy.com/donate/ruhid4715) |
| PayPal | `ruhidjavadoff@gmail.com` |
| Crypto (USDT — BNB Smart Chain) | `0x9a4AD41762D6B07B8C266b312Cf0dBe31FAd890c` |

Every contribution, regardless of size, directly supports the time invested in maintaining and improving this project.