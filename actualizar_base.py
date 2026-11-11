"""Download official Excel files and regenerate a portable HTML snapshot."""
from backend.pipeline import run

if __name__ == "__main__":
    result = run()
    if result:
        raise SystemExit(result)
