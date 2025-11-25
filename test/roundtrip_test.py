import textwrap
import sxpb


def test_loads_and_dumps_roundtrip():
    s = textwrap.dedent("""
        (languages (())
         (()
          (name "Python (PEP 8)")
          (spaces 4)
         )
        )
    """)
    example = s.strip()
    data = sxpb.loads(example, precise=True)
    text = sxpb.dumps(data)
    assert text == example


def test_simple_roundtrip():
    example = "(key value)"
    data = sxpb.loads(example, precise=True)
    text = sxpb.dumps(data)
    assert text == example


def test_simple_content_roundtrip():
    s = textwrap.dedent("""
        (a 1)
        (b hello)
        (c +true)
        (d 1.23)
        (e "")
        (f (())
         hello
         world
        )
    """)
    example = s.strip()
    data = sxpb.loads(example, precise=True)
    text = sxpb.dumps(data)
    assert text == example


def test_loneof_content_roundtrip():
    s = textwrap.dedent("""
        ((bag_with paper) 2)
        ((fruit_as banana)
         (count 5)
         (ripeness 0.4)
        )
    """)
    example = s.strip()
    data = sxpb.loads(example, precise=True)
    text = sxpb.dumps(data)
    assert text == example


def test_manyof_content_roundtrip():
    # This is a simplified version of the manyof.sxpb file, formatted
    # to match the canonical output of the serializer.
    s = textwrap.dedent("""
        (identical_expressions (())
         (()
          (add (())
           (()
            (add (())
             (()
              (value 1)
             )
             (()
              (value 2)
             )
            )
           )
           (()
            (mul (())
             (()
              (value 3)
             )
             (()
              (value 4)
             )
            )
           )
           (()
            (neg (())
             (()
              (div (())
               (()
                (value 56)
               )
               (()
                (value 7)
               )
              )
             )
            )
           )
          )
         )
        )
        (empty_manyof (()))
        (another_empty_manyof (()))
        (empty_message)
    """)
    example = s.strip()
    data = sxpb.loads(example, precise=True)
    text = sxpb.dumps(data)
    assert text == example
