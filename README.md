# RobotLog

Offline replay and fault inspection for timestamped robot joint logs. For robotics students and developers checking commanded versus measured angles before investigating a controller. **Simulation and recorded data only: no hardware connection or actuation.**

## Run

Python 3.12+, standard library only; no packages, model downloads or paid services.

```sh
python robotlog.py examples/simulation.csv --config examples/config.json --out output
```

Open `output/index.html` in a modern browser. Select a joint, scrub time, play/pause at 0.5×/1×/2×, inspect angle/error plots and download fault JSON. `output/report.json` contains all samples, signed errors, summary metrics and evidence. Output directory must be new; existing reports are never overwritten.

```sh
python -m unittest discover -s tests -v
python evaluate.py
```

## Input contract

UTF-8 CSV, exact header and one sample per joint per row:

```csv
timestamp_s,joint,commanded,measured
0,shoulder,0,0
0.1,shoulder,10,11
```

Time is nonnegative elapsed seconds, strictly increasing **within each joint**. Interleaved joints may share timestamps. Duplicate or reversed times, missing columns, nonfinite numbers, empty files and unknown joints fail with an error; rows are not silently repaired. Empty measured fields are invalid: represent a missing update by an absent row.

Config JSON:

```json
{"units":"degrees","period_s":0.1,"gap_tolerance_s":0.02,"error_threshold":5,"joints":{"shoulder":[-90,90],"elbow":[-120,120]}}
```

Units can be `degrees` or `radians`. CSV angles, limits and error threshold must ALL use that unit. The setting declares units; it does not convert input. Limits are inclusive. Period must be positive; gap tolerance must be nonnegative and smaller than period. Threshold is nonnegative. All joints share period/threshold in this MVP.

## Detection and replay

- Tracking error = measured − commanded; a fault requires absolute error strictly above threshold.
- Both commanded and measured angles are checked against joint limits separately.
- A missing-update event occurs when consecutive samples of the same joint are separated by more than period + tolerance (with 1e-12 second floating-point comparison slack). It reports gap duration and previous timestamp, not an assumed exact number of missing packets.
- A configured joint with no samples produces `joint_absent` and null RMSE.
- RMSE is sample-weighted, not time-weighted. Replay holds the previous sample and marks it stale after the allowed interval. Plot lines break across gaps. It makes no start/end completeness claim because recording boundaries are unknown.

## Architecture and trade-offs

`robotlog.py` validates configuration/CSV, computes deterministic per-joint metrics and events, and embeds escaped JSON into `report.html`. The HTML uses native SVG and browser controls; it needs no server or network. Untrusted names are rendered as text, and JSON escapes HTML delimiters. `evaluate.py` compares exact event tuples with independently written fixture labels. GitHub Actions runs unit tests, evaluation and CLI export on Python 3.12.

The standard-library implementation is easy to reproduce and inspect. Entire logs are loaded into memory and SVG renders every sample, so use small logs (a few thousand rows). This is not a streaming telemetry service. No angle wrapping is performed: angles are absolute joint coordinates, not circular headings. There is no interpolation, smoothing, dynamics model, collision detection, synchronization correction, causal diagnosis or hardware validation. Thresholds are user assumptions, not learned safety limits. Reports contain the supplied log data; share accordingly.

## Evaluation

The hand-authored **synthetic** fixture in `examples/` has 12 samples and four labelled fault events: tracking error, commanded limit, measured limit, and a gap. Exact-event evaluation measured 4 true positives, 0 false positives and 0 false negatives (precision/recall 1.0). This tiny deterministic correctness fixture is not evidence of real-world detection quality or adoption. Tests also cover invalid data, timestamp ordering, threshold boundaries, absent joints, radians, HTML escaping and CLI overwrite protection.

Optional browser smoke check (development tooling only):

```sh
npm install --no-save playwright
npx playwright install chromium
node tests/browser.cjs
```

Generate `output` first. The check covers plots, stale gaps, playback, reset, export and mobile overflow. Browser tooling is not required to use RobotLog.

## Interview explanation

“I separated deterministic telemetry analysis from replay rendering, validated per-joint time ordering, and made missing-data assumptions explicit. I tested fault evidence against labelled simulated events and kept measured results separate from claims about physical robots.”
