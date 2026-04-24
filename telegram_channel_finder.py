from __future__ import annotations

from dataclasses import dataclass
import asyncio
import socket
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional


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


def _normalize_username(username: str) -> str:
    username = username.strip().replace("https://t.me/", "")
    if username.startswith("@"):
        username = username[1:]
    return username.strip().lower()


def classify_category(text: str, category_rules: dict[str, list[str]]) -> str:
    text_l = text.lower()
    for category, keywords in category_rules.items():
        if any(k in text_l for k in keywords):
            return category
    return "other"


def detect_language(text: str) -> str:
    text_l = text.lower()
    ru_markers = [" и ", "что", "новости", "канал", "подпис"]
    en_markers = [" the ", "news", "channel", "official", "daily"]

    cyr = sum(1 for ch in text_l if "а" <= ch <= "я" or ch == "ё")
    lat = sum(1 for ch in text_l if "a" <= ch <= "z")

    if any(m in text_l for m in ru_markers) or cyr > lat * 0.8:
        return "ru"
    if any(m in text_l for m in en_markers) or lat > cyr:
        return "en"
    return "other"


def detect_country(text: str) -> str:
    text_l = text.lower()
    country_rules = {
        "germany": ["germany", "deutsch", "berlin", "munich", "hamburg", "германи"],
        "russia": ["россия", "russia", "москва", "спб"],
        "ukraine": ["украина", "ukraine", "киев", "kyiv"],
        "kazakhstan": ["казахстан", "kazakhstan", "алматы", "астана"],
        "belarus": ["беларус", "belarus", "минск"],
        "usa": ["usa", "united states", "америк", "new york", "washington"],
    }
    for country, words in country_rules.items():
        if any(w in text_l for w in words):
            return country
    return "unknown"


def filter_channels(
    channels: Iterable[ChannelInfo],
    required_category: str = "any",
    required_languages: Optional[list[str]] = None,
    required_countries: Optional[list[str]] = None,
    min_subscribers: int = 500,
    require_comments_open: bool = True,
    min_engagement_rate: float = 2.0,
    min_recent_posts: int = 3,
    active_within_days: int = 14,
) -> List[ChannelInfo]:
    required_languages = [x.lower() for x in (required_languages or [])]
    required_countries = [x.lower() for x in (required_countries or [])]

    now = datetime.now(timezone.utc)
    result: List[ChannelInfo] = []

    for ch in channels:
        if ch.subscribers < min_subscribers:
            continue
        if require_comments_open and not ch.comments_enabled:
            continue
        if required_category != "any" and ch.category != required_category:
            continue
        if required_languages and ch.language.lower() not in required_languages:
            continue
        if required_countries and ch.country.lower() not in required_countries:
            continue
        if ch.engagement_rate < min_engagement_rate:
            continue
        if ch.recent_posts < min_recent_posts:
            continue
        if ch.last_post_date is None:
            continue
        if ch.last_post_date < now - timedelta(days=active_within_days):
            continue
        result.append(ch)

    return sorted(result, key=lambda c: (c.engagement_rate, c.subscribers), reverse=True)


def discover_channels_via_telegram(
    api_id: int,
    api_hash: str,
    phone: str,
    search_queries: list[str],
    max_channels: int = 100,
    lookback_days: int = 30,
    proxy: Optional[dict] = None,
) -> List[ChannelInfo]:
    from telethon import TelegramClient, connection
    from telethon.errors import SessionPasswordNeededError
    from telethon.tl.functions.contacts import SearchRequest
    from telethon.tl.functions.channels import GetFullChannelRequest
    from telethon.tl.types import Channel

    category_rules = {
        "news": ["news", "новости", "срочно", "мир", "полит"],
        "finance": ["финанс", "инвест", "crypto", "крипт", "бизнес", "рынок"],
        "tech": ["tech", "тех", "it", "ai", "нейросет", "программ"],
        "education": ["образ", "курс", "study", "learning", "универс"],
        "entertainment": ["юмор", "mem", "кино", "music", "развлеч"],
    }

    unique: dict[str, ChannelInfo] = {}

    created_loop = False
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        created_loop = True

    client_kwargs = {
        "loop": loop,
        "connection_retries": 1,
        "request_retries": 1,
        "timeout": 20,
    }

    if proxy and proxy.get("mode") == "mtproto" and proxy.get("host") and proxy.get("secret"):
        client_kwargs["connection"] = connection.ConnectionTcpMTProxyRandomizedIntermediate
        client_kwargs["proxy"] = (proxy["host"], int(proxy.get("port", 443)), proxy["secret"])

    with TelegramClient("channel_finder_session", api_id, api_hash, **client_kwargs) as client:
        client.connect()
        if not client.is_user_authorized():
            client.send_code_request(phone)
            code = input("Введите код из Telegram: ")
            try:
                client.sign_in(phone, code)
            except SessionPasswordNeededError:
                password = input("Введите пароль 2FA: ")
                client.sign_in(password=password)

        for query in search_queries:
            if len(unique) >= max_channels:
                break
            res = client(SearchRequest(q=query, limit=min(100, max_channels)))
            for chat in res.chats:
                if len(unique) >= max_channels:
                    break
                if not isinstance(chat, Channel):
                    continue
                if not getattr(chat, "username", None):
                    continue

                uname = _normalize_username(chat.username)
                if uname in unique:
                    continue

                full = client(GetFullChannelRequest(chat))
                full_chat = full.full_chat
                subscribers = int(getattr(full_chat, "participants_count", 0) or 0)
                comments_enabled = bool(getattr(full_chat, "linked_chat_id", None))

                messages = list(client.iter_messages(chat, limit=50))
                recent_msgs = [m for m in messages if getattr(m, "date", None)]
                if not recent_msgs:
                    continue

                last_post = max(m.date for m in recent_msgs if m.date)
                cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
                active_msgs = [m for m in recent_msgs if m.date and m.date >= cutoff]
                recent_posts = len(active_msgs)
                views = [getattr(m, "views", 0) or 0 for m in active_msgs]
                avg_views = float(sum(views) / len(views)) if views else 0.0
                engagement_rate = (avg_views / subscribers * 100) if subscribers > 0 else 0.0

                text_for_meta = f"{chat.title or ''} {getattr(full_chat, 'about', '')}"
                category = classify_category(text_for_meta, category_rules)
                language = detect_language(text_for_meta)
                country = detect_country(text_for_meta)

                unique[uname] = ChannelInfo(
                    title=chat.title or uname,
                    username=f"@{uname}",
                    subscribers=subscribers,
                    comments_enabled=comments_enabled,
                    category=category,
                    language=language,
                    country=country,
                    recent_posts=recent_posts,
                    avg_views=round(avg_views, 2),
                    engagement_rate=round(engagement_rate, 2),
                    last_post_date=last_post,
                )

    if created_loop:
        loop.close()
    return list(unique.values())


def check_mtproto_proxy(host: str, port: int, secret: str, timeout: int = 8) -> tuple[bool, str]:
    """Quick connectivity check for MTProto endpoint reachability."""
    try:
        if not secret or len(secret) < 16:
            return False, "Слишком короткий secret MTProto."

        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.close()
        return True, "MTProto endpoint отвечает (TCP доступ есть)."
    except socket.timeout:
        return False, "Таймаут при подключении к MTProto endpoint."
    except Exception as exc:
        return False, f"MTProto endpoint недоступен: {exc}"
