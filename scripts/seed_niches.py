"""Seed the first niche.

Run after migrations:
    uv run python scripts/seed_niches.py
"""

from __future__ import annotations

import sys

from shortstack_core.db import Niche, session_scope
from shortstack_core.schemas import NichePersona


SEEDS = [
    {
        "slug": "ai-productivity",
        "name": "AI Productivity",
        "persona": NichePersona(
            brand="Trending Tech: AI Productivity",
            voice_id="REPLACE_WITH_ELEVENLABS_VOICE_ID",
            tone="energetic, no-fluff, contrarian-friendly",
            hook_styles=["pattern_interrupt", "curiosity_gap", "contrarian"],
            banned_topics=["politics", "celebrity gossip"],
            cta_template="Follow for one AI workflow per day.",
            subreddits=["productivity", "getdisciplined", "ChatGPT", "artificial"],
        ),
        "cost_cap_cents": 100,
        "daily_quota": 3,
    },
]


def main() -> int:
    with session_scope() as s:
        existing = {n.slug for n in s.query(Niche).all()}
        added = 0
        for seed in SEEDS:
            if seed["slug"] in existing:
                print(f"  skip  {seed['slug']} (already seeded)")
                continue
            n = Niche(
                slug=seed["slug"],
                name=seed["name"],
                persona_json=seed["persona"].model_dump(),
                cost_cap_cents=seed["cost_cap_cents"],
                daily_quota=seed["daily_quota"],
            )
            s.add(n)
            added += 1
            print(f"  add   {seed['slug']}")
        print(f"seeded {added} niche(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
