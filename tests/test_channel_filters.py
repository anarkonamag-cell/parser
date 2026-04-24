from datetime import datetime, timedelta, timezone

from telegram_channel_finder import ChannelInfo, filter_channels


def test_filter_channels_matches_required_rules():
    now = datetime.now(timezone.utc)
    channels = [
        ChannelInfo(
            title="A",
            username="@a",
            subscribers=1200,
            comments_enabled=True,
            category="tech",
            recent_posts=7,
            avg_views=500,
            engagement_rate=12.0,
            last_post_date=now - timedelta(days=1),
        ),
        ChannelInfo(
            title="B",
            username="@b",
            subscribers=400,
            comments_enabled=True,
            category="tech",
            recent_posts=20,
            avg_views=200,
            engagement_rate=9.0,
            last_post_date=now,
        ),
    ]

    filtered = filter_channels(
        channels,
        required_category="tech",
        min_subscribers=500,
        require_comments_open=True,
        min_engagement_rate=2.0,
        min_recent_posts=3,
        active_within_days=14,
    )

    assert len(filtered) == 1
    assert filtered[0].username == "@a"
