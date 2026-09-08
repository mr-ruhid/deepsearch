# exporter.py

"""
RJ DEEP SEARCH - Light Crawler
JSON export module.

Reads processed results from the SQLite database and writes them to JSON files,
organized by search term. Each search term gets its own directory and JSON file.

Output structure per resource:
{
    "id": unique_string,
    "title": "...",
    "description": "...",
    "url": "...",
    "image_url": "...",
    "tags": ["tag1", "tag2"]
}
"""

import os
import json
import hashlib
import asyncio
from database import Database

# Directory where JSON files will be stored
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
    (url, score, depth, title, description, image_url, tags, search_term)
    """
    url, score, depth, title, description, image_url, tags, search_term = row
    return {
        "id": generate_id(url),
        "title": title or "",
        "description": description or "",
        "url": url,
        "image_url": image_url or "",
        "tags": parse_tags(tags),
        "score": score,
        "depth": depth,
        "search_term": search_term or ""
    }


async def export_all():
    """
    Export all processed results to JSON files.
    Groups by search_term.
    """
    db = Database()
    await db.connect()
    rows = await db.get_all_results(min_score=0.0)
    await db.close()

    if not rows:
        print("No results to export.")
        return

    # Group rows by search_term
    groups = {}
    for row in rows:
        search_term = row[7] if len(row) > 7 and row[7] else "unknown"
        if search_term not in groups:
            groups[search_term] = []
        groups[search_term].append(build_resource_dict(row))

    # Create export directory if it doesn't exist
    os.makedirs(EXPORT_DIR, exist_ok=True)

    # Write JSON file for each search term
    for term, resources in groups.items():
        # Sanitize filename (remove/replace invalid characters)
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in term)
        safe_name = safe_name.strip().replace(' ', '_').lower()
        if not safe_name:
            safe_name = "results"

        file_path = os.path.join(EXPORT_DIR, f"{safe_name}.json")

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(resources, f, indent=2, ensure_ascii=False)

        print(f"[✓] Exported {len(resources)} resources to {file_path}")

    print(f"\nExport completed. Files saved in '{EXPORT_DIR}/' directory.")


async def main():
    """Run export if this module is executed directly."""
    await export_all()


if __name__ == "__main__":
    asyncio.run(main())