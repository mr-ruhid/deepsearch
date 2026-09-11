# main.py

"""
RJ DEEP SEARCH - Light Crawler
Main entry point with four modes:
1. Crawl a pre-defined platform.
2. Search Common Crawl index.
3. Search via SearXNG (local metasearch, uses Docker).
4. Database cleanup.

After each search, the user can export results to JSON and choose to run
another search in the same mode without restarting the program.
"""

import asyncio
from datetime import datetime
import config
import platforms
from crawler import crawl_platform
from common_crawl import search_cc_index
from searxng_search import search_searxng, ensure_searxng_running
from database import Database
from exporter import export_all
from cleanup import (
    show_stats,
    wipe_all,
    clear_search_results,
    delete_by_search_id,
    delete_by_search_term,
    list_search_ids,
)


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
    print("4. Database cleanup")
    print("q. Quit")
    choice = input("> ").strip().lower()
    if choice == '1':
        return 'platform'
    elif choice == '2':
        return 'commoncrawl'
    elif choice == '3':
        return 'searxng'
    elif choice == '4':
        return 'cleanup'
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


async def save_searxng_results_to_db(keyword, results, search_id):
    """
    Save SearXNG results directly to the database.
    Each result already contains url, title, description, possibly image_url.
    We compute a simple score based on keyword presence in title/description.
    The search_term and search_id are stored for later JSON export.
    """
    db = Database()
    await db.connect()
    saved_count = 0
    for r in results:
        url = r.get('url')
        title = r.get('title') or ''
        description = r.get('description') or ''
        image_url = r.get('img_src') or r.get('image') or None

        text = (title + ' ' + description).lower()
        keyword_lower = keyword.lower()
        hits = text.count(keyword_lower)
        score = min(100.0, hits * 20.0)

        tags = [keyword_lower]

        await db.add_result(
            url=url,
            title=title,
            description=description,
            image_url=image_url,
            tags=tags,
            score=score,
            depth=0,
            search_term=keyword_lower,
            search_id=search_id
        )
        saved_count += 1

    await db.close()
    print(f"\n[✓] {saved_count} results saved to database.")
    return saved_count


async def run_searxng_mode():
    """Run SearXNG search mode with loop for multiple searches."""
    print("Checking SearXNG availability...")
    if not ensure_searxng_running():
        print("SearXNG is not available. Please check Docker or start it manually.")
        return

    while True:
        keyword = input("\nEnter search keyword (or 'q' to quit): ").strip()
        if keyword.lower() == 'q':
            break
        if not keyword:
            print("Keyword cannot be empty.")
            continue

        try:
            limit = int(input("How many results max? (default 50): ").strip() or "50")
            max_pages = int(input("How many pages to search? (default 3): ").strip() or "3")
        except ValueError:
            print("Invalid input, using defaults (limit=50, pages=3).")
            limit, max_pages = 50, 3

        search_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        print(f"\nSearching via local SearXNG for '{keyword}' (limit={limit}, pages={max_pages})...")
        results = await search_searxng(keyword, limit=limit, max_pages=max_pages)
        if not results:
            print("No results from SearXNG.")
        else:
            await save_searxng_results_to_db(keyword, results, search_id)

            export_choice = input("Do you want to export results to JSON? (y/n): ").strip().lower()
            if export_choice == 'y':
                await export_all()

        again = input("\nDo you want to run another search in SearXNG mode? (Enter/y - yes, q - quit): ").strip().lower()
        if again == 'q':
            break


async def run_platform_mode():
    """Run platform crawl mode with loop for multiple crawls."""
    ask_crawl_settings()
    while True:
        selected = choose_platform()
        if selected is None:
            break

        print(f"\nSelected platform: {selected['name']}")
        print(f"Description: {selected['description']}")
        print(f"Seed URLs: {', '.join(selected['seed_urls'])}")
        print("\nStarting crawl...\n")
        await crawl_platform(selected)

        export_choice = input("Do you want to export results to JSON? (y/n): ").strip().lower()
        if export_choice == 'y':
            await export_all()

        again = input("\nDo you want to crawl another platform? (Enter/y - yes, q - quit): ").strip().lower()
        if again == 'q':
            break


async def run_commoncrawl_mode():
    """Run Common Crawl mode with loop for multiple searches."""
    ask_crawl_settings()
    while True:
        keyword, domain = get_common_crawl_settings()
        print(f"\nSearching Common Crawl for '{keyword}'...")
        urls = await search_cc_index(keyword, domain, limit=100)
        if not urls:
            print("No URLs found from Common Crawl.")
        else:
            print(f"Found {len(urls)} URLs. Starting crawl...\n")
            temp_platform = {
                "name": "Common Crawl",
                "description": f"Search results for '{keyword}'",
                "seed_urls": urls,
                "keywords": [keyword.lower()]
            }
            await crawl_platform(temp_platform)

            export_choice = input("Do you want to export results to JSON? (y/n): ").strip().lower()
            if export_choice == 'y':
                await export_all()

        again = input("\nDo you want to run another Common Crawl search? (Enter/y - yes, q - quit): ").strip().lower()
        if again == 'q':
            break


async def run_cleanup_mode():
    """Interactive cleanup submenu."""
    while True:
        print("\n=== Database Cleanup ===")
        print("1. Show database statistics")
        print("2. List all search sessions")
        print("3. Clear entire database (urls + search_results + queue)")
        print("4. Clear only search_results (keep URLs, useful before re-searching)")
        print("5. Delete results by search_id")
        print("6. Delete results by search_term")
        print("q. Back to main menu")
        choice = input("> ").strip().lower()

        if choice == '1':
            await show_stats()
        elif choice == '2':
            await list_search_ids()
        elif choice == '3':
            confirm = input("Are you sure? This will erase ALL data. (y/n): ").strip().lower()
            if confirm == 'y':
                await wipe_all()
        elif choice == '4':
            confirm = input("Clear search_results table? URLs will be kept. (y/n): ").strip().lower()
            if confirm == 'y':
                await clear_search_results()
        elif choice == '5':
            await list_search_ids()
            sid = input("Enter search_id to delete (or Enter to cancel): ").strip()
            if sid:
                await delete_by_search_id(sid)
        elif choice == '6':
            term = input("Enter search_term (keyword) to delete (or Enter to cancel): ").strip()
            if term:
                await delete_by_search_term(term)
        elif choice == 'q':
            break
        else:
            print("Invalid choice.")


async def main():
    print_banner()
    mode = choose_mode()
    if mode == 'quit':
        print("Program stopped.")
        return

    if mode == 'platform':
        await run_platform_mode()
    elif mode == 'commoncrawl':
        await run_commoncrawl_mode()
    elif mode == 'searxng':
        await run_searxng_mode()
    elif mode == 'cleanup':
        await run_cleanup_mode()

    print("\nProgram finished.")


if __name__ == "__main__":
    asyncio.run(main())