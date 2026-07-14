"""Command-line interface for linting SxPB source."""

from .format_cli import parse_cli_args, run_lint


def main() -> int:
    args = parse_cli_args(
        prog="sxpb-lint",
        description="Check SxPB source without modifying it.",
        verb="lint",
    )
    return run_lint(args)


if __name__ == "__main__":
    raise SystemExit(main())
