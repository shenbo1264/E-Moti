from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TEXT = (
    "C:" + "\\Users\\",
    "D:" + "\\",
    "199" + "70",
    "学工" + "文档",
    "首" + "选",
    "_Shinsekai" + "_latest",
    "_VPet" + "_latest",
    "AI" + "不用看" + ".md",
)
TEXT_SUFFIXES = {
    ".bat",
    ".cfg",
    ".cmd",
    ".ini",
    ".iss",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
TEXT_NAMES = {".gitignore"}
REQUIRED_GITIGNORE_PATTERNS = (
    ".env",
    ".env.*",
    "generated/",
    "character_packs/",
    "tmp/live2d_research/",
    "tmp/liveportrait_research/",
    "data/companion_save.json",
    "data/companion_demo_save.json",
    "data/dialogue_history.json",
    "artifacts/simulation/",
    "artifacts/llm_smoke/",
    "artifacts/character-pack-status*.json",
    "artifacts/character-pack-status*.md",
    "artifacts/release-readiness*.json",
    "artifacts/release-readiness*.md",
    "artifacts/portrait-video-frame-normalization*.json",
    "artifacts/portrait-video-frame-preflight*.json",
    "artifacts/portrait-video-frame-qa*.json",
    "artifacts/portrait-video-frame-qa*.png",
    "artifacts/liveportrait-preflight*.json",
    "artifacts/liveportrait-preflight*.md",
    "artifacts/portrait-candidate*.png",
    "artifacts/portrait-candidate*/",
    "artifacts/windows-build-validation*.json",
    "*.key",
)


def _tracked_files() -> list[Path]:
    from subprocess import check_output

    output = check_output(["git", "ls-files"], cwd=REPO_ROOT, text=True, encoding="utf-8")
    return [REPO_ROOT / line for line in output.splitlines() if line]


def test_tracked_text_files_do_not_expose_local_paths_or_private_note_names() -> None:
    leaks: list[str] = []
    for path in _tracked_files():
        if not path.exists():
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in TEXT_NAMES:
            continue
        text = path.read_text(encoding="utf-8-sig")
        relative = path.relative_to(REPO_ROOT).as_posix()
        for token in FORBIDDEN_TEXT:
            if token in text:
                leaks.append(f"{relative}: {token}")

    assert leaks == []


def test_gitignore_covers_local_secrets_and_generation_artifacts() -> None:
    patterns = set((REPO_ROOT / ".gitignore").read_text(encoding="utf-8-sig").splitlines())

    missing = [pattern for pattern in REQUIRED_GITIGNORE_PATTERNS if pattern not in patterns]

    assert missing == []
