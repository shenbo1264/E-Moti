from __future__ import annotations


def distribution_warning_for_boundary(distribution_boundary: str) -> str:
    if distribution_boundary == "private_local_fanwork":
        return "Private fanwork stays local; do not distribute, and it must not be redistributed without rights."
    if distribution_boundary == "local_ugc_only":
        return "Local UGC stays local until provenance, license, and rights review are complete."
    if distribution_boundary == "shareable_after_review":
        return "Shareable after review means publish only after provenance, license, QA, and rights checks."
    return "Distribution boundary is unknown; keep this pack local until rights are reviewed."
