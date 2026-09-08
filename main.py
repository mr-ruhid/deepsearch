# main.py

"""
RJ DEEP SEARCH - Light Crawler
Main entry point with three modes:
1. Crawl a pre-defined platform.
2. Search Common Crawl index.
3. Search via SearXNG (local metasearch, uses Docker).

In SearXNG mode, results are saved directly to the database with metadata,
including the search term used for later JSON export.
"""

import asyncio
import config
import platforms
from crawler import crawl_platform
from common_crawl import search_cc_index
from searxng_search import search_searxng, ensure_searxng_running
from database import Database


def print_banner():
    """Print ASCII banner."""
    banner = r"""
██████╗      ██╗    ██████╗ ███████╗███████╗██████╗ 
██╔══██╗     ██║    ██╔══██╗██╔════╝██╔════╝██╔══██╗
██████╔╝     ██║    ██║  ██║█████╗  █████╗  ██████╔╝
██╔══██╗██   ██║    ██║  ██║██╔══╝  ██╔══╝  ██╔═══╝ 
██║  ██║╚█████╔╝    ██████╔╝███████╗███████╗██║     
╚═╝  ╚═╝ ╚════╝     ╚═════╝ ╚══════╝╚══════╝╚═╝     
"""
    print(banner)
    print("Lightweight and deep web crawler")
    print("=" * 60)


def choose_platform():
    """Ask user to choose a pre-defined platform."""
    platforms.list_platforms()
    print()
    while True:
        try:
            choice = input("Enter the number of the platform to search (or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(platforms.PLATFORMS):
                return platforms.PLATFORMS[idx]
            else:
                print("Invalid number! Try again.")
        except ValueError:
            print("Please enter a number.")


def choose_mode():
    """Ask user which search mode to use."""
    print("Choose a mode:")
    print("1. Crawl a pre-defined platform")
    print("2. Search Common Crawl index")
    print("3. Search via SearXNG (local metasearch)")
    print("q. Quit")
    choice = input("> ").strip().lower()
    if choice == '1':
        return 'platform'
    elif choice == '2':
        return 'commoncrawl'
    elif choice == '3':
        return 'searxng'
    elif choice == 'q':
        return 'quit'
    else:
        print("Invalid choice.")
        return choose_mode()


def get_common_crawl_settings():
    """Get keyword and optional domain from user for Common Crawl."""
    keyword = input("Enter search keyword (e.g., 'awesome list', 'python tutorial'): ").strip()
    if not keyword:
        print("Keyword cannot be empty.")
        return get_common_crawl_settings()
    domain = input("Optional domain filter (e.g., 'github.com', press Enter to skip): ").strip()
    if domain == '':
        domain = None
    return keyword, domain


def ask_crawl_settings():
    """
    Ask user if they want to override default SCORE_THRESHOLD and MAX_DEPTH.
    Modifies config module variables directly.
    """
    print("\nCrawl settings:")
    print(f"Current minimum score threshold: {config.SCORE_THRESHOLD}")
    print(f"Current maximum depth: {config.MAX_DEPTH}")
    change = input("Do you want to change these settings? (y/n): ").strip().lower()
    if change == 'y':
        try:
            new_threshold = input(f"Enter new score threshold (0-100, default {config.SCORE_THRESHOLD}): ").strip()
            if new_threshold:
                config.SCORE_THRESHOLD = float(new_threshold)

            new_depth = input(f"Enter new max depth (0-10, default {config.MAX_DEPTH}): ").strip()
            if new_depth:
                config.MAX_DEPTH = int(new_depth)

            print(f"Settings updated: score threshold = {config.SCORE_THRESHOLD}, max depth = {config.MAX_DEPTH}")
        except ValueError:
            print("Invalid input. Keeping previous settings.")


async def save_searxng_results_to_db(keyword, results):
    """
    Save SearXNG results directly to the database.
    Each result already contains url, title, description, possibly image_url.
    We'll compute a simple score based on keyword presence in title/description.
    The search_term is stored for later JSON export and categorization.
    """
    db = Database()
    await db.connect()
    saved_count = 0
    for r in results:
        url = r.get('url')
        title = r.get('title') or ''
        description = r.get('description') or ''
        image_url = r.get('img_src') or r.get('image') or None

        # Simple scoring: count keyword occurrences in title + description
        text = (title + ' ' + description).lower()
        keyword_lower = keyword.lower()
        hits = text.count(keyword_lower)
        score = min(100.0, hits * 20.0)  # heuristic

        # Basic tag = keyword
        tags = [keyword_lower]

        await db.add_result(
            url=url,
            title=title,
            description=description,
            image_url=image_url,
            tags=tags,
            score=score,
            depth=0,
            search_term=keyword_lower   # store the original keyword
        )
        saved_count += 1

    await db.close()
    print(f"\n[✓] {saved_count} results saved to database.")
    return saved_count


async def main():
    print_banner()
    mode = choose_mode()
    if mode == 'quit':
        print("Program stopped.")
        return

    if mode == 'platform' or mode == 'commoncrawl':
        # Ask for crawl settings only for these modes
        ask_crawl_settings()

    if mode == 'platform':
        selected = choose_platform()
        if selected is None:
            print("Program stopped.")
            return

        print(f"\nSelected platform: {selected['name']}")
        print(f"Description: {selected['description']}")
        print(f"Seed URLs: {', '.join(selected['seed_urls'])}")
        print("\nStarting crawl...\n")
        await crawl_platform(selected)

    elif mode == 'commoncrawl':
        keyword, domain = get_common_crawl_settings()
        print(f"\nSearching Common Crawl for '{keyword}'...")
        urls = await search_cc_index(keyword, domain, limit=100)
        if not urls:
            print("No URLs found from Common Crawl.")
            return

        print(f"Found {len(urls)} URLs. Starting crawl...\n")
        temp_platform = {
            "name": "Common Crawl",
            "description": f"Search results for '{keyword}'",
            "seed_urls": urls,
            "keywords": [keyword.lower()]
        }
        await crawl_platform(temp_platform)

    elif mode == 'searxng':
        # Ensure local SearXNG is running (Docker)
        print("Checking SearXNG availability...")
        if not ensure_searxng_running():
            print("SearXNG is not available. Please check Docker or start it manually.")
            return

        keyword = input("Enter search keyword: ").strip()
        if not keyword:
            print("Keyword cannot be empty.")
            return

        print(f"\nSearching via local SearXNG for '{keyword}'...")
        results = await search_searxng(keyword, limit=50)
        if not results:
            print("No results from SearXNG.")
            return

        # Save directly to database with search term
        await save_searxng_results_to_db(keyword, results)

    print("\nProcess finished.")


if __name__ == "__main__":
    asyncio.run(main())