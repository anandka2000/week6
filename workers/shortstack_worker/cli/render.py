"""``shortstack-worker render ...`` subcommands."""

from __future__ import annotations

import json

import typer

from ..tasks import render as render_tasks

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("video")
def video(video_id: str = typer.Option(..., help="video uuid (must be pending_render)")) -> None:
    """Run the Remotion render service for a video and wait for the mp4."""
    result = render_tasks.render_video.run(video_id)
    typer.echo(json.dumps(result, indent=2, default=str))
