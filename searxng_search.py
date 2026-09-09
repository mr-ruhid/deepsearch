# searxng_search.py

"""
RJ DEEP SEARCH - Light Crawler
SearXNG metasearch engine integration with Docker management.

This version fetches the HTML results page instead of JSON.
HTML is parsed with selectolax to extract results.
Image URLs are converted to absolute URLs and stripped of localhost proxy.
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
    code, _, _ = _run_command("docker --version")
    if code != 0:
        print("[!] Docker is not installed or not in PATH.")
        print("    Please install Docker Desktop and start it, then run this program again.")
        return False

    code, _, _ = _run_command("docker info")
    if code != 0:
        print("[!] Docker daemon is not running. Please start Docker Desktop.")
        return False

    code, stdout, _ = _run_command(f"docker ps -a --filter name=^{CONTAINER_NAME}$ --format {{{{.Names}}}}")
    container_exists = (code == 0 and CONTAINER_NAME in stdout)

    if not container_exists:
        print(f"[i] SearXNG container not found. Creating it from image {IMAGE_NAME}...")
        code, _, stderr = _run_command(f"docker run -d -p {PORT_MAPPING} --name {CONTAINER_NAME} {IMAGE_NAME}")
        if code != 0:
            print(f"[!] Failed to create container: {stderr}")
            return False
    else:
        code, stdout, _ = _run_command(f"docker ps --filter name=^{CONTAINER_NAME}$ --format {{{{.Names}}}}")
        if CONTAINER_NAME not in stdout:
            print(f"[i] Starting existing SearXNG container...")
            code, _, stderr = _run_command(f"docker start {CONTAINER_NAME}")
            if code != 0:
                print(f"[!] Failed to start container: {stderr}")
                return False

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


def _extract_original_image_url(raw_src):
    """
    If the source is a SearXNG image proxy, extract the original URL from its 'url' query parameter.
    Otherwise return the source as is.
    """
    if not raw_src:
        return None

    # Check if it's an image_proxy link
    if '/image_proxy' in raw_src:
        parsed = urlparse(raw_src)
        params = parse_qs(parsed.query)
        if 'url' in params and params['url']:
            # URL may be double-encoded
            original = params['url'][0]
            # Decode percent encoding
            original = unquote(original)
            return original
        else:
            return raw_src
    else:
        return raw_src


async def search_searxng(query, limit=50):
    """
    Search using local SearXNG instance (HTML output).
    Returns a list of dicts with keys: 'url', 'title', 'description', 'img_src'.
    """
    params = {
        "q": query,
        "categories": "general",
        "language": "en",
        "safesearch": 0,
    }
    headers = {"User-Agent": USER_AGENT}
    results = []

    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            async with session.get(SEARXNG_URL, params=params, timeout=15) as response:
                if response.status != 200:
                    print(f"SearXNG error: HTTP {response.status}")
                    return results
                html = await response.text()
        except Exception as e:
            print(f"Error querying SearXNG: {e}")
            return results

    parser = HTMLParser(html)
    for article in parser.css('article.result, div.result, .result'):
        title_tag = article.css_first('h3 a')
        if not title_tag:
            continue

        title = title_tag.text(strip=True)
        raw_url = title_tag.attributes.get('href')
        if not raw_url:
            continue

        url = urljoin(SEARXNG_BASE, raw_url)

        desc_tag = article.css_first('p.content, .content, p')
        description = desc_tag.text(strip=True) if desc_tag else ""

        img_tag = article.css_first('img')
        raw_img_src = img_tag.attributes.get('src') if img_tag else None
        img_src = _extract_original_image_url(raw_img_src)
        # Ensure absolute URL if still relative
        if img_src:
            img_src = urljoin(SEARXNG_BASE, img_src)

        results.append({
            'url': url,
            'title': title,
            'description': description,
            'img_src': img_src
        })
        if len(results) >= limit:
            break

    return results