"""Shared test configuration — sets env vars before any app imports."""

import os

# Set before importing anything from local_scorer
os.environ.setdefault("GOOGLE_PLACES_API_KEY", "test-key-fake")
os.environ.setdefault("RAPIDAPI_KEY", "")
