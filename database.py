# database.py

"""
RJ DEEP SEARCH - Light Crawler
Database module (SQLite + aiosqlite)
- Stores discovered URLs and their metadata
- Manages a persistent queue for crawling
- Provides methods to save results, get top scored URLs, statistics, and export data
- Uses search_results table to track each search session separately and mark new URLs
"""

import time
import json
import hashlib
import aiosqlite

import config   # use external configuration

# Default image URL if none is provided
DEFAULT_IMAGE_URL = "https://github.com/mr-ruhid/deepsearch/blob/main/photo/link.png"

# If config doesn't have DB_PATH, use a default value
DB_PATH = getattr(config, "DB_PATH", "crawler.db")

# Schema for tables:
#   urls           – all unique URLs encountered, with metadata
#   search_results – association between search sessions and URLs, with is_new flag
#   queue          – URLs waiting to be processed (FIFO order)
SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    url TEXT PRIMARY KEY,
    status INTEGER DEFAULT 0,   -- 0=new, 1=processing, 2=done, 3=failed
    depth INTEGER DEFAULT 0,
    score REAL DEFAULT 0.0,
    title TEXT,
    description TEXT,
    image_url TEXT,
    tags TEXT,                  -- JSON array as string
    search_term TEXT,           -- the search keyword that led to this result
    content_hash TEXT,
    visited_at REAL
);
CREATE TABLE IF NOT EXISTS search_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id TEXT NOT NULL,
    url TEXT NOT NULL,
    is_new INTEGER DEFAULT 1,
    FOREIGN KEY (url) REFERENCES urls (url) ON DELETE CASCADE,
    UNIQUE(search_id, url)
);
CREATE TABLE IF NOT EXISTS queue (
    url TEXT PRIMARY KEY,
    depth INTEGER,
    added_at REAL
);
CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status);
CREATE INDEX IF NOT EXISTS idx_queue_added ON queue(added_at);
CREATE INDEX IF NOT EXISTS idx_search_results_search_id ON search_results(search_id);
"""

class Database:
    def __init__(self, db_path=None):
        # Use path from config if not provided, else use the module-level DB_PATH
        self.db_path = db_path or DB_PATH
        self.conn = None

    async def connect(self):
        """Open the SQLite connection and create tables if needed."""
        self.conn = await aiosqlite.connect(self.db_path)
        await self.conn.executescript(SCHEMA)
        await self.conn.commit()

    async def close(self):
        """Close the connection."""
        if self.conn:
            await self.conn.close()

    async def add_to_queue(self, url, depth=0):
        """
        Add a URL to the queue, ignoring if it already exists.
        Also add it to the urls table with status 0 if not present.
        """
        await self.conn.execute(
            "INSERT OR IGNORE INTO urls (url, status, depth) VALUES (?, 0, ?)",
            (url, depth)
        )
        await self.conn.execute(
            "INSERT OR IGNORE INTO queue (url, depth, added_at) VALUES (?, ?, ?)",
            (url, depth, time.time())
        )
        await self.conn.commit()

    async def get_next_from_queue(self):
        """
        Retrieve the oldest URL from the queue.
        Marks it as 'processing' in the urls table.
        Returns a tuple (url, depth) or None if queue is empty.
        """
        async with self.conn.execute(
            "SELECT url, depth FROM queue ORDER BY added_at ASC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            url, depth = row

        # Update status to processing (URL already exists in urls table)
        await self.conn.execute(
            "UPDATE urls SET status = 1, depth = ? WHERE url = ?",
            (depth, url)
        )
        # Remove from queue
        await self.conn.execute("DELETE FROM queue WHERE url = ?", (url,))
        await self.conn.commit()
        return url, depth

    async def mark_processed(self, url, score, content_hash=None, title=None, description=None, image_url=None, tags=None, search_term=None):
        """
        Mark a URL as successfully processed with a score.
        Optionally update metadata fields.
        If image_url is not provided, use DEFAULT_IMAGE_URL.
        This method is used for crawler results (platform / Common Crawl).
        It does NOT write to search_results.
        """
        if image_url is None:
            image_url = DEFAULT_IMAGE_URL

        if tags is not None and not isinstance(tags, str):
            tags = json.dumps(tags)

        await self.conn.execute(
            """
            UPDATE urls
            SET status = 2,
                score = ?,
                content_hash = ?,
                title = ?,
                description = ?,
                image_url = ?,
                tags = ?,
                search_term = ?,
                visited_at = ?
            WHERE url = ?
            """,
            (score, content_hash, title, description, image_url, tags, search_term, time.time(), url)
        )
        await self.conn.commit()

    async def add_result(self, url, title, description, image_url, tags, score=0.0, depth=0, search_term=None, search_id=None):
        """
        Insert or replace a URL as a processed result with full metadata.
        This is used for direct results from SearXNG or similar.

        Additionally, record the association in search_results:
        - If URL does not exist in urls, insert it and mark is_new = 1
        - If URL already exists, only add a search_results entry with is_new = 0

        This ensures the same URL can appear in multiple search sessions
        without being duplicated in the urls table, and we can distinguish new links.

        Parameters:
            search_id : required unique identifier for this search session.
        """
        if not image_url:
            image_url = DEFAULT_IMAGE_URL
        if search_id is None:
            search_id = "unknown"

        # Check if URL already exists in urls table
        cursor = await self.conn.execute("SELECT 1 FROM urls WHERE url = ?", (url,))
        exists = await cursor.fetchone()

        is_new = 0 if exists else 1

        tags_json = json.dumps(tags) if tags else None

        if not exists:
            # Insert new URL into urls table
            await self.conn.execute(
                """
                INSERT INTO urls
                (url, status, depth, score, title, description, image_url, tags, search_term, visited_at)
                VALUES (?, 2, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (url, depth, score, title, description, image_url, tags_json, search_term, time.time())
            )
        else:
            # Optionally update existing URL's metadata if desired
            # For now we leave it as is; can be changed later
            pass

        # Record in search_results
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO search_results (search_id, url, is_new)
            VALUES (?, ?, ?)
            """,
            (search_id, url, is_new)
        )
        await self.conn.commit()

    async def mark_failed(self, url, status=3):
        """Mark a URL as failed with a specific status code."""
        await self.conn.execute(
            "UPDATE urls SET status = ?, visited_at = ? WHERE url = ?",
            (status, time.time(), url)
        )
        await self.conn.commit()

    async def get_top_results(self, limit=50, min_score=0.0):
        """
        Return the top scored URLs that have been processed.
        This method does not include search_results information.
        """
        async with self.conn.execute(
            """
            SELECT url, score, depth, title, description, image_url, tags, search_term
            FROM urls
            WHERE status = 2 AND score >= ?
            ORDER BY score DESC
            LIMIT ?
            """,
            (min_score, limit)
        ) as cursor:
            rows = await cursor.fetchall()
        return rows

    async def get_all_results(self, min_score=0.0):
        """
        Return all processed results with metadata, including search session info.
        Joins urls with search_results.
        Each row: (url, score, depth, title, description, image_url, tags, search_term, search_id, is_new)
        """
        async with self.conn.execute(
            """
            SELECT u.url, u.score, u.depth, u.title, u.description, u.image_url, u.tags,
                   u.search_term, sr.search_id, sr.is_new
            FROM search_results sr
            JOIN urls u ON u.url = sr.url
            WHERE u.status = 2 AND u.score >= ?
            ORDER BY u.score DESC
            """,
            (min_score,)
        ) as cursor:
            rows = await cursor.fetchall()
        return rows

    async def get_stats(self):
        """Return basic statistics: number of URLs processed, in queue, etc."""
        stats = {}
        async with self.conn.execute("SELECT COUNT(*) FROM urls") as cursor:
            row = await cursor.fetchone()
            stats["total_urls"] = row[0] if row else 0

        async with self.conn.execute("SELECT COUNT(*) FROM urls WHERE status = 2") as cursor:
            row = await cursor.fetchone()
            stats["processed"] = row[0] if row else 0

        async with self.conn.execute("SELECT COUNT(*) FROM queue") as cursor:
            row = await cursor.fetchone()
            stats["in_queue"] = row[0] if row else 0

        return stats