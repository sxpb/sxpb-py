import textwrap

import sxpb
from sxpb.types import SxpbLone, SxpbMany


def test_empty_serialization():
    data = {
        "empty_message": {},
        "empty_array": [],
        "array_with_empty_message": [{}],
        "empty_manyof": SxpbMany(),
        "empty_loneof": SxpbLone({"subkey": {}}),
    }
    s = textwrap.dedent("""
        (empty_message)
        (empty_array (()))
        (array_with_empty_message (())
         ()
        )
        ((empty_manyof))
        ((empty_loneof subkey))
    """)
    expected_output = s.strip()
    serialized_output = sxpb.dumps(data)
    assert serialized_output == expected_output
