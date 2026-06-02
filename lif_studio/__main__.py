"""Allow ``python -m lif_studio`` to launch the GUI."""

import sys

from .app import run

if __name__ == "__main__":
    sys.exit(run())
