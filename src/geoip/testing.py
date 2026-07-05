import sys

import pytest


def main() -> None:
    raise SystemExit(pytest.main(["-q", *sys.argv[1:]]))
