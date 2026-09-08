# common_crawl.py

"""
RJ DEEP SEARCH - Light Crawler
Common Crawl Index integration.
Searches the Common Crawl URL index and returns a list of matching URLs.
No heavy scraping – just queries the official API.
"""

import aiohttp
import json
from urllib.parse import quote


async def search_cc_index(keyword, domain=None, limit=100, index="CC-MAIN-2024-10-index"):
    """
    Search the Common Crawl index for URLs matching a keyword.

    Parameters:
        keyword  : search term (e.g., "awesome list", "python tutorial")
        domain   : optional domain filter (e.g., "github.com")
        limit    : maximum number of results to return (default 100)
        index    : Common Crawl index name (default is a recent snapshot)

    Returns:
        list of URL strings
    """
    # Build the query pattern
    if domain:
        pattern = f"{domain}/*{keyword}*"
    else:
        pattern = f"*{keyword}*"

    # Common Crawl index API endpoint
    api_url = (
        f"http://index.commoncrawl.org/{index}-index"
        f"?url={quote(pattern)}&output=json&fl=url&limit={limit}"
    )

    urls = []

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(api_url, timeout=10) as response:
                if response.status != 200:
                    print(f"Common Crawl API error: HTTP {response.status}")
                    return urls

                text = await response.text()
                # Each line is a JSON object with a 'url' field
                for line in text.splitlines():
                    try:
                        data = json.loads(line)
                        if 'url' in data:
                            urls.append(data['url'])
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            print(f"Error querying Common Crawl: {e}")

    return urls