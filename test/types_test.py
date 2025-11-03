from sxpb.parser import loads
from sxpb.types import SxpbDict, SxpbList, SxpbLone, SxpbMany


def test_to_dict_and_to_list():
    sxpb_data = SxpbDict(
        {
            "a": SxpbList([1, 2, 3]),
            "b": SxpbDict({"c": 4}),
            "d": SxpbLone({"e": 5}),
            "f": SxpbMany([SxpbLone({"value": 6})]),
        }
    )

    plain_data = sxpb_data.to_dict()

    assert isinstance(plain_data, dict)
    assert not isinstance(plain_data, SxpbDict)
    assert isinstance(plain_data["a"], list)
    assert not isinstance(plain_data["a"], SxpbList)
    assert isinstance(plain_data["b"], dict)
    assert not isinstance(plain_data["b"], SxpbDict)
    assert isinstance(plain_data["d"], dict)
    assert not isinstance(plain_data["d"], SxpbLone)
    assert isinstance(plain_data["f"], list)
    assert not isinstance(plain_data["f"], SxpbMany)


def test_loads_builtin_only():
    sxpb_string = """
    (a (b 1))
    (c (()) 2 3)
    """

    # Test with builtin_only=False (default)
    sxpb_data = loads(sxpb_string)
    assert isinstance(sxpb_data, SxpbDict)
    assert isinstance(sxpb_data["a"], SxpbDict)
    assert isinstance(sxpb_data["c"], SxpbList)

    # Test with builtin_only=True
    plain_data = loads(sxpb_string, builtin_only=True)
    assert isinstance(plain_data, dict)
    assert not isinstance(plain_data, SxpbDict)
    assert isinstance(plain_data["a"], dict)
    assert not isinstance(plain_data["a"], SxpbDict)
    assert isinstance(plain_data["c"], list)
    assert not isinstance(plain_data["c"], SxpbList)
