from sxpb.parser import loads
from sxpb.types import SxpbList, SxpbLone, SxpbMany, SxpbMesg


def test_to_dict_and_to_list():
    sxpb_data = SxpbMesg(
        {
            "a": SxpbList([1, 2, 3]),
            "b": SxpbMesg({"c": 4}),
            "d": SxpbLone({"e": 5}),
            "f": SxpbMany([SxpbLone({"value": 6})]),
        }
    )

    plain_data = sxpb_data.to_dict()

    assert isinstance(plain_data, dict)
    assert not isinstance(plain_data, SxpbMesg)
    assert isinstance(plain_data["a"], list)
    assert not isinstance(plain_data["a"], SxpbList)
    assert isinstance(plain_data["b"], dict)
    assert not isinstance(plain_data["b"], SxpbMesg)
    assert isinstance(plain_data["d"], dict)
    assert not isinstance(plain_data["d"], SxpbLone)
    assert isinstance(plain_data["f"], list)
    assert not isinstance(plain_data["f"], SxpbMany)


def test_loads_precise():
    sxpb_string = """
    (a (b 1))
    (c (()) 2 3)
    """

    # Test with precise=False (default)
    plain_data = loads(sxpb_string)
    assert isinstance(plain_data, dict)
    assert not isinstance(plain_data, SxpbMesg)
    assert isinstance(plain_data["a"], dict)
    assert not isinstance(plain_data["a"], SxpbMesg)
    assert isinstance(plain_data["c"], list)
    assert not isinstance(plain_data["c"], SxpbList)

    # Test with precise=True
    sxpb_data = loads(sxpb_string, precise=True)
    assert isinstance(sxpb_data, SxpbMesg)
    assert isinstance(sxpb_data["a"], SxpbMesg)
    assert isinstance(sxpb_data["c"], SxpbList)
