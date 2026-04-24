from __future__ import annotations

import csv
import io
import json
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request

from telegram_channel_finder import check_mtproto_proxy, discover_channels_via_telegram, filter_channels

app = Flask(__name__)
PARSE_LOCK = threading.Lock()
SETTINGS_FILE = Path("tg_defaults.json")
DEFAULT_SETTINGS = {
    "api_id": "35779099",
    "api_hash": "4b4d4ecbe7623c805baf43ce6aef2448",
    "phone": "+79198037500",
    "mtproto_host": "138.249.28.36",
    "mtproto_port": "443",
    "mtproto_secret": "ee534540bab647a0ee1f9a9452d43a729a79612e7275",
    "mtproto_dc_id": "8049",
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


@app.post("/api/check_proxy")
def check_proxy():
    payload = request.get_json(force=True, silent=True) or {}
    host = str(payload.get("mtproto_host", "")).strip()
    port = str(payload.get("mtproto_port", "443")).strip()
    secret = str(payload.get("mtproto_secret", "")).strip()
    api_id = str(payload.get("api_id", "")).strip()
    api_hash = str(payload.get("api_hash", "")).strip()

    if not host or not secret:
        return jsonify({"ok": False, "error": "Укажите MTProto host и secret."}), 400

    ok, message = check_mtproto_proxy(
        host=host,
        port=int(port or "443"),
        secret=secret,
        api_id=int(api_id) if api_id else None,
        api_hash=api_hash or None,
    )
    status = 200 if ok else 400
    return jsonify({"ok": ok, "message": message}), status


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
        "mtproto_host": request.form.get("mtproto_host", "").strip(),
        "mtproto_port": request.form.get("mtproto_port", "443").strip(),
        "mtproto_secret": request.form.get("mtproto_secret", "").strip(),
        "mtproto_dc_id": request.form.get("mtproto_dc_id", "").strip(),
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
    if current_settings["mtproto_host"] and current_settings["mtproto_secret"]:
        proxy = {
            "mode": "mtproto",
            "host": current_settings["mtproto_host"],
            "port": int(current_settings["mtproto_port"] or "443"),
            "secret": current_settings["mtproto_secret"],
            "dc_id": current_settings["mtproto_dc_id"] or None,
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
                "error": "Таймаут подключения к Telegram через MTProto. Проверьте host/port/secret и повторите.",
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
