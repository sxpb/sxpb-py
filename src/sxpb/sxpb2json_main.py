import argparse
import json
import sys
from contextlib import ExitStack

from .jsonutil import to_plain_types
from .parse import loads


def main():
    """Converts Sxpb to JSON."""
    parser = argparse.ArgumentParser(description="Convert Sxpb to JSON.")
    parser.add_argument(
        "infile",
        nargs="?",
        default=None,
        help="Input Sxpb file (stdin if not specified)",
    )
    parser.add_argument(
        "outfile",
        nargs="?",
        default=None,
        help="Output JSON file (stdout if not specified)",
    )
    parser.add_argument("--indent", type=int, help="Indentation level for JSON output")
    parser.add_argument(
        "--sort-keys", action="store_true", help="Sort keys in JSON output"
    )

    args = parser.parse_args()

    try:
        with ExitStack() as stack:
            infile = (
                sys.stdin
                if args.infile in (None, "-")
                else stack.enter_context(open(args.infile, encoding="utf-8"))
            )
            outfile = (
                sys.stdout
                if args.outfile in (None, "-")
                else stack.enter_context(open(args.outfile, "w", encoding="utf-8"))
            )

            sxpb_data = loads(infile.read(), precise=True)
            plain_data = to_plain_types(sxpb_data)

            json_kwargs = {
                "indent": args.indent,
                "sort_keys": args.sort_keys,
            }
            json.dump(plain_data, outfile, **json_kwargs)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
