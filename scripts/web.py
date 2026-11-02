"""Start the Vite dev server.

Used by the PyCharm run configuration "Web (vite)" so the frontend can be
started from the IDE without opening a separate terminal.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    frontend = root / "frontend"
    return subprocess.call(
        ["npm.cmd", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"],
        cwd=frontend,
    )


if __name__ == "__main__":
    raise SystemExit(main())
