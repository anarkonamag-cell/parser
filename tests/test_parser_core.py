from datetime import datetime, timezone

from parser_core import Post, _parse_views, filter_posts


def test_parse_views():
    assert _parse_views("1.2K") == 1200
    assert _parse_views("3M") == 3_000_000
    assert _parse_views("999") == 999


def test_filter_posts_by_keyword_date_and_views():
    posts = [
        Post("demo", "1", "hello ai", datetime(2026, 4, 1, tzinfo=timezone.utc), 1200, "u1"),
        Post("demo", "2", "hello world", datetime(2026, 4, 10, tzinfo=timezone.utc), 100, "u2"),
    ]

    result = filter_posts(
        posts,
        keyword="ai",
        date_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
        date_to=datetime(2026, 4, 5, tzinfo=timezone.utc),
        min_views=1000,
    )

    assert len(result) == 1
    assert result[0].message_id == "1"
