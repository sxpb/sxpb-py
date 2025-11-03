import argparse
import json
import sys

from .serializer import dumps


def main():
    """Converts JSON to Sxpb."""
    parser = argparse.ArgumentParser(description="Convert JSON to Sxpb.")
    parser.add_argument(
        "infile",
        nargs="?",
        type=argparse.FileType("r"),
        default=sys.stdin,
        help="Input JSON file (stdin if not specified)",
    )
    parser.add_argument(
        "outfile",
        nargs="?",
        type=argparse.FileType("w"),
        default=sys.stdout,
        help="Output Sxpb file (stdout if not specified)",
    )
    parser.add_argument(
        "--indent", type=int, default=1, help="Indentation level for Sxpb output"
    )

    args = parser.parse_args()

    try:
        json_data = json.load(args.infile)
        sxpb_str = dumps(json_data, indent=args.indent)
        args.outfile.write(sxpb_str)
        if not sxpb_str.endswith("\n"):
            args.outfile.write("\n")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
