# database.py

"""
RJ DEEP SEARCH - Light Crawler
Database module (SQLite + aiosqlite)
- Stores discovered URLs and their status
- Manages a persistent queue for crawling
- Provides methods to save results, get top scored URLs, and statistics
"""

import time
import aiosqlite

import config   # use external configuration

# Schema for two tables:
#   urls  – all URLs encountered, with status, depth, score, etc.
#   queue – URLs waiting to be processed (FIFO order)
SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
    url TEXT PRIMARY KEY,
    status INTEGER DEFAULT 0,   -- 0=new, 1=processing, 2=done, 3=failed
    depth INTEGER DEFAULT 0,
    score REAL DEFAULT 0.0,
    content_hash TEXT,
    visited_at REAL
);
CREATE TABLE IF NOT EXISTS queue (
    url TEXT PRIMARY KEY,
    depth INTEGER,
    added_at REAL
);
CREATE INDEX IF NOT EXISTS idx_urls_status ON urls(status);
CREATE INDEX IF NOT EXISTS idx_queue_added ON queue(added_at);
"""

class Database:
    def __init__(self, db_path=None):
        # Use path from config if not provided
        self.db_path = db_path or config.DB_PATH
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

    async def mark_processed(self, url, score, content_hash=None):
        """Mark a URL as successfully processed with a score."""
        await self.conn.execute(
            "UPDATE urls SET status = 2, score = ?, content_hash = ?, visited_at = ? WHERE url = ?",
            (score, content_hash, time.time(), url)
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
        """Return the top scored URLs that have been processed."""
        async with self.conn.execute(
            "SELECT url, score, depth FROM urls WHERE status = 2 AND score >= ? ORDER BY score DESC LIMIT ?",
            (min_score, limit)
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