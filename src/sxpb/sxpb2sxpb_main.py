import argparse
import sys
from contextlib import ExitStack

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
        default=None,
        help="Input Sxpb file (stdin if not specified)",
    )
    parser.add_argument(
        "outfile",
        nargs="?",
        default=None,
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

            sxpb_content = infile.read()
            sxpb_data = loads(sxpb_content, precise=True)
            if not args.validate_only:
                formatted_sxpb = dumps(sxpb_data, indent=args.indent)
                outfile.write(formatted_sxpb)
                if not formatted_sxpb.endswith("\n"):
                    outfile.write("\n")
    except LarkError as e:
        print("Validation failed:", file=sys.stderr)
        print(format_lark_error(e, sxpb_content), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred:\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
