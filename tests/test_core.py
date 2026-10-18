from fractions import Fraction

import pytest

from dovetail import core


def test_parse_number_reads_decimals_fractions_and_mixed_numbers():
    assert core.parse_number("12.5") == Fraction(25, 2)
    assert core.parse_number("3/4") == Fraction(3, 4)
    assert core.parse_number("1-1/2") == Fraction(3, 2)
    with pytest.raises(ValueError, match="not a number"):
        core.parse_number("abc")
    with pytest.raises(ValueError):
        core.parse_number("1/0")


def test_inch_units_are_converted_to_exact_millimetres():
    joints, problems = core.parse_text("units in\ndovetail sides width=12 stock=3/4 tails=4")
    assert problems == []
    assert joints[0].values["width"] == 12 * core.MM_PER_INCH
    assert joints[0].values["stock"] == Fraction(3, 4) * core.MM_PER_INCH


def test_dovetail_segments_cover_the_width_exactly():
    layouts, _ = core.analyze("dovetail sides width=300 stock=18 tails=4 ratio=8")
    layout = layouts[0]
    assert layout.segments[0].start == 0
    assert layout.segments[-1].end == 300
    labels = [s.label for s in layout.segments]
    assert labels.count("tail") == 4
    assert labels.count("pin") == 3
    assert labels.count("half-pin") == 2


def test_dovetail_tail_and_pin_widths_at_both_faces():
    layouts, _ = core.analyze("dovetail sides width=300 stock=18 tails=4 ratio=8")
    measures = {m.label: m.value for m in layouts[0].measures}
    # unit = 300 / 8 = 37.5 mm; lateral offset per side = 18 / 8 = 2.25 mm
    assert measures["Spacing unit"] == Fraction(75, 2)
    assert measures["Lateral offset per side"] == Fraction(9, 4)
    assert measures["Tail width at outer face"] == 42
    assert measures["Pin width at outer face"] == 33


def test_dovetail_angle_matches_the_slope_ratio():
    layouts, _ = core.analyze("dovetail sides width=300 stock=18 tails=4 ratio=8")
    angle = next(m.value for m in layouts[0].measures if m.unit == "deg")
    assert angle == pytest.approx(14.25, abs=0.01)


def test_pins_too_thin_at_the_outer_face_is_an_error_with_line_number():
    joints, problems = core.parse_text(
        "units mm\ndovetail sides width=300 stock=18 tails=40 ratio=8\n"
    )
    assert joints == []
    assert len(problems) == 1
    assert problems[0].is_error and problems[0].line == 2
    assert "below the minimum" in problems[0].message


def test_unusual_slope_is_a_warning_and_the_joint_is_kept():
    joints, problems = core.parse_text("dovetail sides width=300 stock=18 tails=4 ratio=2")
    assert len(joints) == 1
    assert [p.level for p in problems] == ["warning"]


def test_box_finger_count_is_odd_and_close_to_request():
    layouts, _ = core.analyze("box drawer width=400 finger=15 stock=15")
    layout = layouts[0]
    count = next(m.value for m in layout.measures if m.label == "Fingers")
    assert count == 27
    assert count % 2 == 1
    assert len(layout.segments) == count


def test_box_segments_start_and_end_on_fingers():
    layouts, _ = core.analyze("box drawer width=400 finger=15")
    labels = [s.label for s in layouts[0].segments]
    assert labels[0] == "finger" and labels[-1] == "finger"
    assert all(label == ("finger" if i % 2 == 0 else "gap") for i, label in enumerate(labels))


def test_tenon_defaults_give_a_third_thickness_and_one_mm_clearance():
    layouts, _ = core.analyze("tenon rail stock=18 length=30")
    measures = {m.label: m.value for m in layouts[0].measures}
    assert measures["Tenon thickness"] == 6
    assert measures["Shoulder each side"] == 6
    assert measures["Mortise depth"] == 31


def test_tenon_thicker_than_stock_is_rejected():
    joints, problems = core.parse_text("tenon rail stock=18 length=30 thickness=18")
    assert joints == []
    assert any(p.is_error and p.line == 1 for p in problems)


def test_duplicate_names_and_unknown_keys_report_their_lines():
    text = (
        "dovetail sides width=300 stock=18 tails=4\n"
        "dovetail sides width=300 stock=18 tails=4\n"
        "box drawer width=400 finger=15 colour=red\n"
    )
    joints, problems = core.parse_text(text)
    messages = {(p.line, p.message) for p in problems}
    assert any(line == 2 and "duplicate name" in msg for line, msg in messages)
    assert any(line == 3 and "unknown key 'colour'" in msg for line, msg in messages)
    assert [j.name for j in joints] == ["sides"]


def test_missing_required_key_is_reported():
    _, problems = core.parse_text("tenon rail stock=18")
    assert problems[0].is_error
    assert "missing length" in problems[0].message


def test_fmt_inch_rounds_to_sixteenths():
    assert core.fmt_inch(Fraction(3, 4) * core.MM_PER_INCH) == '3/4"'
    assert core.fmt_inch(Fraction(3, 2) * core.MM_PER_INCH) == '1 1/2"'
    assert core.fmt_inch(0) == '0"'


def test_fmt_length_in_millimetres_rounds_half_up():
    assert core.fmt_length(Fraction(37, 2)) == "18.5 mm"
    assert core.fmt_length(Fraction(-3, 4)) == "-0.8 mm"


def test_diagram_marks_about_half_the_board_for_four_equal_tails():
    layouts, _ = core.analyze("dovetail sides width=300 stock=18 tails=4 ratio=8")
    rows = core.diagram(layouts[0], columns=40)
    assert len(rows) == 2
    assert abs(rows[0].count("#") - 20) <= 1
    assert rows[1].count("|") == len(layouts[0].segments)
