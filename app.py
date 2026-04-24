from __future__ import annotations

import csv
import io
import threading

from flask import Flask, Response, jsonify, render_template, request

from telegram_channel_finder import discover_channels_via_telegram, filter_channels

app = Flask(__name__)
PARSE_LOCK = threading.Lock()


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/parse")
def parse_channel_list():
    api_id_raw = request.form.get("api_id", "").strip()
    api_hash = request.form.get("api_hash", "").strip()
    phone = request.form.get("phone", "").strip()
    queries_raw = request.form.get("queries", "").strip()

    if not api_id_raw or not api_hash or not phone or not queries_raw:
        return jsonify({"ok": False, "error": "Заполните API ID, API HASH, телефон и поисковые запросы."}), 400

    required_category = request.form.get("category", "any")
    min_subscribers = int(request.form.get("min_subscribers", "500") or 500)
    require_comments_open = request.form.get("require_comments", "on") == "on"
    min_engagement_rate = float(request.form.get("min_engagement_rate", "2") or 2)
    min_recent_posts = int(request.form.get("min_recent_posts", "3") or 3)
    active_within_days = int(request.form.get("active_within_days", "14") or 14)
    max_channels = int(request.form.get("max_channels", "100") or 100)
    lookback_days = int(request.form.get("lookback_days", "30") or 30)

    search_queries = [q.strip() for q in queries_raw.split(",") if q.strip()]

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
        )
        filtered = filter_channels(
            discovered,
            required_category=required_category,
            min_subscribers=min_subscribers,
            require_comments_open=require_comments_open,
            min_engagement_rate=min_engagement_rate,
            min_recent_posts=min_recent_posts,
            active_within_days=active_within_days,
        )
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
    app.run(host="0.0.0.0", port=5000, debug=True)
