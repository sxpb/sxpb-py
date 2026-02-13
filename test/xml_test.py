from pathlib import Path
import sxpb

CONTENT_DIR = Path(__file__).parent / "content"


def test_pumpkin_xml_serialization():
    sxpb_path = CONTENT_DIR / "pumpkin.sxpb"
    svg_path = CONTENT_DIR / "pumpkin.svg"

    sxpb_data = sxpb.load(str(sxpb_path), precise=True)
    from sxpb.types import SxpbMesg

    assert isinstance(sxpb_data, SxpbMesg)
    xml_output = sxpb.to_xml(sxpb_data)

    expected_svg = svg_path.read_text()

    assert xml_output.strip() == expected_svg.strip()
