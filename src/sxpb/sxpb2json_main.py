import argparse
import json
import sys

from .jsonutil import to_plain_types
from .parser import loads


def main():
    """Converts Sxpb to JSON."""
    parser = argparse.ArgumentParser(description="Convert Sxpb to JSON.")
    parser.add_argument(
        "infile",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Input Sxpb file (stdin if not specified)",
    )
    parser.add_argument(
        "outfile",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output JSON file (stdout if not specified)",
    )
    parser.add_argument("--indent", type=int, help="Indentation level for JSON output")
    parser.add_argument(
        "--sort-keys", action="store_true", help="Sort keys in JSON output"
    )

    args = parser.parse_args()

    try:
        sxpb_data = loads(args.infile.read())
        plain_data = to_plain_types(sxpb_data)

        json_kwargs = {
            "indent": args.indent,
            "sort_keys": args.sort_keys,
        }
        json.dump(plain_data, args.outfile, **json_kwargs)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
