from __future__ import annotations


def distribution_warning_for_boundary(distribution_boundary: str) -> str:
    if distribution_boundary == "private_local_fanwork":
        return "Non-commercial fanwork UGC; public sharing is allowed for this demo route, keep a source note with the pack."
    if distribution_boundary == "local_ugc_only":
        return "Local UGC can be shared in the non-commercial demo route after basic QA; keep provenance with the pack."
    if distribution_boundary == "shareable_after_review":
        return "Shareable pack; publish after basic QA and provenance notes are present."
    return "Distribution boundary is unknown; keep provenance notes with the pack before sharing."
