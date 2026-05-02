"""``shortstack-worker publish ...`` subcommands."""

from __future__ import annotations

import json

import typer

from ..tasks import publish as publish_tasks

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("video")
def video(
    video_id: str = typer.Option(..., help="video uuid (must be approved)"),
    platform: str = typer.Option("youtube_shorts", help="platform slug"),
    visibility: str = typer.Option("unlisted", help="unlisted | public"),
) -> None:
    """Upload an approved video to the named platform."""
    result = publish_tasks.publish_video.run(video_id, platform, visibility)
    typer.echo(json.dumps(result, indent=2, default=str))
