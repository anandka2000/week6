"""TTS task pure-logic tests.

Only the narration composition helper is covered here; the celery task
itself touches Postgres + S3 + ElevenLabs and is exercised end-to-end via
the orchestrator integration test.
"""

# DB-integration test deferred -- requires a real Postgres + MinIO.

from __future__ import annotations

from shortstack_core.schemas import Scene, ScriptDraft
from shortstack_worker.tasks.tts import _compose_narration


def _draft(scenes: list[Scene]) -> ScriptDraft:
    total = sum(s.duration_sec for s in scenes)
    return ScriptDraft(
        hook=scenes[0].narration,
        scenes=scenes,
        cta="Follow for more.",
        total_duration_sec=total,
        prompt_version="scripts_v1",
        model="claude-sonnet-4-6",
    )


def _scene(index: int, narration: str, duration: float = 4.0) -> Scene:
    return Scene(
        index=index,
        narration=narration,
        on_screen_text="",
        visual_prompt="placeholder visual prompt",
        duration_sec=duration,
    )


def test_compose_narration_joins_with_period_space():
    draft = _draft(
        [
            _scene(0, "Hook line here", duration=2.5),
            _scene(1, "Second beat"),
            _scene(2, "Third beat"),
            _scene(3, "Fourth beat"),
        ]
    )
    assert _compose_narration(draft) == (
        "Hook line here. Second beat. Third beat. Fourth beat"
    )


def test_compose_narration_orders_by_scene_index():
    # Build scenes in non-monotonic input order; the helper must still emit
    # them by ``index`` ascending so scene 0 (the hook) leads.
    scenes = [
        _scene(2, "third"),
        _scene(0, "first", duration=2.5),
        _scene(3, "fourth"),
        _scene(1, "second"),
    ]
    draft = _draft(sorted(scenes, key=lambda s: s.index))
    # Re-shuffle the draft.scenes list to confirm the helper -- not the
    # validator -- is doing the ordering.
    draft = draft.model_copy(update={"scenes": scenes})

    assert _compose_narration(draft) == "first. second. third. fourth"


def test_compose_narration_hook_is_first_sentence():
    draft = _draft(
        [
            _scene(0, "Hook sentence", duration=2.5),
            _scene(1, "Body one"),
            _scene(2, "Body two"),
            _scene(3, "Body three"),
        ]
    )
    out = _compose_narration(draft)
    assert out.split(". ")[0] == "Hook sentence"
