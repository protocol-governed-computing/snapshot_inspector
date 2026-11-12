"""`python -m inspector` → the `si` CLI, so the tool runs without being installed."""
import sys

from inspector.cli import main

if __name__ == "__main__":
    sys.exit(main())
