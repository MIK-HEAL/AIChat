"""Launcher for the refactored desktop-pet app.

This file provides a single main() entry that delegates to src.app.main().
"""

from __future__ import annotations

import sys


def main() -> int:
    # run the application from src.app
    from src.app import main as app_main

    return app_main()


if __name__ == '__main__':
    sys.exit(main())
