# searxng_search.py

"""
RJ DEEP SEARCH - Light Crawler
SearXNG metasearch engine integration with Docker management.

This version fetches the HTML results page instead of JSON.
HTML is parsed with selectolax to extract results.
Supports pagination (max_pages) to gather more links.
URLs (both result and image) are stripped of SearXNG proxy/redirect so that
only the original external URL is stored.
"""

import asyncio
import subprocess
import time
import sys
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import aiohttp
from selectolax.parser import HTMLParser

# Configuration
SEARXNG_BASE = "http://localhost:8888"
SEARXNG_URL = f"{SEARXNG_BASE}/search"
CONTAINER_NAME = "searxng"
IMAGE_NAME = "searxng/searxng"
PORT_MAPPING = "8888:8080"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _run_command(cmd):
    """Run a shell command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            check=False
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def ensure_searxng_running():
    """
    Check if Docker is running and the SearXNG container exists and is started.
    Returns True if SearXNG is ready, False otherwise.
    """
    # 1. Check Docker availability
    code, _, _ = _run_command("docker --version")
    if code != 0:
        print("[!] Docker is not installed or not in PATH.")
        print("    Please install Docker Desktop and start it, then run this program again.")
        return False

    # 2. Check if Docker daemon is running
    code, _, _ = _run_command("docker info")
    if code != 0:
        print("[!] Docker daemon is not running. Please start Docker Desktop.")
        return False

    # 3. Check if container exists
    code, stdout, _ = _run_command(f"docker ps -a --filter name=^{CONTAINER_NAME}$ --format {{{{.Names}}}}")
    container_exists = (code == 0 and CONTAINER_NAME in stdout)

    if not container_exists:
        print(f"[i] SearXNG container not found. Creating it from image {IMAGE_NAME}...")
        code, _, stderr = _run_command(f"docker run -d -p {PORT_MAPPING} --name {CONTAINER_NAME} {IMAGE_NAME}")
        if code != 0:
            print(f"[!] Failed to create container: {stderr}")
            return False
    else:
        # 4. Check if container is running
        code, stdout, _ = _run_command(f"docker ps --filter name=^{CONTAINER_NAME}$ --format {{{{.Names}}}}")
        if CONTAINER_NAME not in stdout:
            print(f"[i] Starting existing SearXNG container...")
            code, _, stderr = _run_command(f"docker start {CONTAINER_NAME}")
            if code != 0:
                print(f"[!] Failed to start container: {stderr}")
                return False

    # 5. Wait for SearXNG to be ready
    print("[i] Waiting for SearXNG to become ready...")
    for _ in range(30):
        try:
            import urllib.request
            req = urllib.request.Request(SEARXNG_BASE, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=2) as response:
                if response.status == 200:
                    return True
        except:
            pass
        time.sleep(1)
    print("[!] SearXNG did not become ready in time.")
    return False


def _extract_real_url(raw_url, base=SEARXNG_BASE):
    """
    Extract the original URL from a possible SearXNG proxy/redirect link.
    SearXNG typically wraps external links as:
        /redirect?url=ENCODED_URL
        /url?q=ENCODED_URL
        /image_proxy?url=ENCODED_URL
    If raw_url contains such a pattern, return the decoded original URL.
    Otherwise, return raw_url (joined with base if relative).
    """
    if not raw_url:
        return raw_url

    # If it's a relative path, make absolute first
    absolute = urljoin(base, raw_url)
    parsed = urlparse(absolute)

    # Check path for known proxy endpoints
    if parsed.path in ('/redirect', '/url', '/image_proxy'):
        params = parse_qs(parsed.query)
        if 'url' in params and params['url']:
            original = params['url'][0]
            # May be double-encoded
            original = unquote(original)
            return original
        elif 'q' in params and params['q']:
            original = params['q'][0]
            original = unquote(original)
            return original

    # If no proxy pattern, return the absolute URL
    return absolute


async def search_searxng(query, limit=50, max_pages=3):
    """
    Search using local SearXNG instance (HTML output).
    Supports pagination to gather more results.

    Parameters:
        query     : search term
        limit     : maximum total results to return
        max_pages : number of result pages to crawl (starting from 1)

    Returns:
        list of dicts with keys: 'url', 'title', 'description', 'img_src'
    """
    all_results = []
    seen_urls = set()  # avoid duplicates within this search

    for page in range(1, max_pages + 1):
        params = {
            "q": query,
            "categories": "general",
            "language": "en",
            "safesearch": 0,
            "pageno": page,
        }
        headers = {"User-Agent": USER_AGENT}
        page_results = []

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                async with session.get(SEARXNG_URL, params=params, timeout=15) as response:
                    if response.status != 200:
                        print(f"SearXNG error on page {page}: HTTP {response.status}")
                        break
                    html = await response.text()
            except Exception as e:
                print(f"Error on page {page}: {e}")
                break

        parser = HTMLParser(html)
        for article in parser.css('article.result, div.result, .result'):
            title_tag = article.css_first('h3 a')
            if not title_tag:
                continue

            title = title_tag.text(strip=True)
            raw_url = title_tag.attributes.get('href')
            if not raw_url:
                continue

            url = _extract_real_url(raw_url, SEARXNG_BASE)
            if url in seen_urls:
                continue  # skip duplicates within this search
            seen_urls.add(url)

            desc_tag = article.css_first('p.content, .content, p')
            description = desc_tag.text(strip=True) if desc_tag else ""

            img_tag = article.css_first('img')
            raw_img_src = img_tag.attributes.get('src') if img_tag else None
            img_src = _extract_real_url(raw_img_src, SEARXNG_BASE) if raw_img_src else None

            page_results.append({
                'url': url,
                'title': title,
                'description': description,
                'img_src': img_src
            })

        if not page_results:
            # No more results, stop
            break

        all_results.extend(page_results)
        if len(all_results) >= limit:
            break

    return all_results[:limit]