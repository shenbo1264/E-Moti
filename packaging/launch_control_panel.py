from __future__ import annotations

import sys

from guanghe_companion import app as companion_app


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--demo-save" not in args and "--reset-demo-save" not in args:
        args.append("--demo-save")
    return companion_app.launch(["E-Moti", *args])


if __name__ == "__main__":
    raise SystemExit(main())
