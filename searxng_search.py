# searxng_search.py

"""
RJ DEEP SEARCH - Light Crawler
SearXNG metasearch engine integration with Docker management.

This module provides:
- ensure_searxng_running(): automatically checks and starts the SearXNG Docker container.
- search_searxng(): sends a query to local SearXNG and returns results.
"""

import asyncio
import subprocess
import time
import sys

import aiohttp

# Configuration
SEARXNG_URL = "http://localhost:8888/search"
CONTAINER_NAME = "searxng"
IMAGE_NAME = "searxng/searxng"
PORT_MAPPING = "8888:8080"

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
    Check if Docker is running, if the SearXNG container exists and is started.
    If not, it tries to start/create it.
    Returns True if SearXNG is ready, False otherwise.
    """
    # 1. Check Docker availability
    code, _, _ = _run_command("docker --version")
    if code != 0:
        print("[!] Docker is not installed or not in PATH.")
        print("    Please install Docker Desktop and start it, then run this program again.")
        print("    You may need to run this script as Administrator.")
        return False

    # 2. Check if Docker daemon is running
    code, _, _ = _run_command("docker info")
    if code != 0:
        print("[!] Docker daemon is not running. Starting Docker Desktop...")
        # Try to start Docker Desktop (Windows)
        if sys.platform.startswith("win"):
            _run_command('start "" "C:\\Program Files\\Docker\\Docker\\Docker Desktop.exe"')
            # Wait for Docker daemon to be ready
            for _ in range(30):
                time.sleep(2)
                code, _, _ = _run_command("docker info")
                if code == 0:
                    break
            if code != 0:
                print("[!] Failed to start Docker automatically.")
                print("    Please start Docker Desktop manually and re-run.")
                return False
        else:
            print("[!] Please start Docker daemon manually.")
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
    for _ in range(20):
        try:
            # Simple HTTP request to the main page
            code, _, _ = _run_command(f"curl -s -o NUL -w \"%{{http_code}}\" {SEARXNG_URL.replace('/search', '')}")
            if code == 0:
                # curl exit code 0 means success
                return True
        except:
            pass
        time.sleep(1)
    print("[!] SearXNG did not become ready in time.")
    return False

async def search_searxng(query, limit=50):
    """
    Search using local SearXNG instance.

    Parameters:
        query : search term
        limit : max number of results

    Returns:
        list of dicts with keys: 'url', 'title', 'description'
    """
    params = {
        "q": query,
        "format": "json",
        "pageno": 1,
        "categories": "general",
        "language": "en",
        "safesearch": 0,
    }
    results = []
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(SEARXNG_URL, params=params, timeout=15) as response:
                if response.status != 200:
                    print(f"SearXNG error: HTTP {response.status}")
                    return results
                data = await response.json()
                for item in data.get("results", []):
                    result = {
                        "url": item.get("url"),
                        "title": item.get("title"),
                        "description": item.get("content", "")
                    }
                    results.append(result)
                    if len(results) >= limit:
                        break
        except Exception as e:
            print(f"Error querying SearXNG: {e}")
    return results