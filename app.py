from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from flask import Flask, Response, jsonify, render_template, request

from parser_core import fetch_channel_posts, filter_posts

app = Flask(__name__)


def _parse_datetime(value: str):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/check")
def check_channel():
    channel = request.form.get("channel", "")
    try:
        posts = fetch_channel_posts(channel)
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": f"Ошибка проверки: {exc}"}), 400

    latest = posts[0].date.isoformat() if posts else None
    return jsonify({"ok": True, "posts_found": len(posts), "latest_post": latest})


@app.post("/api/parse")
def parse_channel():
    channel = request.form.get("channel", "")
    keyword = request.form.get("keyword", "")
    date_from = _parse_datetime(request.form.get("date_from", ""))
    date_to = _parse_datetime(request.form.get("date_to", ""))

    min_views_raw = request.form.get("min_views", "").strip()
    min_views = int(min_views_raw) if min_views_raw else None

    try:
        posts = fetch_channel_posts(channel)
        filtered = filter_posts(
            posts,
            keyword=keyword,
            date_from=date_from,
            date_to=date_to,
            min_views=min_views,
        )
    except Exception as exc:  # pragma: no cover
        return jsonify({"ok": False, "error": f"Ошибка парсинга: {exc}"}), 400

    return jsonify(
        {
            "ok": True,
            "count": len(filtered),
            "items": [
                {
                    "channel": p.channel,
                    "message_id": p.message_id,
                    "text": p.text,
                    "date": p.date.isoformat(),
                    "views": p.views,
                    "url": p.url,
                }
                for p in filtered
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
        fieldnames=["channel", "message_id", "date", "views", "url", "text"],
    )
    writer.writeheader()
    for item in items:
        writer.writerow(
            {
                "channel": item.get("channel", ""),
                "message_id": item.get("message_id", ""),
                "date": item.get("date", ""),
                "views": item.get("views", ""),
                "url": item.get("url", ""),
                "text": item.get("text", ""),
            }
        )

    csv_data = buffer.getvalue()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=telegram_posts.csv"},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
