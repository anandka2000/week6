from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Scene(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    index: int = Field(ge=0)
    narration: str = Field(min_length=1)
    on_screen_text: str = Field(default="")
    visual_prompt: str = Field(min_length=1)
    duration_sec: float = Field(ge=2.0, le=6.0)


class ScriptDraft(BaseModel):
    """Full output of script generation. Validated before assets run."""

    model_config = ConfigDict(from_attributes=True)

    hook: str = Field(min_length=1)
    scenes: list[Scene] = Field(min_length=4, max_length=10)
    cta: str = Field(min_length=1)
    total_duration_sec: float = Field(le=55.0)
    prompt_version: str
    model: str

    @field_validator("hook")
    @classmethod
    def hook_word_limit(cls, v: str) -> str:
        if len(v.split()) > 15:
            raise ValueError("hook must be <= 15 words")
        return v

    @model_validator(mode="after")
    def scene_indices_contiguous(self) -> "ScriptDraft":
        for i, scene in enumerate(self.scenes):
            if scene.index != i:
                raise ValueError(f"scene index {scene.index} != position {i}")
        actual = sum(s.duration_sec for s in self.scenes)
        if abs(actual - self.total_duration_sec) > 0.5:
            raise ValueError(
                f"total_duration_sec={self.total_duration_sec} disagrees with sum={actual}"
            )
        return self

    @model_validator(mode="after")
    def scene_zero_is_hook(self) -> "ScriptDraft":
        """Scene 0 carries the hook and must fit in the first 3 seconds."""
        s0 = self.scenes[0]
        if s0.duration_sec > 3.0:
            raise ValueError(
                f"scene 0 duration_sec={s0.duration_sec} must be <= 3.0 "
                "(the hook plays in the first 3 seconds)"
            )
        n_words = len(s0.narration.split())
        if n_words > 10:
            raise ValueError(
                f"scene 0 narration is {n_words} words; must be <= 10 to fit in 3 seconds"
            )
        return self
