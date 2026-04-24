from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Iterable, List, Optional
from urllib.parse import quote



@dataclass
class ChannelInfo:
    title: str
    username: str
    subscribers: int
    comments_enabled: bool
    category: str
    language: str
    country: str
    recent_posts: int
    avg_views: float
    engagement_rate: float
    last_post_date: Optional[datetime]


def _parse_views(raw: str) -> int:
    cleaned = (raw or "").replace(" ", "").replace(",", ".").lower()
    m = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([km]?)", cleaned)
    if not m:
        return 0
    v = float(m.group(1))
    if m.group(2) == "k":
        v *= 1000
    elif m.group(2) == "m":
        v *= 1_000_000
    return int(v)


def detect_language(text: str) -> str:
    cyr = sum(1 for ch in text.lower() if "а" <= ch <= "я" or ch == "ё")
    lat = sum(1 for ch in text.lower() if "a" <= ch <= "z")
    if cyr > lat:
        return "ru"
    if lat > cyr:
        return "en"
    return "other"


def detect_country(text: str) -> str:
    text_l = text.lower()
    rules = {
        "germany": ["germany", "deutsch", "berlin", "герман"],
        "france": ["france", "paris", "франц"],
        "italy": ["italy", "roma", "итал"],
        "spain": ["spain", "madrid", "испан"],
        "netherlands": ["netherlands", "holland", "amsterdam"],
        "poland": ["poland", "warsaw", "польш"],
        "russia": ["россия", "russia", "москва"],
        "usa": ["usa", "united states", "америк"],
    }
    for c, words in rules.items():
        if any(w in text_l for w in words):
            return c
    return "unknown"


def classify_category(text: str) -> str:
    t = text.lower()
    if any(x in t for x in ["news", "новости", "полит"]):
        return "news"
    if any(x in t for x in ["финанс", "crypto", "крипт", "инвест"]):
        return "finance"
    if any(x in t for x in ["tech", "it", "ai", "нейросет"]):
        return "tech"
    if any(x in t for x in ["курс", "study", "образ"]):
        return "education"
    if any(x in t for x in ["юмор", "кино", "music", "mem"]):
        return "entertainment"
    return "other"


def _discover_usernames(search_queries: list[str], max_channels: int = 100) -> list[str]:
    import requests
    headers = {"User-Agent": "Mozilla/5.0"}
    found: list[str] = []
    for q in search_queries:
        if len(found) >= max_channels:
            break
        url = f"https://tgstat.com/en/channels/search?query={quote(q)}"
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            continue
        # find /channel/@username links
        usernames = set(re.findall(r"/channel/@([a-zA-Z0-9_]{5,})", r.text))
        for uname in usernames:
            if uname not in found:
                found.append(uname)
            if len(found) >= max_channels:
                break
    return found


def _analyze_channel(username: str, lookback_days: int = 30) -> Optional[ChannelInfo]:
    import requests
    from bs4 import BeautifulSoup
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(f"https://t.me/s/{username}", headers=headers, timeout=20)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")

    title = (soup.select_one("div.tgme_channel_info_header_title") or soup.select_one("meta[property='og:title']"))
    title_text = title.get_text(strip=True) if hasattr(title, "get_text") else (title.get("content", username) if title else username)
    about = soup.select_one("div.tgme_channel_info_description")
    about_text = about.get_text(" ", strip=True) if about else ""

    nodes = soup.select("div.tgme_widget_message_wrap")
    if not nodes:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    recent_posts = 0
    views_arr: list[int] = []
    last_post: Optional[datetime] = None

    for node in nodes[:50]:
        t = node.select_one("a.tgme_widget_message_date time")
        if not t:
            continue
        dt_raw = t.get("datetime", "")
        if dt_raw.endswith("Z"):
            dt_raw = dt_raw.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(dt_raw)
        except Exception:
            continue
        if last_post is None or dt > last_post:
            last_post = dt
        if dt < cutoff:
            continue
        recent_posts += 1
        v = node.select_one("span.tgme_widget_message_views")
        views_arr.append(_parse_views(v.get_text(strip=True) if v else "0"))

    avg_views = float(sum(views_arr) / len(views_arr)) if views_arr else 0.0

    # Subscribers from web source not reliable: keep 0 when unknown.
    subscribers = 0
    engagement_rate = 0.0

    text_for_meta = f"{title_text} {about_text}"
    return ChannelInfo(
        title=title_text,
        username=f"@{username}",
        subscribers=subscribers,
        comments_enabled=True,
        category=classify_category(text_for_meta),
        language=detect_language(text_for_meta),
        country=detect_country(text_for_meta),
        recent_posts=recent_posts,
        avg_views=round(avg_views, 2),
        engagement_rate=round(engagement_rate, 2),
        last_post_date=last_post,
    )


def discover_channels_via_telegram(
    api_id: int,
    api_hash: str,
    phone: str,
    search_queries: list[str],
    max_channels: int = 100,
    lookback_days: int = 30,
    proxy: Optional[dict] = None,
) -> List[ChannelInfo]:
    usernames = _discover_usernames(search_queries, max_channels=max_channels)
    items: list[ChannelInfo] = []
    for uname in usernames:
        ch = _analyze_channel(uname, lookback_days=lookback_days)
        if ch:
            items.append(ch)
    return items


def check_mtproto_proxy(*args, **kwargs) -> tuple[bool, str]:
    return True, "Telethon отключен: проверка MTProto недоступна в веб-режиме."


def check_socks5_proxy(*args, **kwargs) -> tuple[bool, str]:
    return True, "Telethon отключен: проверка SOCKS5 недоступна в веб-режиме."


def filter_channels(
    channels: Iterable[ChannelInfo],
    required_category: str = "any",
    required_languages: Optional[list[str]] = None,
    required_countries: Optional[list[str]] = None,
    min_subscribers: int = 0,
    require_comments_open: bool = False,
    min_engagement_rate: float = 0.0,
    min_recent_posts: int = 1,
    active_within_days: int = 30,
) -> List[ChannelInfo]:
    required_languages = [x.lower() for x in (required_languages or [])]
    required_countries = [x.lower() for x in (required_countries or [])]

    now = datetime.now(timezone.utc)
    out: list[ChannelInfo] = []
    for ch in channels:
        if required_category != "any" and ch.category != required_category:
            continue
        if required_languages and ch.language not in required_languages:
            continue
        if required_countries and ch.country not in required_countries:
            continue
        if ch.recent_posts < min_recent_posts:
            continue
        if ch.last_post_date and ch.last_post_date < now - timedelta(days=active_within_days):
            continue
        out.append(ch)
    return out
