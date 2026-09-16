"""NyxRecover launcher — PyInstaller entrypoint.

Usage:
  NyxRecover.exe            → TUI (interactive dark interface)
  NyxRecover.exe --cli …    → CLI passthrough
"""
import os
import sys


def main():
    # PyInstaller bundles the package under sys._MEIPASS/nyx
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    if base not in sys.path:
        sys.path.insert(0, base)
    args = sys.argv[1:]
    if args and args[0] == "--cli":
        sys.argv = ["nyx"] + args[1:]
        from nyx.nyxcore.cli import main as cli_main
        cli_main()
    else:
        from nyx.nyxcore.tui import main as tui_main
        tui_main()


if __name__ == "__main__":
    main()
