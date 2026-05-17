from __future__ import annotations

from dataclasses import dataclass

from .character_pack import CharacterPack


@dataclass(frozen=True, slots=True)
class CharacterProfileExpressionContextProvider:
    character_pack: CharacterPack

    def __call__(self) -> dict[str, object]:
        return {
            "tool_results": [
                {
                    "source": "local_character_pack",
                    "title": f"{self.character_pack.name} | {self.character_pack.title}",
                    "summary": self.character_pack.description,
                },
                {
                    "source": "local_character_pack",
                    "title": "modes",
                    "summary": self._mode_summary(),
                },
            ]
        }

    def _mode_summary(self) -> str:
        parts = [
            f"{mode}: {self.character_pack.mode_descriptions[mode]}"
            for mode in self.character_pack.modes[:3]
            if mode in self.character_pack.mode_descriptions
        ]
        return " / ".join(parts)
