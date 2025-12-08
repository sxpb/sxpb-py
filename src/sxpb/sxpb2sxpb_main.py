import argparse
import sys

from lark.exceptions import LarkError

from .exceptions import format_lark_error
from .parser import loads
from .serializer import dumps


def main():
    """Reformats SxPB data."""
    parser = argparse.ArgumentParser(description="Reformat Sxpb data.")
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
        help="Output Sxpb file (stdout if not specified)",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=1,
        help="Indentation level for Sxpb output",
    )
    parser.add_argument(
        "--validate_only",
        action="store_true",
        help="Parse the input file and exit without writing to output",
    )

    args = parser.parse_args()
    sxpb_content = args.infile.read()

    try:
        sxpb_data = loads(sxpb_content, precise=True)
        if not args.validate_only:
            formatted_sxpb = dumps(sxpb_data, indent=args.indent)
            args.outfile.write(formatted_sxpb)
            if not formatted_sxpb.endswith("\n"):
                args.outfile.write("\n")
    except LarkError as e:
        print("Validation failed:", file=sys.stderr)
        print(format_lark_error(e, sxpb_content), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred:\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
