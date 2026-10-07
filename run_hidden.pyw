"""Silent entry point for the background scheduled task.

pythonw.exe has no console, so print() output would vanish. This redirects it
to busy-bar.log beside the script, then hands off to main.py unchanged.

Installed by install-task.ps1. For interactive use, run main.py directly.
"""

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LOG = HERE / "busy-bar.log"

# Rotate once rather than letting months of logons grow the file unbounded.
MAX_BYTES = 1_000_000


def main():
    if LOG.exists() and LOG.stat().st_size > MAX_BYTES:
        LOG.replace(HERE / "busy-bar.log.old")

    with open(LOG, "a", buffering=1, encoding="utf-8") as stream:
        sys.stdout = stream
        sys.stderr = stream
        runpy.run_path(str(HERE / "main.py"), run_name="__main__")


if __name__ == "__main__":
    main()