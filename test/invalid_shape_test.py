import pytest

from sxpb import SxpbParseError, parse


@pytest.mark.parametrize("precise", [False, True])
@pytest.mark.parametrize(
    "source",
    [
        "(a 1) () (b 2)",
        "(outer (a 1) () (b 2))",
    ],
)
def test_rejects_anonymous_empty_message_fields(source, precise):
    with pytest.raises(SxpbParseError, match="Unexpected empty message"):
        parse.loads(source, precise=precise)


@pytest.mark.parametrize("precise", [False, True])
@pytest.mark.parametrize(
    "source",
    [
        "(a ((()) 1)",
        "(a ((()) 1))",
    ],
)
def test_rejects_parenthesized_array_values(source, precise):
    with pytest.raises(SxpbParseError):
        parse.loads(source, precise=precise)


@pytest.mark.parametrize("precise", [False, True])
def test_rejects_bare_nest_discriminator_as_nest_item(precise):
    with pytest.raises(SxpbParseError):
        parse.loads('(n ("") (""))', precise=precise)


def test_related_canonical_forms_remain_valid():
    assert parse.loads("(a (()) 1)") == {"a": [1]}
    assert parse.loads('(n ("") "" tail)') == {"n": ["", "tail"]}
