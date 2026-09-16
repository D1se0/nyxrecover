"""python -m nyx → TUI; python -m nyx.cli → CLI (handled by packaging)."""
from nyx.nyxcore.tui import main

if __name__ == "__main__":
    main()
