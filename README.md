# dovetail

**Offline joinery layout planner: exact dovetail, box-joint and tenon cut marks from one plain-text file.**

Describe your joints in a few `key=value` lines and `dovetail` prints where every tail, pin, finger and shoulder goes, in exact millimetres or sixteenth-inch fractions. It checks your joint geometry as it goes and reports problems with line numbers. Pure Python standard library, no network, no accounts.

## Features

- **Plain-text joint files** with `#` comments, one joint per line, named so you can pick them out later.
- **Through-dovetail layouts**: evenly spaced tails and pins with half-pins at both edges, computed exactly with fractions.
- **Dovetail geometry**: tail and pin widths at both the baseline and the outer face, lateral offset per side, and the full dovetail angle from the slope ratio.
- **Box (finger) joints**: picks the nearest odd finger count so both outer ends sit on the same board, and reports the adjusted finger width.
- **Tenon sizing**: tenon thickness (default one third of the stock), shoulder widths, mortise width and mortise depth with bottoming clearance.
- **Inches or millimetres**: write `units in` in a file, or pass `--units in` to see results as sixteenth-inch fractions.
- **ASCII board diagrams** (`--diagram`) showing which board gets the tails or fingers, with cut-start markers.
- **Line-numbered lint**: unknown keys, repeated keys, duplicate joint names, bad numbers and impossible geometry are all reported as `file:line: error`.
- **Warnings for odd designs**: slopes outside 1:5 to 1:10, fingers far from stock thickness, and short tenons with little glue area.
- **CI-friendly exit codes**: `check` exits 1 on errors, and `check --strict` also fails on warnings.
- **One-off calculator**: `dovetail calc tenon stock=18 length=30` lays out a joint without writing a file.
- **JSON export** of every layout and cut mark for other tools or scripts.

## Quick start

```bash
python3 -m dovetail check examples/carcase.jnt
```

Output:

```text
examples/carcase.jnt: 4 joint(s) ok, 0 error(s), 0 warning(s)
```

The example file is a small walnut chest carcase:

```text
# examples/carcase.jnt
units mm

dovetail sides width=300 stock=18 tails=4 ratio=8
dovetail drawer-front width=400 stock=15 tails=5 ratio=6 min=5
box drawer-box width=400 finger=15 stock=15
tenon rail-tenon stock=18 length=20
```

Lay out one joint, with a board diagram:

```bash
python3 -m dovetail layout examples/carcase.jnt --name sides --diagram
```

Or try a joint without a file:

```bash
python3 -m dovetail calc tenon stock=18 length=30
```

```text
tenon "calc" (line 1), span 18.0 mm
  Tenon thickness             6.0 mm
  Shoulder each side          6.0 mm
  Tenon length                30.0 mm
  Mortise width               6.0 mm
  Mortise depth              31.0 mm
  note: Mortise depth is tenon length plus bottoming clearance.
```

## File format

| Line | Meaning |
| --- | --- |
| `units mm` or `units in` | Units for every length after this line. Default is `mm`. |
| `dovetail NAME width= stock= tails= [ratio=8] [min=6]` | Through dovetail. `ratio` is the slope 1:R (default 8). `min` is the narrowest allowed pin (default 6 mm). |
| `box NAME width= finger= [stock=]` | Box joint. `stock` is optional and enables the finger-versus-stock warning. |
| `tenon NAME stock= length= [thickness=] [clearance=1]` | Tenon. Thickness defaults to a third of the stock. |

Lengths accept decimals (`12.5`), fractions (`3/4`) and mixed fractions (`1-1/2`). Joint names must be unique.

## Commands

| Command | What it does |
| --- | --- |
| `check FILE [--strict]` | Lint the file. Exit 0 when clean, 1 on errors (or warnings with `--strict`), 2 when the file cannot be read. |
| `layout FILE [--name N] [--units mm\|in] [--diagram]` | Print the measures, cut marks, diagram and notes for each joint. |
| `export FILE` | Print every layout as JSON. Problems go to stderr so the JSON stays clean. |
| `calc KIND key=value ... [--input-units mm\|in] [--units mm\|in] [--diagram]` | Lay out one joint given inline. |

## How to run

Requires Python 3.9 or newer. Run every command from the project root, the directory that contains the `dovetail/` package:

```bash
python3 -m dovetail --help
python3 -m dovetail check path/to/your.jnt
```

## How to test

Tests use pytest. Install it once, then run from the project root:

```bash
python3 -m pip install pytest
python3 -m pytest -q
```

The suite covers number parsing, inch conversion, dovetail and box geometry, tenon sizing, line-numbered errors, the diagram, and every CLI command, including exit codes.

## Project layout

```text
dovetail/        core.py (pure geometry and parsing), cli.py (commands), __main__.py
examples/        carcase.jnt (clean sample) and broken.jnt (shows error reports)
tests/           pytest suite for core logic and the CLI
```
