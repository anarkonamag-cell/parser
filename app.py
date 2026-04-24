from __future__ import annotations

import csv
import io
import json
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from telegram_channel_finder import discover_channels_via_telegram, filter_channels

app = Flask(__name__)
PARSE_LOCK = threading.Lock()
SETTINGS_FILE = Path("tg_defaults.json")
DEFAULT_SETTINGS = {
    "api_id": "35779099",
    "api_hash": "4b4d4ecbe7623c805baf43ce6aef2448",
    "phone": "+79198037500",
    "proxy_host": "",
    "proxy_port": "1080",
    "proxy_username": "",
    "proxy_password": "",
}


def load_settings() -> dict:
    if not SETTINGS_FILE.exists():
        return DEFAULT_SETTINGS.copy()
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        merged = DEFAULT_SETTINGS.copy()
        merged.update({k: str(v) for k, v in data.items() if k in DEFAULT_SETTINGS})
        return merged
    except Exception:
        return DEFAULT_SETTINGS.copy()


def save_settings(data: dict) -> None:
    payload = DEFAULT_SETTINGS.copy()
    payload.update({k: str(v) for k, v in data.items() if k in payload})
    SETTINGS_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/settings")
def get_settings():
    return jsonify({"ok": True, "settings": load_settings()})


@app.post("/api/settings")
def set_settings():
    data = request.get_json(force=True, silent=True) or {}
    save_settings(data)
    return jsonify({"ok": True})


@app.post("/api/parse")
def parse_channel_list():
    saved = load_settings()

    api_id_raw = request.form.get("api_id", "").strip() or saved["api_id"]
    api_hash = request.form.get("api_hash", "").strip() or saved["api_hash"]
    phone = request.form.get("phone", "").strip() or saved["phone"]
    queries_raw = request.form.get("queries", "").strip()

    if not api_id_raw or not api_hash or not phone or not queries_raw:
        return jsonify({"ok": False, "error": "Заполните API ID, API HASH, телефон и поисковые запросы."}), 400

    current_settings = {
        "api_id": api_id_raw,
        "api_hash": api_hash,
        "phone": phone,
        "proxy_host": request.form.get("proxy_host", "").strip(),
        "proxy_port": request.form.get("proxy_port", "1080").strip(),
        "proxy_username": request.form.get("proxy_username", "").strip(),
        "proxy_password": request.form.get("proxy_password", "").strip(),
    }
    save_settings(current_settings)

    required_category = request.form.get("category", "any")
    selected_languages = [v.strip().lower() for v in request.form.getlist("languages") if v.strip()]
    selected_countries = [v.strip().lower() for v in request.form.getlist("countries") if v.strip()]

    min_subscribers = int(request.form.get("min_subscribers", "500") or 500)
    require_comments_open = request.form.get("require_comments", "on") == "on"
    min_engagement_rate = float(request.form.get("min_engagement_rate", "2") or 2)
    min_recent_posts = int(request.form.get("min_recent_posts", "3") or 3)
    active_within_days = int(request.form.get("active_within_days", "14") or 14)
    max_channels = int(request.form.get("max_channels", "100") or 100)
    lookback_days = int(request.form.get("lookback_days", "30") or 30)

    search_queries = [q.strip() for q in queries_raw.split(",") if q.strip()]

    proxy = None
    if current_settings["proxy_host"]:
        proxy = {
            "host": current_settings["proxy_host"],
            "port": int(current_settings["proxy_port"] or "1080"),
            "username": current_settings["proxy_username"] or None,
            "password": current_settings["proxy_password"] or None,
        }

    if not PARSE_LOCK.acquire(blocking=False):
        return jsonify({"ok": False, "error": "Парсинг уже выполняется. Дождитесь завершения текущего запуска и повторите."}), 409

    try:
        discovered = discover_channels_via_telegram(
            api_id=int(api_id_raw),
            api_hash=api_hash,
            phone=phone,
            search_queries=search_queries,
            max_channels=max_channels,
            lookback_days=lookback_days,
            proxy=proxy,
        )
        filtered = filter_channels(
            discovered,
            required_category=required_category,
            required_languages=selected_languages,
            required_countries=selected_countries,
            min_subscribers=min_subscribers,
            require_comments_open=require_comments_open,
            min_engagement_rate=min_engagement_rate,
            min_recent_posts=min_recent_posts,
            active_within_days=active_within_days,
        )
    except TimeoutError:
        return jsonify(
            {
                "ok": False,
                "error": "Таймаут подключения к Telegram. Попробуйте прокси (SOCKS5), проверьте сеть и повторите.",
            }
        ), 400
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": f"Ошибка парсинга: {exc}"}), 400
    finally:
        PARSE_LOCK.release()

    return jsonify(
        {
            "ok": True,
            "count": len(filtered),
            "items": [
                {
                    "title": c.title,
                    "username": c.username,
                    "subscribers": c.subscribers,
                    "comments_enabled": c.comments_enabled,
                    "category": c.category,
                    "language": c.language,
                    "country": c.country,
                    "recent_posts": c.recent_posts,
                    "avg_views": c.avg_views,
                    "engagement_rate": c.engagement_rate,
                    "last_post_date": c.last_post_date.isoformat() if c.last_post_date else None,
                }
                for c in filtered
            ],
        }
    )


@app.post("/api/export")
def export_csv():
    payload = request.get_json(force=True, silent=True) or {}
    items = payload.get("items", [])

    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "title",
            "username",
            "subscribers",
            "comments_enabled",
            "category",
            "language",
            "country",
            "recent_posts",
            "avg_views",
            "engagement_rate",
            "last_post_date",
        ],
    )
    writer.writeheader()
    for item in items:
        writer.writerow(item)

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=telegram_channels.csv"},
    )


if __name__ == "__main__":
    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
    app.run(host="0.0.0.0", port=5000, debug=True)
