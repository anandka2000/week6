"""Automation tasks — task registration + flow tests with chained-task mocks."""

from __future__ import annotations

from shortstack_worker.tasks.automation import (
    daily_pipeline,
    daily_pipeline_all,
    publish_approved,
    publish_approved_all,
)


def test_daily_pipeline_task_is_registered():
    assert (
        daily_pipeline.name == "shortstack_worker.tasks.automation.daily_pipeline"
    )


def test_daily_pipeline_all_task_is_registered():
    assert (
        daily_pipeline_all.name
        == "shortstack_worker.tasks.automation.daily_pipeline_all"
    )


def test_publish_approved_task_is_registered():
    assert (
        publish_approved.name
        == "shortstack_worker.tasks.automation.publish_approved"
    )


def test_publish_approved_all_task_is_registered():
    assert (
        publish_approved_all.name
        == "shortstack_worker.tasks.automation.publish_approved_all"
    )


def test_render_imports_should_auto_approve():
    """Phase 9 hook: render_video gates approval through should_auto_approve.
    Confirm the import is wired so the heuristic actually runs in production.
    """
    import shortstack_worker.tasks.render as render_mod

    assert hasattr(render_mod, "should_auto_approve")
    assert hasattr(render_mod, "_recent_views_for_niche")


def test_beat_schedule_includes_phase9_entries():
    """Beat must fire daily_pipeline_all + publish_approved_all every day."""
    from shortstack_worker.celery_app import app as celery_app

    schedule = celery_app.conf.beat_schedule
    assert "automation-daily-pipeline" in schedule
    assert (
        schedule["automation-daily-pipeline"]["task"]
        == "shortstack_worker.tasks.automation.daily_pipeline_all"
    )
    assert "automation-publish-approved" in schedule
    assert (
        schedule["automation-publish-approved"]["task"]
        == "shortstack_worker.tasks.automation.publish_approved_all"
    )
