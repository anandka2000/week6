"""Operator CLI.

    uv run python -m shortstack_worker.cli trends fetch --niche ai-productivity
    uv run python -m shortstack_worker.cli trends cluster --niche ai-productivity
    uv run python -m shortstack_worker.cli trends pick --niche ai-productivity
"""

from __future__ import annotations

import typer

from .trends import app as trends_app

app = typer.Typer(no_args_is_help=True, add_completion=False)
app.add_typer(trends_app, name="trends")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
