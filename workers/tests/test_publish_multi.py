"""``publish_video_all`` task — fan-out + partial-failure tests.

Patches ``_run_single_publish`` so we never touch DB / S3 / publisher
HTTP. The seam exists specifically so this test can mock at the import
boundary as required by CLAUDE.md.
"""

from __future__ import annotations

from unittest.mock import patch

from shortstack_worker.tasks import publish as publish_tasks
from shortstack_worker.tasks.publish import publish_video_all


def test_publish_video_all_task_is_registered():
    assert publish_video_all.name == (
        "shortstack_worker.tasks.publish.publish_video_all"
    )


def test_publish_video_all_runs_each_platform_in_order():
    calls: list[tuple[str, str, str]] = []

    def fake(video_id: str, platform: str, visibility: str) -> dict:
        calls.append((video_id, platform, visibility))
        return {
            "video_id": video_id,
            "platform": platform,
            "external_id": f"ext-{platform}",
            "external_url": f"https://example.com/{platform}",
            "visibility": visibility,
        }

    with patch.object(publish_tasks, "_run_single_publish", side_effect=fake):
        out = publish_video_all.run(
            "vid-1",
            ["ig_reels", "tiktok", "x", "linkedin"],
            "unlisted",
        )

    assert [c[1] for c in calls] == ["ig_reels", "tiktok", "x", "linkedin"]
    assert all(c[0] == "vid-1" and c[2] == "unlisted" for c in calls)
    assert out["video_id"] == "vid-1"
    assert out["errors"] == []
    assert [r["platform"] for r in out["results"]] == [
        "ig_reels",
        "tiktok",
        "x",
        "linkedin",
    ]
    # The single-publish payload is merged into each result entry.
    assert out["results"][0]["external_id"] == "ext-ig_reels"


def test_publish_video_all_collects_per_platform_failures():
    def fake(video_id: str, platform: str, visibility: str) -> dict:
        if platform == "tiktok":
            raise RuntimeError("tiktok upstream is down")
        return {
            "video_id": video_id,
            "platform": platform,
            "external_id": f"ext-{platform}",
            "external_url": f"https://example.com/{platform}",
            "visibility": visibility,
        }

    with patch.object(publish_tasks, "_run_single_publish", side_effect=fake):
        out = publish_video_all.run(
            "vid-2",
            ["ig_reels", "tiktok", "x"],
            "unlisted",
        )

    # Successes for ig_reels and x; tiktok captured in errors.
    assert sorted(r["platform"] for r in out["results"]) == ["ig_reels", "x"]
    assert len(out["errors"]) == 1
    assert out["errors"][0]["platform"] == "tiktok"
    assert "tiktok upstream is down" in out["errors"][0]["error"]


def test_publish_video_all_continues_after_first_failure():
    """A failure on the first platform must not short-circuit the rest."""
    seen: list[str] = []

    def fake(video_id: str, platform: str, visibility: str) -> dict:
        seen.append(platform)
        if platform == "ig_reels":
            raise ValueError("missing buffer profile")
        return {
            "video_id": video_id,
            "platform": platform,
            "external_id": f"ext-{platform}",
            "external_url": f"https://example.com/{platform}",
            "visibility": visibility,
        }

    with patch.object(publish_tasks, "_run_single_publish", side_effect=fake):
        out = publish_video_all.run(
            "vid-3",
            ["ig_reels", "linkedin"],
            "public",
        )

    # Both platforms were attempted even though the first failed.
    assert seen == ["ig_reels", "linkedin"]
    assert [r["platform"] for r in out["results"]] == ["linkedin"]
    assert [e["platform"] for e in out["errors"]] == ["ig_reels"]


def test_publish_video_all_with_empty_platforms_returns_empty_lists():
    with patch.object(publish_tasks, "_run_single_publish") as mocked:
        out = publish_video_all.run("vid-4", [], "unlisted")
    mocked.assert_not_called()
    assert out == {"video_id": "vid-4", "results": [], "errors": []}
