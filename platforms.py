# platforms.py

"""
RJ DEEP SEARCH - Light Crawler
This module holds the list of platforms that can be crawled.
Each platform is defined as a dictionary with:
- id           : unique short identifier
- name         : display name
- description  : short description of what the platform offers
- seed_urls    : starting points for crawling
- keywords     : used later for heuristic scoring
You can add more platforms by appending new dictionaries to the PLATFORMS list.
"""

PLATFORMS = [
    {
        "id": "github",
        "name": "GitHub",
        "description": "Open-source projects and developer resources",
        "seed_urls": [
            "https://github.com/sindresorhus/awesome",
            "https://github.com/topics",
        ],
        "keywords": ["awesome", "list", "tool", "free", "developer", "open-source"]
    },
    {
        "id": "stackoverflow",
        "name": "Stack Overflow",
        "description": "Programming questions and answers",
        "seed_urls": [
            "https://stackoverflow.com/questions",
            "https://stackoverflow.com/tags",
        ],
        "keywords": ["question", "answer", "developer", "programming", "solution"]
    },
    {
        "id": "reddit",
        "name": "Reddit",
        "description": "Various communities and discussions",
        "seed_urls": [
            "https://www.reddit.com/r/programming/",
            "https://www.reddit.com/r/learnprogramming/",
        ],
        "keywords": ["resource", "tutorial", "guide", "free", "tool"]
    },
    {
        "id": "hackernews",
        "name": "Hacker News",
        "description": "Tech news and startup discussions",
        "seed_urls": [
            "https://news.ycombinator.com/",
        ],
        "keywords": ["startup", "tech", "programming", "show", "ask"]
    },
    {
        "id": "devto",
        "name": "Dev.to",
        "description": "Developer articles and tutorials",
        "seed_urls": [
            "https://dev.to/",
        ],
        "keywords": ["tutorial", "developer", "programming", "guide", "webdev"]
    },
    {
        "id": "medium",
        "name": "Medium",
        "description": "Articles on various technical topics",
        "seed_urls": [
            "https://medium.com/tag/programming",
        ],
        "keywords": ["programming", "software", "tutorial", "guide", "developer"]
    },
    # Add more platforms here
]

def get_platform(platform_id):
    """Return the platform dictionary matching the given id."""
    for p in PLATFORMS:
        if p["id"] == platform_id:
            return p
    return None

def list_platforms():
    """Print the list of available platforms."""
    print("Available platforms:")
    for i, p in enumerate(PLATFORMS, start=1):
        print(f"{i}. {p['name']} - {p['description']}")