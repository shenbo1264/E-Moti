from __future__ import annotations

from dataclasses import dataclass

MAX_DIALOGUE_INPUT_LENGTH = 240


@dataclass(frozen=True, slots=True)
class DialogueRequest:
    text: str
    source: str = "desktop_pet"

    def normalized_text(self) -> str:
        if not isinstance(self.text, str):
            return ""
        normalized = "".join(" " if ord(char) < 32 or ord(char) == 127 else char for char in self.text)
        return normalized.strip()[:MAX_DIALOGUE_INPUT_LENGTH]

