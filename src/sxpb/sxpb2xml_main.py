import argparse

from . import load, to_xml
from .jsonutil import to_plain_types


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("sxpb_file")
    args = parser.parse_args()
    data = load(args.sxpb_file)
    plain_data = to_plain_types(data)
    xml_data = to_xml(plain_data)
    print(xml_data)


if __name__ == "__main__":
    main()
