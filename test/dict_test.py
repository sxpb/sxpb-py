from sxpb.parse import loads
from sxpb.serialize import dumps
from sxpb.types import SxpbDict, SxpbMesg
import textwrap


def test_dict_type():
    sxpb_string = textwrap.dedent("""
        (my_dict ()
         (key1 val1)
        )
    """)
    data = loads(sxpb_string, precise=True)
    assert isinstance(data, SxpbMesg)
    assert isinstance(data["my_dict"], SxpbDict)
    assert data["my_dict"]["key1"] == "val1"

    dumped = dumps(data, indent=1)
    assert "(my_dict ()\n" in dumped


def test_dict_toplevel():
    sxpb_string = textwrap.dedent("""
        ()
        (key1 val1)
    """)
    data = loads(sxpb_string, precise=True)
    assert isinstance(data, SxpbDict)
    assert data["key1"] == "val1"

    dumped = dumps(data, indent=1)
    assert dumped.startswith("()\n")


def test_dict_empty():
    sxpb_string = textwrap.dedent("""
        (my_dict ())
    """)
    data = loads(sxpb_string, precise=True)
    assert isinstance(data, SxpbMesg)
    assert isinstance(data["my_dict"], SxpbDict)
    assert len(data["my_dict"]) == 0

    dumped = dumps(data, indent=1)
    assert dumped.strip() == "(my_dict ())"


def test_dict_empty_toplevel():
    sxpb_string = textwrap.dedent("""
        ()
    """)
    data = loads(sxpb_string, precise=True)
    assert isinstance(data, SxpbDict)
    assert len(data) == 0

    dumped = dumps(data, indent=1)
    assert dumped.strip() == "()"


def test_dict_serialization():
    data = SxpbMesg({"a": SxpbDict({"b": 1})})

    assert dumps(data, indent=1) == "(a ()\n (b 1)\n)"
    assert dumps(data, indent=0) == "(a () (b 1))"
    assert dumps(data, indent=-1) == "(a()(b 1))"
