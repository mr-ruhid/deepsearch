# cleanup.py

"""
RJ DEEP SEARCH - Light Crawler
Database cleanup utility.

Provides options to:
1. Wipe the entire database (urls, search_results, queue).
2. Clear only search_results (keeps urls, useful for re-exporting).
3. Delete results for a specific search_id.
4. Delete results for a specific search_term (keyword).
5. Show current database statistics.

Run directly:  python cleanup.py
Called from main.py as a submenu.
"""

import asyncio
import aiosqlite
import config


DB_PATH = getattr(config, "DB_PATH", "crawler.db")


async def show_stats():
    """Print current database statistics."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute("SELECT COUNT(*) FROM urls") as cur:
            total_urls = (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM search_results") as cur:
            total_sr = (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(DISTINCT search_id) FROM search_results") as cur:
            total_sessions = (await cur.fetchone())[0]
        async with conn.execute("SELECT COUNT(*) FROM queue") as cur:
            in_queue = (await cur.fetchone())[0]

    print("\n--- Database statistics ---")
    print(f"Total URLs          : {total_urls}")
    print(f"Search results rows : {total_sr}")
    print(f"Unique search IDs   : {total_sessions}")
    print(f"URLs in queue       : {in_queue}")
    print("--------------------------\n")


async def wipe_all():
    """Delete all data from urls, search_results, and queue tables."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM search_results")
        await conn.execute("DELETE FROM urls")
        await conn.execute("DELETE FROM queue")
        await conn.commit()
        await conn.execute("VACUUM")
        await conn.commit()
    print("[✓] Entire database wiped (urls, search_results, queue).")


async def clear_search_results():
    """Clear only the search_results table (keeps urls intact)."""
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute("DELETE FROM search_results")
        await conn.commit()
        await conn.execute("VACUUM")
        await conn.commit()
    print("[✓] search_results table cleared. URLs are kept.")


async def delete_by_search_id(search_id):
    """Delete all results for a specific search_id."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "DELETE FROM search_results WHERE search_id = ?", (search_id,)
        )
        await conn.commit()
        deleted = cursor.rowcount
        await conn.execute(
            """
            DELETE FROM urls
            WHERE url NOT IN (SELECT DISTINCT url FROM search_results)
            """
        )
        await conn.commit()
        await conn.execute("VACUUM")
        await conn.commit()
    print(f"[✓] Deleted {deleted} rows for search_id = '{search_id}'.")


async def delete_by_search_term(search_term):
    """Delete all results for a specific search_term (keyword)."""
    async with aiosqlite.connect(DB_PATH) as conn:
        cursor = await conn.execute(
            "DELETE FROM search_results WHERE search_id IN ("
            "  SELECT DISTINCT search_id FROM search_results sr "
            "  JOIN urls u ON u.url = sr.url WHERE u.search_term = ?"
            ")",
            (search_term,)
        )
        await conn.commit()
        deleted = cursor.rowcount
        await conn.execute(
            "DELETE FROM urls WHERE search_term = ? AND url NOT IN "
            "(SELECT DISTINCT url FROM search_results)",
            (search_term,)
        )
        await conn.commit()
        await conn.execute("VACUUM")
        await conn.commit()
    print(f"[✓] Deleted {deleted} rows for search_term = '{search_term}'.")


async def list_search_ids():
    """Print all search IDs with their search terms."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            """
            SELECT DISTINCT sr.search_id, u.search_term, COUNT(sr.url)
            FROM search_results sr
            JOIN urls u ON u.url = sr.url
            GROUP BY sr.search_id
            ORDER BY sr.search_id DESC
            """
        ) as cur:
            rows = await cur.fetchall()

    if not rows:
        print("No search sessions found.")
        return

    print("\n--- Search sessions ---")
    for sid, term, count in rows:
        print(f"  {sid} | {term} | {count} URLs")
    print()


async def interactive_menu():
    """
    Interactive cleanup menu.

    Returns:
        True  — user chose to go back to main menu
        False — user chose to quit entirely
    """
    while True:
        print("\n=== RJ DEEP SEARCH - Cleanup Menu ===")
        print("1. Show database statistics")
        print("2. List all search sessions")
        print("3. Clear entire database (urls + search_results + queue)")
        print("4. Clear only search_results (keep URLs, useful before re-searching)")
        print("5. Delete results by search_id")
        print("6. Delete results by search_term")
        print("b. Back to main menu")
        print("q. Quit program")
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
        elif choice == 'b':
            return True   # back to main menu
        elif choice == 'q':
            return False  # quit program
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    # When run directly, quitting ends the program
    result = asyncio.run(interactive_menu())
    # If user chose 'b' (back), but there is no main menu, just exit