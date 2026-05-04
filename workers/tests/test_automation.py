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


def test_celery_app_registers_automation_tasks_on_worker_startup():
    """Regression guard for the QA9 critical finding: the worker calls
    ``app.loader.import_default_modules()`` on startup, which walks the
    ``include=`` list. If automation isn't in that list every beat-fired
    automation task raises NotRegistered at runtime.

    Pre-fix: this assertion failed (0 automation tasks registered). The
    bug was invisible to a normal `pytest` run because importing the
    test module pulls in tasks/automation.py separately.
    """
    from shortstack_worker.celery_app import app as celery_app

    # Force the same import path the worker takes on startup.
    celery_app.loader.import_default_modules()

    auto_tasks = {t for t in celery_app.tasks if "shortstack_worker.tasks.automation" in t}
    assert "shortstack_worker.tasks.automation.daily_pipeline_all" in auto_tasks
    assert "shortstack_worker.tasks.automation.publish_approved_all" in auto_tasks

    # Also catch the parallel Phase-6 regression that hit analytics.
    analytics_tasks = {t for t in celery_app.tasks if "shortstack_worker.tasks.analytics" in t}
    assert "shortstack_worker.tasks.analytics.nightly_catchup" in analytics_tasks
    assert "shortstack_worker.tasks.analytics.weekly_learnings_all" in analytics_tasks


def test_automation_tasks_route_to_analytics_queue():
    """Automation orchestrators are low-priority cron work; they share the
    analytics queue rather than competing with user-critical-path tasks."""
    from shortstack_core.enums import CostKind  # noqa: F401  (sanity import)

    from shortstack_worker.celery_app import app as celery_app
    from shortstack_worker.queues import Queue

    routes = celery_app.conf.task_routes
    assert "shortstack_worker.tasks.automation.*" in routes
    assert routes["shortstack_worker.tasks.automation.*"]["queue"] == Queue.ANALYTICS.value
