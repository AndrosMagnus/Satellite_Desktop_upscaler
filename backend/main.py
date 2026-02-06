from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="Backend CLI placeholder.")
    parser.parse_args()
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
