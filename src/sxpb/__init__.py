"""sxpb - read/write SxPB files (schema-agnostic)

Exports: loads, loads_file, dumps, dump, to_json, from_json
"""

from .parser import loads as loads, load as load
from .serializer import dumps as dumps, dump as dump
from .jsonutil import to_json, from_json
from .xml import to_xml
from .types import (
    SxpbDict as Dict,
    SxpbList as List,
    SxpbLone as Lone,
    SxpbMany as Many,
)

__all__ = [
    "loads",
    "load",
    "dumps",
    "dump",
    "to_json",
    "from_json",
    "to_xml",
    "Dict",
    "List",
    "Lone",
    "Many",
]
