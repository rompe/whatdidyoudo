#!/usr/bin/env python
"""Run whatdidyoudo in debug mode."""

import os

from whatdidyoudo import app


def main() -> None:
    """Run in debug mode."""
    app.static_dir = os.path.join(os.path.dirname(__file__), 'static_dir')
    app.app.run(host="0.0.0.0", debug=True)


if __name__ == "__main__":
    main()
