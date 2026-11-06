"""Root entrypoint for hosts that look for main.py at the project root (for example Vercel). The application lives in the `app` package."""
from app.main import app  # noqa: F401
