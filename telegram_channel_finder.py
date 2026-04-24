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


def _normalize_secret(secret: str) -> str:
    return "".join(secret.strip().split()).lower()


def classify_category(text: str, category_rules: dict[str, list[str]]) -> str:
    text_l = text.lower()
    for category, keywords in category_rules.items():
        if any(k in text_l for k in keywords):
            return category
    return "other"


def detect_language(text: str) -> str:
    text_l = text.lower()
    cyr = sum(1 for ch in text_l if "а" <= ch <= "я" or ch == "ё")
    lat = sum(1 for ch in text_l if "a" <= ch <= "z")
    if cyr > lat * 0.8:
        return "ru"
    if lat > cyr:
        return "en"
    return "other"


def detect_country(text: str) -> str:
    text_l = text.lower()
    country_rules = {
        "germany": ["germany", "deutsch", "berlin", "герман"],
        "france": ["france", "paris", "франц"],
        "italy": ["italy", "roma", "итал"],
        "spain": ["spain", "madrid", "испан"],
        "portugal": ["portugal", "lisbon", "португал"],
        "netherlands": ["netherlands", "holland", "amsterdam", "нидерланд"],
        "belgium": ["belgium", "brussels", "бельг"],
        "switzerland": ["switzerland", "zurich", "bern", "швейцар"],
        "austria": ["austria", "vienna", "австри"],
        "poland": ["poland", "warsaw", "польш"],
        "czechia": ["czech", "prague", "чех"],
        "slovakia": ["slovakia", "bratislava", "словаки"],
        "hungary": ["hungary", "budapest", "венгр"],
        "romania": ["romania", "bucharest", "румын"],
        "bulgaria": ["bulgaria", "sofia", "болгар"],
        "greece": ["greece", "athens", "греци"],
        "croatia": ["croatia", "zagreb", "хорват"],
        "serbia": ["serbia", "belgrade", "серби"],
        "slovenia": ["slovenia", "ljubljana", "словени"],
        "bosnia": ["bosnia", "sarajevo", "босн"],
        "montenegro": ["montenegro", "podgorica", "черногор"],
        "albania": ["albania", "tirana", "албани"],
        "north_macedonia": ["macedonia", "skopje", "македон"],
        "norway": ["norway", "oslo", "норвег"],
        "sweden": ["sweden", "stockholm", "швец"],
        "finland": ["finland", "helsinki", "финлян"],
        "denmark": ["denmark", "copenhagen", "дан"],
        "ireland": ["ireland", "dublin", "ирланд"],
        "iceland": ["iceland", "reykjavik", "ислан"],
        "estonia": ["estonia", "tallinn", "эстон"],
        "latvia": ["latvia", "riga", "латви"],
        "lithuania": ["lithuania", "vilnius", "литв"],
        "luxembourg": ["luxembourg", "люксем"],
        "malta": ["malta", "мальт"],
        "cyprus": ["cyprus", "кипр"],
        "ukraine": ["украина", "ukraine", "киев", "kyiv"],
        "belarus": ["беларус", "belarus", "минск"],
        "russia": ["россия", "russia", "москва", "спб"],
        "kazakhstan": ["казахстан", "kazakhstan", "алматы", "астана"],
        "usa": ["usa", "united states", "америк"],
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


def _telethon_client_for_mtproto(session_name: str, api_id: int, api_hash: str, host: str, port: int, secret: str, loop):
    from telethon.sync import TelegramClient
    from telethon import connection

    conn_candidates = [
        connection.ConnectionTcpMTProxyRandomizedIntermediate,
        connection.ConnectionTcpMTProxyIntermediate,
        connection.ConnectionTcpMTProxyAbridged,
    ]

    last_exc: Exception | None = None
    for conn_cls in conn_candidates:
        client = TelegramClient(
            session_name,
            api_id,
            api_hash,
            loop=loop,
            connection=conn_cls,
            proxy=(host, port, secret),
            connection_retries=1,
            request_retries=1,
            timeout=20,
        )
        try:
            client.connect()
            if client.is_connected():
                return client
            client.disconnect()
        except Exception as exc:
            last_exc = exc
            try:
                client.disconnect()
            except Exception:
                pass
    raise RuntimeError(f"MTProto connect failed: {last_exc}")


def _telethon_client_for_socks5(session_name: str, api_id: int, api_hash: str, host: str, port: int, username, password, loop):
    from telethon.sync import TelegramClient
    import socks

    client = TelegramClient(
        session_name,
        api_id,
        api_hash,
        loop=loop,
        proxy=(socks.SOCKS5, host, port, True, username, password),
        connection_retries=1,
        request_retries=1,
        timeout=20,
    )
    client.connect()
    return client


def discover_channels_via_telegram(
    api_id: int,
    api_hash: str,
    phone: str,
    search_queries: list[str],
    max_channels: int = 100,
    lookback_days: int = 30,
    proxy: Optional[dict] = None,
) -> List[ChannelInfo]:
    from telethon.sync import TelegramClient
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

    client = None
    try:
        if proxy and proxy.get("mode") == "mtproto":
            client = _telethon_client_for_mtproto(
                session_name="channel_finder_session",
                api_id=api_id,
                api_hash=api_hash,
                host=proxy["host"],
                port=int(proxy.get("port", 443)),
                secret=_normalize_secret(proxy["secret"]),
                loop=loop,
            )
        elif proxy and proxy.get("mode") == "socks5":
            client = _telethon_client_for_socks5(
                session_name="channel_finder_session",
                api_id=api_id,
                api_hash=api_hash,
                host=proxy["host"],
                port=int(proxy.get("port", 1080)),
                username=proxy.get("username"),
                password=proxy.get("password"),
                loop=loop,
            )
        else:
            client = TelegramClient("channel_finder_session", api_id, api_hash, loop=loop)
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
    finally:
        if client is not None:
            try:
                client.disconnect()
            except Exception:
                pass
        if created_loop:
            loop.close()

    return list(unique.values())


def check_mtproto_proxy(host: str, port: int, secret: str, timeout: int = 8, api_id: Optional[int] = None, api_hash: Optional[str] = None) -> tuple[bool, str]:
    try:
        normalized_secret = _normalize_secret(secret)
        if not normalized_secret or len(normalized_secret) < 16:
            return False, "Слишком короткий secret MTProto."

        sock = socket.create_connection((host, int(port)), timeout=timeout)
        sock.close()

        if api_id and api_hash:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                client = _telethon_client_for_mtproto(
                    session_name="mtproto_check_session",
                    api_id=api_id,
                    api_hash=api_hash,
                    host=host,
                    port=int(port),
                    secret=normalized_secret,
                    loop=loop,
                )
                client.disconnect()
            finally:
                loop.close()
            return True, "MTProto проверка успешна: TCP + Telethon handshake OK."

        return True, "MTProto endpoint отвечает (TCP доступ есть)."
    except Exception as exc:
        return False, f"MTProto недоступен/некорректен: {exc}"


def check_socks5_proxy(host: str, port: int, username=None, password=None, timeout: int = 8, api_id: Optional[int] = None, api_hash: Optional[str] = None) -> tuple[bool, str]:
    try:
        import socks

        sock = socks.socksocket()
        sock.set_proxy(socks.SOCKS5, host, int(port), True, username, password)
        sock.settimeout(timeout)
        sock.connect(("149.154.167.51", 443))
        sock.close()

        if api_id and api_hash:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                client = _telethon_client_for_socks5(
                    session_name="socks5_check_session",
                    api_id=api_id,
                    api_hash=api_hash,
                    host=host,
                    port=int(port),
                    username=username,
                    password=password,
                    loop=loop,
                )
                client.disconnect()
            finally:
                loop.close()
            return True, "SOCKS5 проверка успешна: TCP + Telethon handshake OK."

        return True, "SOCKS5 endpoint отвечает (TCP доступ есть)."
    except Exception as exc:
        return False, f"SOCKS5 недоступен/некорректен: {exc}"
