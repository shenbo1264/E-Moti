"""Fit complete evidence objects into the existing provider prompt limit."""
from __future__ import annotations

import json

from .memory_prompt_budget import trim_memory_evidence, trim_memory_metadata, trim_profile


def fit_prompt(lines: list[str], *, limit: int) -> str:
    """Drop optional/low-ranked context, never slice a fact or JSON document.

    Keep stable identity and the highest ranked memory ahead of extra profile
    values and redundant chapters. Unknown is preferable to a truncated claim.
    """
    prefixes = ("emotional_memory: ", "persona: ", "plugin_context (transient, not shared memories): ")
    slots = {prefix: next((i for i, line in enumerate(lines) if line.startswith(prefix)), -1) for prefix in prefixes}
    data = {prefix: json.loads(lines[index][len(prefix):]) if index >= 0 else {} for prefix, index in slots.items()}
    def render() -> str:
        for prefix, index in slots.items():
            if index >= 0:
                lines[index] = prefix + json.dumps(data[prefix], ensure_ascii=False, separators=(",", ":"))
        return "\n".join(lines)
    text = render()
    while len(text) > limit:
        memory, persona, plugin = (data[prefix] for prefix in prefixes)
        persona_lists = [value for key, value in persona.items() if isinstance(value, list) and key != "boundaries"]
        if "relationship_development" in memory:
            memory.pop("relationship_development")
        elif plugin:
            plugin.pop(next(reversed(plugin)))
        elif "relationship_chapter" in memory:
            memory.pop("relationship_chapter")
        elif trim_profile(memory, keep_each=2):
            pass
        elif any(persona_lists):
            max(persona_lists, key=lambda value: len(json.dumps(value, ensure_ascii=False))).pop()
        elif trim_memory_evidence(memory, preserve_one=True):
            pass
        else:
            # Legacy or extremely verbose external/profile material is optional.
            candidates = [i for i, line in enumerate(lines) if line.startswith((
                "recent_dialogue: ", "recent_memory: ", "long_term_memory: ", "只读外部线索：", "只读屏幕观察："))
                and len(line) > 25]
            if candidates:
                lines[max(candidates, key=lambda i: len(lines[i]))] = ""
            elif trim_profile(memory, include_boundaries=True):
                pass
            elif trim_memory_evidence(memory):
                pass
            elif trim_memory_metadata(memory):
                pass
            else:
                # Authored persona boundaries and identity are required just
                # like fixed policy. Never publish a prompt that silently drops
                # them to make room; the caller reports the budget failure.
                raise ValueError("fixed expression policy and required persona exceed prompt budget")
        text = render()
    return text
