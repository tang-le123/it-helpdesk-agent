"""Run the API from PyCharm's right-click menu.

PyCharm's auto-created run configuration may use the script directory as the
working directory. This script switches to the project root first so that
``knowledge/``, ``.env`` and ``app`` all resolve correctly.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.asgi:app", host="127.0.0.1", port=8002, reload=True)
