"""``shortstack-worker assets ...`` subcommands."""

from __future__ import annotations

import json

import typer

from ..tasks import assets as asset_tasks

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("generate")
def generate(video_id: str = typer.Option(..., help="video uuid")) -> None:
    """Run visuals -> tts -> captions for a video, in order."""
    result = asset_tasks.generate_assets.run(video_id)
    typer.echo(json.dumps(result, indent=2, default=str))
