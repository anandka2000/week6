"""Operator CLI.

    uv run python -m shortstack_worker.cli trends fetch --niche ai-productivity
    uv run python -m shortstack_worker.cli trends cluster --niche ai-productivity
    uv run python -m shortstack_worker.cli trends pick --niche ai-productivity
    uv run python -m shortstack_worker.cli scripts generate --trend-id <uuid>
    uv run python -m shortstack_worker.cli assets generate --video-id <uuid>
    uv run python -m shortstack_worker.cli render video --video-id <uuid>
    uv run python -m shortstack_worker.cli publish video --video-id <uuid>
    uv run python -m shortstack_worker.cli publish all --video-id <uuid> --platforms ig_reels,tiktok
    uv run python -m shortstack_worker.cli analytics snapshot --publication-id <uuid>
    uv run python -m shortstack_worker.cli analytics learnings --niche <slug>
    uv run python -m shortstack_worker.cli automation daily --niche <slug> [--max N]
    uv run python -m shortstack_worker.cli automation publish-approved --niche <slug>
"""

from __future__ import annotations

import typer

from .analytics import app as analytics_app
from .assets import app as assets_app
from .automation import app as automation_app
from .publish import app as publish_app
from .render import app as render_app
from .scripts import app as scripts_app
from .trends import app as trends_app

app = typer.Typer(no_args_is_help=True, add_completion=False)
app.add_typer(trends_app, name="trends")
app.add_typer(scripts_app, name="scripts")
app.add_typer(assets_app, name="assets")
app.add_typer(render_app, name="render")
app.add_typer(publish_app, name="publish")
app.add_typer(analytics_app, name="analytics")
app.add_typer(automation_app, name="automation")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
