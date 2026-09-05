"""Thin entrypoint — real code lives in src/. Keeps `python server.py` working."""
import os

import uvicorn

from src.app import app  # noqa: F401 — re-exported for `python server.py` and tests

# Back-compat: some scripts import TOOLS / HANDLERS from server.py
from src.app import HANDLERS  # noqa: F401
from src.tools import TOOLS  # noqa: F401

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
