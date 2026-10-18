"""Pure joinery geometry for dovetail.

Parses a plain-text joint file, checks every joint, and lays out cut marks in
exact fractions of a millimetre. Nothing here prints or touches the disk.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from fractions import Fraction

MM_PER_INCH = Fraction(254, 10)
INCH_DENOMINATOR = 16
DEFAULT_MIN_MM = Fraction(6)
DEFAULT_RATIO = Fraction(8)
DEFAULT_CLEARANCE_MM = Fraction(1)

LENGTH_KEYS = frozenset({"width", "stock", "finger", "length", "thickness", "clearance", "min"})
KINDS = {
    "dovetail": (frozenset({"width", "stock", "tails"}), frozenset({"ratio", "min"})),
    "box": (frozenset({"width", "finger"}), frozenset({"stock"})),
    "tenon": (frozenset({"stock", "length"}), frozenset({"thickness", "clearance"})),
}

_MIXED = re.compile(r"(\d+)-(\d+)/(\d+)")


@dataclass(frozen=True)
class Problem:
    line: int
    level: str  # "error" or "warning"
    message: str

    @property
    def is_error(self) -> bool:
        return self.level == "error"


@dataclass
class Joint:
    kind: str
    name: str
    line: int
    values: dict  # lengths are Fractions in mm; "tails" is an int; "ratio" a Fraction


@dataclass(frozen=True)
class Segment:
    label: str
    start: Fraction
    end: Fraction


@dataclass(frozen=True)
class Measure:
    label: str
    value: object  # Fraction in mm, float in degrees, or int count
    unit: str  # "mm", "deg" or "count"


@dataclass
class Layout:
    kind: str
    name: str
    line: int
    span: Fraction
    measures: list = field(default_factory=list)
    segments: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def _error(line: int, message: str) -> Problem:
    return Problem(line, "error", message)


def _warning(line: int, message: str) -> Problem:
    return Problem(line, "warning", message)


def parse_number(text: str) -> Fraction:
    """Read '12.5', '3/4', '-2' or a mixed fraction such as '1-1/2' exactly."""
    s = text.strip()
    try:
        mixed = _MIXED.fullmatch(s)
        if mixed:
            whole, num, den = (int(g) for g in mixed.groups())
            return whole + Fraction(num, den)
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        raise ValueError(f"not a number: {text!r}") from None


def _parse_value(key: str, text: str, units: str):
    if key == "tails":
        count = parse_number(text)
        if count.denominator != 1:
            raise ValueError("must be a whole number")
        return int(count)
    if key == "ratio":
        return parse_number(text)
    factor = MM_PER_INCH if units == "in" else Fraction(1)
    return parse_number(text) * factor


def _parse_joint(kind, name, line, tokens, units):
    required, optional = KINDS[kind]
    problems, values = [], {}
    for token in tokens:
        key, sep, text = token.partition("=")
        key = key.lower()
        if not sep:
            problems.append(_error(line, f"expected key=value, got {token!r}"))
        elif key not in required | optional:
            problems.append(_error(line, f"unknown key {key!r} for {kind}"))
        elif key in values:
            problems.append(_error(line, f"repeated key {key!r}"))
        else:
            try:
                values[key] = _parse_value(key, text, units)
            except ValueError as exc:
                problems.append(_error(line, f"{key}: {exc}"))
    missing = sorted(required - set(values))
    if missing:
        problems.append(_error(line, f"{kind} {name} is missing {', '.join(missing)}"))
    if problems:
        return None, problems
    return Joint(kind, name, line, values), []


def parse_text(text: str, units: str = "mm") -> tuple[list[Joint], list[Problem]]:
    """Parse a joint file. Returns the usable joints and every problem found."""
    joints, problems = [], []
    names = {}
    for lineno, raw in enumerate(text.splitlines(), start=1):
        tokens = raw.split("#", 1)[0].split()
        if not tokens:
            continue
        head = tokens[0].lower()
        if head == "units":
            if len(tokens) == 2 and tokens[1].lower() in ("mm", "in"):
                units = tokens[1].lower()
            else:
                problems.append(_error(lineno, "units must be 'mm' or 'in'"))
            continue
        if head not in KINDS:
            problems.append(_error(lineno, f"unknown joint kind {tokens[0]!r}"))
            continue
        if len(tokens) < 2 or "=" in tokens[1]:
            problems.append(_error(lineno, "joint needs a name after the kind"))
            continue
        name = tokens[1]
        if name in names:
            problems.append(_error(lineno, f"duplicate name {name!r} (first used on line {names[name]})"))
            continue
        names[name] = lineno
        joint, found = _parse_joint(head, name, lineno, tokens[2:], units)
        problems.extend(found)
        if joint is None:
            continue
        found = check_joint(joint)
        problems.extend(found)
        if not any(p.is_error for p in found):
            joints.append(joint)
    return joints, problems


def _dovetail_geometry(values):
    """Return (spacing unit, lateral offset per side) for a dovetail."""
    unit = values["width"] / (2 * values["tails"])
    lateral = values["stock"] / values.get("ratio", DEFAULT_RATIO)
    return unit, lateral


def _finger_count(width, finger):
    """Nearest odd finger count (at least 3) so both outer ends sit on one board."""
    base = max(3, round(width / finger))
    candidates = [n for n in range(base - 2, base + 3) if n >= 3 and n % 2 == 1]
    return min(candidates, key=lambda n: (abs(width / n - finger), n))


def _tenon_thickness(values):
    return values.get("thickness", values["stock"] / 3)


def _plain(number) -> str:
    return f"{float(number):g}"


def check_joint(joint: Joint) -> list[Problem]:
    """Rule checks for one joint. Errors make the joint unusable."""
    v, line = joint.values, joint.line
    problems = []
    for key in sorted(LENGTH_KEYS.intersection(v)):
        if key == "clearance":
            if v[key] < 0:
                problems.append(_error(line, "clearance must be zero or more"))
        elif v[key] <= 0:
            problems.append(_error(line, f"{key} must be greater than zero"))
    if v.get("ratio", DEFAULT_RATIO) <= 0:
        problems.append(_error(line, "ratio must be greater than zero"))
    if joint.kind == "dovetail" and v["tails"] < 2:
        problems.append(_error(line, "a dovetail needs at least 2 tails"))
    if any(p.is_error for p in problems):
        return problems
    if joint.kind == "dovetail":
        problems += _check_dovetail(joint)
    elif joint.kind == "box":
        problems += _check_box(joint)
    else:
        problems += _check_tenon(joint)
    return problems


def _check_dovetail(joint):
    v, line = joint.values, joint.line
    problems = []
    ratio = v.get("ratio", DEFAULT_RATIO)
    if not 5 <= ratio <= 10:
        problems.append(_warning(
            line, f"unusual slope 1:{_plain(ratio)} (softwood is about 1:6, hardwood about 1:8)"))
    unit, lateral = _dovetail_geometry(v)
    limit = v.get("min", DEFAULT_MIN_MM)
    pin_outer = unit - 2 * lateral
    if pin_outer < limit:
        problems.append(_error(
            line,
            f"pins are {fmt_length(pin_outer)} wide at the outer face, below the minimum of "
            f"{fmt_length(limit)}; use fewer tails or a flatter slope"))
    return problems


def _check_box(joint):
    v, line = joint.values, joint.line
    problems = []
    actual = v["width"] / _finger_count(v["width"], v["finger"])
    stock = v.get("stock")
    if stock is not None and abs(actual - stock) > stock / 4:
        problems.append(_warning(
            line,
            f"finger width {fmt_length(actual)} is more than 25% away from stock "
            f"thickness {fmt_length(stock)}"))
    return problems


def _check_tenon(joint):
    v, line = joint.values, joint.line
    problems = []
    thickness = _tenon_thickness(v)
    if thickness >= v["stock"]:
        problems.append(_error(line, "tenon thickness must be less than the stock thickness"))
    elif v["length"] < 2 * thickness:
        problems.append(_warning(
            line, "short tenon: length is under twice its thickness, so little glue area"))
    return problems


def layout_joint(joint: Joint) -> Layout:
    if joint.kind == "dovetail":
        return _layout_dovetail(joint)
    if joint.kind == "box":
        return _layout_box(joint)
    return _layout_tenon(joint)


def _layout_dovetail(joint):
    v = joint.values
    tails, width = v["tails"], v["width"]
    ratio = v.get("ratio", DEFAULT_RATIO)
    unit, lateral = _dovetail_geometry(v)
    segments, x = [], Fraction(0)

    def add(label, size):
        nonlocal x
        segments.append(Segment(label, x, x + size))
        x += size

    add("half-pin", unit / 2)
    for i in range(tails):
        add("tail", unit)
        if i < tails - 1:
            add("pin", unit)
    add("half-pin", unit / 2)
    measures = [
        Measure("Tails", tails, "count"),
        Measure("Spacing unit", unit, "mm"),
        Measure("Tail width at baseline", unit, "mm"),
        Measure("Tail width at outer face", unit + 2 * lateral, "mm"),
        Measure("Pin width at baseline", unit, "mm"),
        Measure("Pin width at outer face", unit - 2 * lateral, "mm"),
        Measure("Lateral offset per side", lateral, "mm"),
        Measure("Full dovetail angle", math.degrees(2 * math.atan(1 / float(ratio))), "deg"),
    ]
    notes = [
        "Scribe the baseline on both boards at the stock thickness.",
        "Cut the tails first, then transfer them to the pin board with a knife.",
    ]
    return Layout("dovetail", joint.name, joint.line, width, measures, segments, notes)


def _layout_box(joint):
    v = joint.values
    width = v["width"]
    count = _finger_count(width, v["finger"])
    size = width / count
    segments = [
        Segment("finger" if i % 2 == 0 else "gap", i * size, (i + 1) * size)
        for i in range(count)
    ]
    measures = [
        Measure("Fingers", count, "count"),
        Measure("Finger width", size, "mm"),
        Measure("Requested finger", v["finger"], "mm"),
    ]
    notes = ["Cut fingers on one board and matching gaps on the other."]
    if size != v["finger"]:
        notes.append("Finger width was adjusted so the odd count fills the width exactly.")
    return Layout("box", joint.name, joint.line, width, measures, segments, notes)


def _layout_tenon(joint):
    v = joint.values
    stock = v["stock"]
    thickness = _tenon_thickness(v)
    clearance = v.get("clearance", DEFAULT_CLEARANCE_MM)
    measures = [
        Measure("Tenon thickness", thickness, "mm"),
        Measure("Shoulder each side", (stock - thickness) / 2, "mm"),
        Measure("Tenon length", v["length"], "mm"),
        Measure("Mortise width", thickness, "mm"),
        Measure("Mortise depth", v["length"] + clearance, "mm"),
    ]
    notes = ["Mortise depth is tenon length plus bottoming clearance."]
    return Layout("tenon", joint.name, joint.line, stock, measures, [], notes)


def analyze(text: str, units: str = "mm"):
    """Parse and lay out a whole file. Returns (layouts, problems)."""
    joints, problems = parse_text(text, units)
    return [layout_joint(j) for j in joints], problems


def _fixed(value, places: int) -> str:
    magnitude = abs(Fraction(value))
    scaled = math.floor(magnitude * 10**places + Fraction(1, 2))
    whole, frac = divmod(scaled, 10**places)
    text = f"{whole}.{frac:0{places}d}" if places else str(whole)
    return f"-{text}" if value < 0 and scaled else text


def fmt_inch(value) -> str:
    """Round to the nearest sixteenth inch and print it as a fraction."""
    sixteenths = math.floor(Fraction(value) / MM_PER_INCH * INCH_DENOMINATOR + Fraction(1, 2))
    sign = "-" if sixteenths < 0 else ""
    inches = Fraction(abs(sixteenths), INCH_DENOMINATOR)
    whole = inches.numerator // inches.denominator
    part = inches - whole
    if part == 0:
        return f'{sign}{whole}"'
    frac = f"{part.numerator}/{part.denominator}"
    return f'{sign}{whole} {frac}"' if whole else f'{sign}{frac}"'


def fmt_length(value, units: str = "mm") -> str:
    if units == "in":
        return fmt_inch(value)
    return f"{_fixed(value, 1)} mm"


def format_measure(measure: Measure, units: str = "mm") -> str:
    if measure.unit == "mm":
        return fmt_length(measure.value, units)
    if measure.unit == "deg":
        return f"{measure.value:.1f} deg"
    return str(measure.value)


def diagram(layout: Layout, columns: int = 60) -> list[str]:
    """Two text rows: '#' for the board that gets tails or fingers, '.' for the other board.
    The second row marks where each cut starts."""
    if not layout.segments:
        return []
    row, marks = [], [" "] * columns
    for col in range(columns):
        x = (col + Fraction(1, 2)) * layout.span / columns
        char = "."
        for seg in layout.segments:
            if seg.start <= x < seg.end:
                char = "#" if seg.label in ("tail", "finger") else "."
                break
        row.append(char)
    for seg in layout.segments:
        marks[min(columns - 1, int(seg.start * columns / layout.span))] = "|"
    return ["".join(row), "".join(marks)]


def layout_to_dict(layout: Layout) -> dict:
    return {
        "kind": layout.kind,
        "name": layout.name,
        "line": layout.line,
        "span_mm": round(float(layout.span), 4),
        "measures": [
            {"label": m.label, "value": round(float(m.value), 4), "unit": m.unit}
            for m in layout.measures
        ],
        "segments": [
            {"label": s.label, "start_mm": round(float(s.start), 4), "end_mm": round(float(s.end), 4)}
            for s in layout.segments
        ],
        "notes": list(layout.notes),
    }
