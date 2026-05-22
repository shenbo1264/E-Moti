from __future__ import annotations

from guanghe_companion import app as companion_app


def main() -> int:
    return companion_app.launch(["E-Moti", "--pet-mode", "--demo-save"])


if __name__ == "__main__":
    raise SystemExit(main())
