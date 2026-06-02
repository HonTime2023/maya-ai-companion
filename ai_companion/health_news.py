"""
Health News Module — Voice-callable health news from free RSS feeds.
No API key required. Uses BBC Health, WHO, and Medical News Today RSS.
All functions return plain spoken strings.
"""
import logging
from datetime import datetime

logger = logging.getLogger("AI_Companion")

_FEEDS = {
    "bbc":     "http://feeds.bbci.co.uk/news/health/rss.xml",
    "who":     "https://www.who.int/rss-feeds/news-english.xml",
    "medical": "https://www.medicalnewstoday.com/rss",
}

_DEFAULT_SOURCES = ["bbc", "medical"]


def _fetch_headlines(source_key: str, max_items: int = 5) -> list[dict]:
    """Fetch and return headline dicts from a single RSS feed."""
    try:
        import feedparser
        feed = feedparser.parse(_FEEDS[source_key])
        results = []
        for entry in feed.entries[:max_items]:
            results.append({
                "title": entry.get("title", "").strip(),
                "summary": entry.get("summary", "").strip()[:200],
                "published": entry.get("published", ""),
                "source": source_key.upper(),
            })
        return results
    except Exception as e:
        logger.error(f"[HEALTH_NEWS] Failed to fetch {source_key}: {e}")
        return []


def get_health_news(topic: str = None, count: int = 3) -> str:
    """
    Fetch top health news headlines. Optional topic filter (e.g. 'cancer', 'diabetes').
    Returns spoken summary of top headlines.
    """
    try:
        count = max(1, min(int(count), 5))
    except (TypeError, ValueError):
        count = 3

    all_items = []
    for src in _DEFAULT_SOURCES:
        all_items.extend(_fetch_headlines(src, max_items=8))

    if not all_items:
        return (
            "I was unable to fetch health news right now. "
            "Please check your internet connection and try again."
        )

    # Filter by topic if given
    if topic:
        topic_lower = topic.lower()
        filtered = [i for i in all_items if topic_lower in i["title"].lower() or topic_lower in i["summary"].lower()]
        if filtered:
            all_items = filtered
        else:
            return f"I could not find any recent health news about {topic}. Here are today's top health headlines instead. " + _format_headlines(all_items[:count])

    return _format_headlines(all_items[:count])


def _format_headlines(items: list[dict]) -> str:
    if not items:
        return "No health news available right now."

    lines = [f"Here are the latest health headlines."]
    for i, item in enumerate(items, 1):
        lines.append(f"Headline {i}: {item['title']}.")
        if item.get("summary"):
            # Trim summary to a short spoken version
            summary = item["summary"].split(".")[0].strip()
            if len(summary) > 20:
                lines.append(summary + ".")

    return " ".join(lines)


def get_health_news_by_topic(topic: str) -> str:
    """Search health news for a specific topic like 'diabetes', 'cancer', 'heart disease'."""
    return get_health_news(topic=topic, count=3)
