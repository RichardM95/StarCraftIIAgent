"""Synthetic-fixture tests for the strict Warcraft SYLK parser.

These tests use in-memory byte fixtures only; they do not read maps, the
filesystem or the network.  They were not executed as part of authoring.
"""

import codecs
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from sc2_mcp.errors import SC2Error  # noqa: E402
from sc2_mcp.war3_slk import parse_slk_bytes  # noqa: E402


def _slk(*lines: str) -> bytes:
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def test_first_char_preserved_and_y_inherited():
    data = _slk(
        "ID;PWXL;N;E",
        "B;X3;Y3;D0",
        'C;X1;Y1;K"unitID"',
        'C;X2;Y1;K"movetp"',
        'C;X3;Y1;K"targType"',
        'C;X1;Y2;K"amg"',
        'C;X2;K"foot"',
        'C;X3;K"ground"',
        'C;X1;Y3;K"hfoo"',
        'C;X2;K"foot"',
        'C;X3;K"ground"',
        "E",
    )
    result = parse_slk_bytes(data, source="synthetic.slk")
    assert result["encoding"] == "utf-8"
    assert result["columns"] == ["unitID", "movetp", "targType"]
    assert result["rows"] == [
        {"unitID": "amg", "movetp": "foot", "targType": "ground"},
        {"unitID": "hfoo", "movetp": "foot", "targType": "ground"},
    ]
    assert result["cell_count"] == 9


def test_x_inherited_when_only_y_given():
    data = _slk(
        'C;X1;Y1;K"unitID"',
        'C;X2;Y1;K"movetp"',
        'C;X1;Y2;K"amg"',
        'C;Y3;K"hfoo"',
    )
    result = parse_slk_bytes(data)
    assert result["columns"] == ["unitID", "movetp"]
    assert result["rows"] == [{"unitID": "amg"}, {"unitID": "hfoo"}]


def test_semicolon_inside_quotes():
    data = _slk(
        'C;X1;Y1;K"unitID"',
        'C;X2;Y1;K"comment"',
        'C;X1;Y2;K"hfoo"',
        'C;X2;Y2;K"a;b;c"',
    )
    result = parse_slk_bytes(data)
    assert result["rows"] == [{"unitID": "hfoo", "comment": "a;b;c"}]


def test_doubled_quote_escape():
    data = _slk(
        'C;X1;Y1;K"unitID"',
        'C;X2;Y1;K"comment"',
        'C;X1;Y2;K"hfoo"',
        'C;X2;Y2;K"say ""hi"""',
    )
    result = parse_slk_bytes(data)
    assert result["rows"] == [{"unitID": "hfoo", "comment": 'say "hi"'}]


def test_backslash_quote_escape():
    data = _slk(
        'C;X1;Y1;K"unitID"',
        'C;X2;Y1;K"comment"',
        'C;X1;Y2;K"hfoo"',
        'C;X2;Y2;K"say \\"hi\\""',
    )
    result = parse_slk_bytes(data)
    assert result["rows"] == [{"unitID": "hfoo", "comment": 'say "hi"'}]


def test_numbers_keep_original_text():
    data = _slk(
        'C;X1;Y1;K"goldCost"',
        'C;X2;Y1;K"ratio"',
        "C;X1;Y2;K-1.5",
        "C;X2;Y2;K0.7500",
        "C;X1;Y3;K+42",
    )
    result = parse_slk_bytes(data)
    assert result["rows"] == [
        {"goldCost": "-1.5", "ratio": "0.7500"},
        {"goldCost": "+42"},
    ]


def test_non_c_records_are_ignored():
    data = _slk(
        "ID;PWXL;N;E",
        "B;X2;Y2;D0",
        "F;P0;DG0G8;M255",
        "O;L;D;V0;K0",
        "E",
        'C;X1;Y1;K"unitID"',
        'C;X1;Y2;K"amg"',
    )
    result = parse_slk_bytes(data)
    assert result["columns"] == ["unitID"]
    assert result["rows"] == [{"unitID": "amg"}]
    assert result["cell_count"] == 2


