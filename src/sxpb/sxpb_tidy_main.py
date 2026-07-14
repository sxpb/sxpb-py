"""Command-line interface for tidying SxPB source."""

from .format_cli import parse_cli_args, run_tidy


def main() -> int:
    args = parse_cli_args(
        prog="sxpb-tidy",
        description="Tidy SxPB source without discarding comments.",
        verb="tidy",
    )
    return run_tidy(args)


if __name__ == "__main__":
    raise SystemExit(main())
