# config.py

"""
RJ DEEP SEARCH - Light Crawler
Configuration file.
Edit these values to customize the crawler behavior without touching the core code.
"""

# ---- HTTP settings ----
REQUEST_TIMEOUT = 5            # seconds per request
MAX_CONCURRENT = 5             # number of simultaneous connections
MAX_DEPTH = 2                  # default crawl depth (levels from seed URL)
USER_AGENT = "Mozilla/5.0 (compatible; RJDeepSearch/0.1; +http://example.com/bot)"

# ---- Filtering ----
# File extensions to never fetch (you can remove or add)
BLOCKED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp",
    ".css", ".js", ".mp4", ".avi", ".mov", ".mp3", ".wav",
    ".zip", ".tar", ".gz", ".pdf", ".doc", ".docx", ".ppt",
    ".pptx", ".xls", ".xlsx", ".exe", ".dmg", ".iso"
}

# Content types we are willing to accept (only these will be fetched)
# Leave empty list to accept only text/html by default
ACCEPTED_CONTENT_TYPES = [
    "text/html",
    # "application/json",   # uncomment if you want JSON pages
    # "text/plain",        # uncomment for plain text
]

# Minimum score to consider a page useful (0 to 100)
SCORE_THRESHOLD = 5.0

# ---- Database ----
DB_PATH = "crawler.db"