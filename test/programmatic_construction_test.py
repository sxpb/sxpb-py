import textwrap

from sxpb.serialize import dumps
from sxpb.types import SxpbList, SxpbMesg


def test_programmatic_construction():
    holidays = SxpbMesg(
        {
            "description": "My favorite holidays in 2025",
            "year": 2025,
            "holidays": SxpbList(
                [
                    SxpbMesg(
                        {
                            "month": "January",
                            "day": 1,
                            "name": "New Year's Day",
                            "activity": "Watch the Rose Parade",
                        }
                    ),
                    SxpbMesg(
                        {
                            "month": "October",
                            "day": 31,
                            "name": "Halloween",
                            "activity": "Carve pumpkins",
                        }
                    ),
                    SxpbMesg(
                        {
                            "month": "December",
                            "day": 25,
                            "name": "Christmas",
                            "activity": "Decorate the tree",
                        }
                    ),
                ]
            ),
        }
    )

    generated_sxpb = dumps(holidays)

    expected_sxpb = textwrap.dedent(
        """
        (description My favorite holidays in 2025)
        (year 2025)
        (holidays (())
         (()
          (month January)
          (day 1)
          (name New Year's Day)
          (activity Watch the Rose Parade)
         )
         (()
          (month October)
          (day 31)
          (name Halloween)
          (activity Carve pumpkins)
         )
         (()
          (month December)
          (day 25)
          (name Christmas)
          (activity Decorate the tree)
         )
        )
        """
    ).strip()

    assert generated_sxpb == expected_sxpb


def test_non_ascii_bare_strings():
    data = {"key": "ação"}
    expected_sxpb = "(key ação)"
    generated_sxpb = dumps(data)
    assert generated_sxpb == expected_sxpb


def test_strings_that_must_be_quoted():
    # These strings should be quoted because they do not have a valid BARE prefix
    # or contain illegal characters.
    test_cases = {
        "+foo": '(key "+foo")',
        "123": '(key "123")',
        ".5": '(key ".5")',
        "+true": '(key "+true")',
        "+false": '(key "+false")',
        "-.": '(key "-.")',
    }

    for input_str, expected_sxpb in test_cases.items():
        data = {"key": input_str}
        generated_sxpb = dumps(data)
        assert generated_sxpb == expected_sxpb, f"Failed for input: {input_str}"


def test_array_of_single_word_strings():
    data = {"key": ["hello", "world"]}
    expected_sxpb = textwrap.dedent(
        """
        (key (())
         hello
         world
        )
        """
    ).strip()
    generated_sxpb = dumps(data)
    assert generated_sxpb == expected_sxpb


def test_array_of_multi_word_strings():
    data = {"key": ["hello world", "foo bar"]}
    expected_sxpb = textwrap.dedent(
        """
        (key (())
         "hello world"
         "foo bar"
        )
        """
    ).strip()
    generated_sxpb = dumps(data)
    assert generated_sxpb == expected_sxpb


def test_strings_that_can_be_bare():
    # These strings should NOT be quoted.
    test_cases = {
        "ação": "(key ação)",
        "--foo": "(key --foo)",
        "foo-bar": "(key foo-bar)",
        ".": "(key .)",
        "-": "(key -)",
        "--": "(key --)",
        "hello world": "(key hello world)",
    }

    for input_str, expected_sxpb in test_cases.items():
        data = {"key": input_str}
        generated_sxpb = dumps(data)
        assert generated_sxpb == expected_sxpb, f"Failed for input: {input_str}"
