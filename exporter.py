# exporter.py

"""
RJ DEEP SEARCH - Light Crawler
JSON export module.

Reads processed results from the SQLite database and writes them to JSON files,
organized by search term and search session ID (search_id). Each unique search session
gets its own JSON file, so results from repeated searches with the same keyword do not mix.

Output structure per resource:
{
    "id": unique_string,
    "title": "...",
    "description": "...",
    "url": "...",
    "image_url": "...",
    "tags": ["tag1", "tag2"],
    "is_new": true/false
}
"""

import os
import json
import hashlib
import asyncio
from database import Database

EXPORT_DIR = "exports"


def generate_id(url):
    """Generate a unique ID based on URL hash."""
    return hashlib.md5(url.encode('utf-8')).hexdigest()


def parse_tags(tags_str):
    """
    Convert tags from JSON string (or comma-separated string) to Python list.
    If tags_str is already a list, return it as is.
    """
    if not tags_str:
        return []
    if isinstance(tags_str, list):
        return tags_str
    try:
        # Try to parse as JSON array
        parsed = json.loads(tags_str)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    # Fallback: split by comma
    return [t.strip() for t in tags_str.split(',') if t.strip()]


def build_resource_dict(row):
    """
    Convert a database row (tuple) into a resource dictionary.
    Row order expected:
    (url, score, depth, title, description, image_url, tags, search_term, search_id, is_new)
    """
    url, score, depth, title, description, image_url, tags, search_term, search_id, is_new = row
    return {
        "id": generate_id(url),
        "title": title or "",
        "description": description or "",
        "url": url,
        "image_url": image_url or "",
        "tags": parse_tags(tags),
        "is_new": bool(is_new)   # boolean true/false
        # score, depth, search_term, search_id are intentionally omitted
    }


async def export_all():
    """
    Export all processed results to JSON files.
    Groups by (search_term, search_id) so that each search session is separate.
    """
    db = Database()
    await db.connect()
    rows = await db.get_all_results(min_score=0.0)
    await db.close()

    if not rows:
        print("No results to export.")
        return

    # Group rows by search_term and search_id
    groups = {}
    for row in rows:
        # row = (url, score, depth, title, description, image_url, tags, search_term, search_id, is_new)
        search_term = row[7] if len(row) > 7 and row[7] else "unknown"
        search_id = row[8] if len(row) > 8 and row[8] else "unknown"
        key = (search_term, search_id)

        if key not in groups:
            groups[key] = {
                "search_term": search_term,
                "search_id": search_id,
                "resources": []
            }
        groups[key]["resources"].append(build_resource_dict(row))

    # Create export directory if it doesn't exist
    os.makedirs(EXPORT_DIR, exist_ok=True)

    # Write JSON file for each group
    for (term, sid), group in groups.items():
        # Sanitize filename (remove/replace invalid characters)
        safe_term = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in term)
        safe_term = safe_term.strip().replace(' ', '_').lower()
        if not safe_term:
            safe_term = "results"

        safe_sid = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in sid)
        file_path = os.path.join(EXPORT_DIR, f"{safe_term}_{safe_sid}.json")

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(group["resources"], f, indent=2, ensure_ascii=False)

        print(f"[✓] Exported {len(group['resources'])} resources to {file_path}")

    print(f"\nExport completed. Files saved in '{EXPORT_DIR}/' directory.")


async def main():
    """Run export if this module is executed directly."""
    await export_all()


if __name__ == "__main__":
    asyncio.run(main())