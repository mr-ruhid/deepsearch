# crawler.py

"""
RJ DEEP SEARCH - Light Crawler
Core crawling module integrated with config and database.
- Fetches only allowed content types (default: only text/html)
- Asynchronous with limited concurrency (semaphore)
- Calculates quality score based on keywords
- Stores results in SQLite database and manages queue
"""

import asyncio
import time
from urllib.parse import urljoin, urlparse

import aiohttp
from selectolax.parser import HTMLParser

import config
from database import Database

# ---- Helper functions ----

def is_valid_url(url):
    """Check if URL is HTTP(S) and not in the blocked extensions list."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        path = parsed.path.lower()
        if any(path.endswith(ext) for ext in config.BLOCKED_EXTENSIONS):
            return False
        return True
    except:
        return False


def extract_text_and_links(html, base_url):
    """
    Parse HTML with selectolax.
    Returns a tuple: (plain_text, set_of_absolute_links)
    """
    parser = HTMLParser(html)
    text = parser.text(separator=' ')        # all visible text
    links = set()
    for node in parser.css('a[href]'):
        href = node.attributes.get('href')
        if href:
            absolute = urljoin(base_url, href)
            if is_valid_url(absolute):
                links.add(absolute)
    return text, links


def calculate_score(text, keywords):
    """
    Simple heuristic score based on keyword density.
    Returns a float between 0 and 100.
    """
    if not text:
        return 0.0
    text_lower = text.lower()
    total_words = len(text_lower.split())
    if total_words == 0:
        return 0.0
    hits = sum(text_lower.count(kw.lower()) for kw in keywords)
    density = hits / total_words
    score = min(100.0, density * 1000)   # scale factor
    return round(score, 2)


# ---- Crawling functions ----

async def fetch_page(session, url, semaphore):
    """
    Fetch a single URL.
    Returns HTML text if the response is successful and content type is accepted.
    """
    async with semaphore:
        try:
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    return None
                content_type = response.headers.get('Content-Type', '')
                # If ACCEPTED_CONTENT_TYPES is empty, default to only 'text/html'
                accepted = config.ACCEPTED_CONTENT_TYPES if config.ACCEPTED_CONTENT_TYPES else ["text/html"]
                if any(ct in content_type for ct in accepted):
                    if 'text/html' in content_type:
                        return await response.text()
                    # For other accepted types, we could handle differently,
                    # but for now we return None because we only parse HTML.
                    # In future we might store binary data or plain text.
                    else:
                        return None
                else:
                    return None
        except (asyncio.TimeoutError, aiohttp.ClientError):
            return None
        except Exception:
            return None


async def process_url(session, url, depth, keywords, db, semaphore):
    """
    Process one URL: fetch, extract text/links, compute score.
    Stores the result in the database.
    Returns a list of (new_url, new_depth) to add to the queue.
    """
    html = await fetch_page(session, url, semaphore)
    if html is None:
        await db.mark_failed(url)
        return []

    text, links = extract_text_and_links(html, url)
    score = calculate_score(text, keywords)

    # Store the processed result
    await db.mark_processed(url, score)

    # If depth limit not reached, return new links with increased depth
    if depth < config.MAX_DEPTH:
        return [(link, depth + 1) for link in links]
    return []


async def crawl_platform(platform):
    """
    Crawl starting from the platform's seed URLs.
    Uses database for queue and result storage.
    """
    keywords = platform.get("keywords", [])
    seed_urls = platform.get("seed_urls", [])

    # Initialize database
    db = Database(config.DB_PATH)
    await db.connect()

    # Seed initial URLs
    for seed in seed_urls:
        if is_valid_url(seed):
            await db.add_to_queue(seed, depth=0)

    # Create aiohttp session
    headers = {"User-Agent": config.USER_AGENT}
    connector = aiohttp.TCPConnector(limit=0, ssl=False)   # no connection limit
    timeout = aiohttp.ClientTimeout(total=config.REQUEST_TIMEOUT)
    semaphore = asyncio.Semaphore(config.MAX_CONCURRENT)

    async with aiohttp.ClientSession(headers=headers,
                                     connector=connector,
                                     timeout=timeout) as session:

        # Main crawling loop
        while True:
            # Get next URL from database queue
            item = await db.get_next_from_queue()
            if item is None:
                break
            url, depth = item

            # Process this URL
            new_links = await process_url(session, url, depth, keywords, db, semaphore)

            # Add new links to database queue
            for new_url, new_depth in new_links:
                if is_valid_url(new_url):
                    await db.add_to_queue(new_url, new_depth)

            # Optional progress
            print(f"Processed: {url} (depth={depth})")

    # Print top results
    print("\n--- Top Results ---")
    top = await db.get_top_results(limit=10, min_score=config.SCORE_THRESHOLD)
    for row in top:
        print(f"{row[0]} | Score: {row[1]} | Depth: {row[2]}")

    stats = await db.get_stats()
    print("\n--- Crawl Statistics ---")
    print(f"Total URLs seen: {stats['total_urls']}")
    print(f"Processed successfully: {stats['processed']}")
    print(f"Remaining in queue: {stats['in_queue']}")

    await db.close()