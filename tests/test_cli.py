import json
from pathlib import Path

from dovetail.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def test_check_example_file_passes(capsys):
    assert main(["check", str(EXAMPLES / "carcase.jnt")]) == 0
    out = capsys.readouterr().out
    assert "4 joint(s) ok, 0 error(s), 0 warning(s)" in out


def test_check_broken_file_reports_line_numbers_and_exits_one(capsys):
    assert main(["check", str(EXAMPLES / "broken.jnt")]) == 1
    out = capsys.readouterr().out
    assert "broken.jnt:2: error" in out
    assert "broken.jnt:3: error" in out
    assert "broken.jnt:4: error" in out
    assert "broken.jnt:5: error" in out


def test_strict_mode_fails_on_warnings(tmp_path, capsys):
    path = tmp_path / "slope.jnt"
    path.write_text("dovetail sides width=300 stock=18 tails=4 ratio=2\n", encoding="utf-8")
    assert main(["check", str(path)]) == 0
    assert main(["check", "--strict", str(path)]) == 1
    assert "unusual slope" in capsys.readouterr().out


def test_layout_prints_marks_and_diagram_for_one_joint(capsys):
    assert main(["layout", str(EXAMPLES / "carcase.jnt"), "--name", "sides", "--diagram"]) == 0
    out = capsys.readouterr().out
    assert 'dovetail "sides"' in out
    assert "Tail width at outer face" in out
    assert "cut marks:" in out
    assert "#" in out


def test_layout_inches_option_shows_sixteenths(capsys):
    assert main(["layout", str(EXAMPLES / "carcase.jnt"), "--name", "drawer-box", "--units", "in"]) == 0
    out = capsys.readouterr().out
    assert '"' in out


def test_export_writes_valid_json_with_every_joint(capsys):
    assert main(["export", str(EXAMPLES / "carcase.jnt")]) == 0
    payload = json.loads(capsys.readouterr().out)
    kinds = [joint["kind"] for joint in payload["joints"]]
    assert kinds == ["dovetail", "dovetail", "box", "tenon"]
    assert payload["joints"][0]["span_mm"] == 300.0


def test_calc_lays_out_an_ad_hoc_joint(capsys):
    assert main(["calc", "tenon", "stock=18", "length=30"]) == 0
    out = capsys.readouterr().out
    assert "Mortise depth" in out
    assert "31.0 mm" in out


def test_calc_rejects_a_bad_spec_with_exit_one(capsys):
    assert main(["calc", "box", "width=400"]) == 1
    assert "missing finger" in capsys.readouterr().out
