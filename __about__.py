"""Root shim for the flat Hermes plugin loader — delegates to the package copy."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
from toolshed.__about__ import __version__  # noqa: E402
