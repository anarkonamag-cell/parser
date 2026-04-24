from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Iterable, List, Optional


TELEGRAM_WEB_BASE = "https://t.me/s/"


@dataclass
class Post:
    channel: str
    message_id: str
    text: str
    date: datetime
    views: Optional[int]
    url: str


def _normalize_channel(channel: str) -> str:
    channel = channel.strip()
    if channel.startswith("https://t.me/"):
        channel = channel.split("https://t.me/")[-1]
    if channel.startswith("@"):
        channel = channel[1:]
    channel = channel.split("/")[0].strip()
    if not channel:
        raise ValueError("Укажите имя публичного канала (например: durov)")
    return channel


def _parse_views(raw: str) -> Optional[int]:
    if not raw:
        return None
    cleaned = raw.replace(" ", "").replace(",", ".").lower()
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([km]?)", cleaned)
    if not match:
        return None
    value = float(match.group(1))
    suffix = match.group(2)
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return int(value)


def fetch_channel_posts(channel: str, timeout: int = 15) -> List[Post]:
    import requests
    from bs4 import BeautifulSoup

    channel_name = _normalize_channel(channel)
    url = f"{TELEGRAM_WEB_BASE}{channel_name}"
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    message_nodes = soup.select("div.tgme_widget_message_wrap")

    posts: List[Post] = []
    for node in message_nodes:
        text_node = node.select_one("div.tgme_widget_message_text")
        date_node = node.select_one("a.tgme_widget_message_date time")
        views_node = node.select_one("span.tgme_widget_message_views")
        date_link = node.select_one("a.tgme_widget_message_date")

        if not date_node or not date_link:
            continue

        raw_dt = date_node.attrs.get("datetime", "")
        if raw_dt.endswith("Z"):
            raw_dt = raw_dt.replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw_dt)

        text = text_node.get_text("\n", strip=True) if text_node else ""
        views = _parse_views(views_node.get_text(strip=True) if views_node else "")

        href = date_link.attrs.get("href", "")
        message_id = href.rstrip("/").split("/")[-1] if href else ""
        full_url = f"https://t.me{href}" if href.startswith("/") else href

        posts.append(
            Post(
                channel=channel_name,
                message_id=message_id,
                text=text,
                date=dt,
                views=views,
                url=full_url,
            )
        )

    return sorted(posts, key=lambda p: p.date, reverse=True)


def filter_posts(
    posts: Iterable[Post],
    keyword: str = "",
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    min_views: Optional[int] = None,
) -> List[Post]:
    keyword_lower = keyword.lower().strip()

    result: List[Post] = []
    for post in posts:
        if keyword_lower and keyword_lower not in post.text.lower():
            continue
        if date_from and post.date < date_from:
            continue
        if date_to and post.date > date_to:
            continue
        if min_views is not None:
            if post.views is None or post.views < min_views:
                continue
        result.append(post)
    return result