def test_utf8_bom_encoding():
    data = codecs.BOM_UTF8 + 'C;X1;Y1;K"unitID"\r\nC;X1;Y2;K"amg"\r\n'.encode("utf-8")
    result = parse_slk_bytes(data)
    assert result["encoding"] == "utf-8-sig"
    assert result["rows"] == [{"unitID": "amg"}]


def test_gb18030_fallback():
    text = 'C;X1;Y1;K"unitID"\r\nC;X1;Y2;K"步兵"\r\n'
    data = text.encode("gb18030")
    result = parse_slk_bytes(data)
    assert result["encoding"] == "gb18030"
    assert result["rows"] == [{"unitID": "步兵"}]


def test_invalid_encoding_raises():
    with pytest.raises(SC2Error) as excinfo:
        parse_slk_bytes(b"\xff\xfe\xfd", source="broken.slk")
    assert excinfo.value.code == "war3_slk_encoding"
    assert excinfo.value.details["source"] == "broken.slk"


def test_unclosed_quote_raises():
    with pytest.raises(SC2Error) as excinfo:
        parse_slk_bytes(_slk('C;X1;Y1;K"abc'))
    assert excinfo.value.code == "war3_slk_unclosed_quote"


@pytest.mark.parametrize(
    "line",
    [
        'C;X0;Y1;K"a"',
        'C;X1;Y-2;K"a"',
        'C;Xabc;Y1;K"a"',
        'C;X1;K"a"',
    ],
)
def test_illegal_coordinate_raises(line):
    with pytest.raises(SC2Error) as excinfo:
        parse_slk_bytes(_slk(line))
    assert excinfo.value.code == "war3_slk_coordinate"


def test_duplicate_coordinate_raises():
    with pytest.raises(SC2Error) as excinfo:
        parse_slk_bytes(_slk('C;X1;Y1;K"a"', 'C;X1;Y1;K"b"'))
    assert excinfo.value.code == "war3_slk_duplicate_cell"


def test_duplicate_header_raises():
    with pytest.raises(SC2Error) as excinfo:
        parse_slk_bytes(_slk('C;X1;Y1;K"a"', 'C;X2;Y1;K"a"'))
    assert excinfo.value.code == "war3_slk_header"


def test_empty_header_raises():
    with pytest.raises(SC2Error) as excinfo:
        parse_slk_bytes(_slk('C;X1;Y1;K"a"', 'C;X2;Y1;K""', 'C;X1;Y2;K"v"'))
    assert excinfo.value.code == "war3_slk_header"


def test_missing_header_row_raises():
    with pytest.raises(SC2Error) as excinfo:
        parse_slk_bytes(_slk('C;X1;Y2;K"a"'))
    assert excinfo.value.code == "war3_slk_header"


def test_unknown_data_column_raises():
    with pytest.raises(SC2Error) as excinfo:
        parse_slk_bytes(_slk('C;X1;Y1;K"a"', 'C;X2;Y2;K"v"'))
    assert excinfo.value.code == "war3_slk_missing_header"


def test_explicit_unknown_column_preservation_keeps_raw_coordinates():
    data = _slk('C;X1;Y1;K"unitID"', 'C;X1;Y2;K"Hamg"', 'C;X6;Y2;KFALSE')
    result = parse_slk_bytes(data,preserve_unknown_columns=True)
    assert result['rows'] == [{'unitID':'Hamg'}]
    assert result['unknown_cells'] == [{'x':6,'y':2,'value':'FALSE'}]
    assert result['complete'] is False


@pytest.mark.parametrize("line", ['C;X1;Y1;K"a"x', 'C;X1;Y1;K"a";K"b"'])
def test_malformed_k_field_raises(line):
    with pytest.raises(SC2Error) as excinfo:
        parse_slk_bytes(_slk(line))
    assert excinfo.value.code == "war3_slk_field"


def test_header_only_has_no_rows():
    result = parse_slk_bytes(_slk('C;X1;Y1;K"unitID"'))
    assert result["columns"] == ["unitID"]
    assert result["rows"] == []
    assert result["cell_count"] == 1


def test_lf_and_cr_line_endings():
    data = b'C;X1;Y1;K"unitID"\nC;X1;Y2;K"amg"\r'
    result = parse_slk_bytes(data)
    assert result["rows"] == [{"unitID": "amg"}]
