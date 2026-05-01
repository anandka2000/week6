"""``shortstack-worker scripts ...`` subcommands."""

from __future__ import annotations

import json

import typer

from ..tasks import scripts as script_tasks

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command("generate")
def generate(trend_id: str = typer.Option(..., help="trend uuid")) -> None:
    """Generate (and persist) a script + draft video for a trend."""
    result = script_tasks.generate_script.run(trend_id)
    typer.echo(json.dumps(result, indent=2, default=str))
