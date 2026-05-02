"""Operator CLI.

    uv run python -m shortstack_worker.cli trends fetch --niche ai-productivity
    uv run python -m shortstack_worker.cli trends cluster --niche ai-productivity
    uv run python -m shortstack_worker.cli trends pick --niche ai-productivity
    uv run python -m shortstack_worker.cli scripts generate --trend-id <uuid>
    uv run python -m shortstack_worker.cli assets generate --video-id <uuid>
"""

from __future__ import annotations

import typer

from .assets import app as assets_app
from .scripts import app as scripts_app
from .trends import app as trends_app

app = typer.Typer(no_args_is_help=True, add_completion=False)
app.add_typer(trends_app, name="trends")
app.add_typer(scripts_app, name="scripts")
app.add_typer(assets_app, name="assets")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
