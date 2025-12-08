import json
import textwrap
from collections import UserDict, UserList
from pathlib import Path

import pytest
import sxpb

CONTENT_DIR = Path(__file__).parent / "content"
CONTENT_FILES = [f.stem for f in CONTENT_DIR.glob("*.sxpb") if "pumpkin" not in f.stem]


def to_plain_types(data):
    if isinstance(data, UserDict):
        return {k: to_plain_types(v) for k, v in data.items()}
    if isinstance(data, UserList):
        return [to_plain_types(v) for v in data]
    return data


@pytest.mark.parametrize("name", CONTENT_FILES)
def test_sxpb_files_can_be_parsed_as_expected(name):
    sxpb_path = CONTENT_DIR / f"{name}.sxpb"
    json_path = CONTENT_DIR / f"{name}.json"

    # Standard parsing check against JSON (relaxed types)
    sxpb_data = sxpb.load(str(sxpb_path))
    json_data = json.loads(json_path.read_text())

    assert to_plain_types(sxpb_data) == json_data


@pytest.mark.parametrize("name", CONTENT_FILES)
def test_sxpb_roundtrip(name):
    sxpb_path = CONTENT_DIR / f"{name}.sxpb"

    # Strict roundtrip check (precise types)
    original_data = sxpb.load(str(sxpb_path), precise=True)
    serialized = sxpb.dumps(original_data)

    try:
        reloaded_data = sxpb.loads(serialized, precise=True)
    except Exception as e:
        print(f"FAILED SERIALIZATION FOR {name}:")
        print(serialized)
        raise e

    if reloaded_data != original_data:
        print(f"MISMATCH FOR {name}:")
        print("Expected:")
        print(original_data)
        print("Actual:")
        print(reloaded_data)
        print("Serialized output:")
        print(serialized)

    assert reloaded_data == original_data


def test_unquoted_array_string_parsing():
    sxpb_string = textwrap.dedent(
        """
        (my_array (())
         ("" this is a multi-word string)
         ("" so is this)
         these
         are
         not
        )
    """
    )
    expected_data = {
        "my_array": ["this is a multi-word string", "so is this", "these", "are", "not"]
    }
    parsed_data = sxpb.loads(sxpb_string)
    assert to_plain_types(parsed_data) == expected_data
