import argparse
import json
import sys
from contextlib import ExitStack

from .serializer import dumps


def main():
    """Converts JSON to Sxpb."""
    parser = argparse.ArgumentParser(description="Convert JSON to Sxpb.")
    parser.add_argument(
        "infile",
        nargs="?",
        default=None,
        help="Input JSON file (stdin if not specified)",
    )
    parser.add_argument(
        "outfile",
        nargs="?",
        default=None,
        help="Output Sxpb file (stdout if not specified)",
    )
    parser.add_argument(
        "--indent", type=int, default=1, help="Indentation level for Sxpb output"
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

            json_data = json.load(infile)
            sxpb_str = dumps(json_data, indent=args.indent)
            outfile.write(sxpb_str)
            if not sxpb_str.endswith("\n"):
                outfile.write("\n")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
