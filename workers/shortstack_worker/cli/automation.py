"""``shortstack-worker automation ...`` subcommands."""

from __future__ import annotations

import json

import typer
from sqlalchemy import select

from shortstack_core.db import Niche, session_scope
from shortstack_core.enums import Platform

from ..tasks import automation as automation_tasks

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _niche_id_by_slug(slug: str) -> str:
    with session_scope() as s:
        n = s.execute(select(Niche).where(Niche.slug == slug)).scalar_one_or_none()
        if n is None:
            raise typer.BadParameter(f"niche slug not found: {slug}")
        return str(n.id)


@app.command("daily")
def daily(
    niche: str = typer.Option(..., help="niche slug"),
    max_videos: int | None = typer.Option(
        None, "--max", help="cap below niche.daily_quota for this run", min=0
    ),
) -> None:
    """Run today's pipeline for a niche: trends → script → assets → render
    until the quota is met or no more eligible trends remain.
    """
    result = automation_tasks.daily_pipeline.run(
        _niche_id_by_slug(niche), max_videos
    )
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command("publish-approved")
def publish_approved_cmd(
    niche: str = typer.Option(..., help="niche slug"),
    platform: str = typer.Option("youtube_shorts"),
    visibility: str = typer.Option("unlisted"),
) -> None:
    """Queue publish_video for every APPROVED video in this niche that
    doesn't yet have a Publication for the target platform."""
    valid = {p.value for p in Platform}
    if platform not in valid:
        raise typer.BadParameter(
            f"unknown platform slug: {platform}. valid: {', '.join(sorted(valid))}",
            param_hint="--platform",
        )
    if visibility not in {"unlisted", "public"}:
        raise typer.BadParameter(
            f"visibility must be 'unlisted' or 'public', got {visibility!r}",
            param_hint="--visibility",
        )
    result = automation_tasks.publish_approved.run(
        _niche_id_by_slug(niche), platform, visibility
    )
    typer.echo(json.dumps(result, indent=2, default=str))
