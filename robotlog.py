"""Offline joint-log analysis. No dependencies, networking or robot control."""
import argparse
import csv
import io
import json
import math
from pathlib import Path


def number(value, name):
    if isinstance(value, bool):
        raise ValueError(f'{name} must be a finite number')
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'{name} must be a finite number') from None
    if not math.isfinite(result):
        raise ValueError(f'{name} must be a finite number')
    return result


def validate_config(config):
    if config.get('units') not in ('degrees', 'radians'):
        raise ValueError('units must be degrees or radians')
    period = number(config.get('period_s'), 'period_s')
    tolerance = number(config.get('gap_tolerance_s', 0), 'gap_tolerance_s')
    threshold = number(config.get('error_threshold'), 'error_threshold')
    if period <= 0 or tolerance < 0 or tolerance >= period or threshold < 0:
        raise ValueError('positive period, 0 <= gap tolerance < period and nonnegative error threshold required')
    joints = config.get('joints')
    if not isinstance(joints, dict) or not joints:
        raise ValueError('joints must be a nonempty mapping of names to [min,max]')
    limits = {}
    for name, bounds in joints.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(bounds, list) or len(bounds) != 2:
            raise ValueError('each joint requires a name and [min,max] limits')
        lo, hi = [number(v, 'joint limit') for v in bounds]
        if lo >= hi:
            raise ValueError('joint minimum must be below maximum')
        limits[name] = [lo, hi]
    return dict(units=config['units'], period_s=period, gap_tolerance_s=tolerance,
                error_threshold=threshold, joints=limits)


def parse_csv(text, config):
    reader = csv.DictReader(io.StringIO(text))
    required = ['timestamp_s', 'joint', 'commanded', 'measured']
    if reader.fieldnames != required:
        raise ValueError('CSV header must be timestamp_s,joint,commanded,measured')
    rows, last = [], {}
    for line, row in enumerate(reader, 2):
        if None in row or any(v is None for v in row.values()):
            raise ValueError(f'line {line}: wrong field count')
        joint = row['joint']
        if joint not in config['joints']:
            raise ValueError(f'line {line}: unknown joint {joint!r}')
        t = number(row['timestamp_s'], f'line {line} timestamp')
        if t < 0 or t <= last.get(joint, -1):
            raise ValueError(f'line {line}: timestamps must be nonnegative and strictly increasing per joint')
        last[joint] = t
        rows.append(dict(timestamp_s=t, joint=joint,
                         commanded=number(row['commanded'], f'line {line} commanded'),
                         measured=number(row['measured'], f'line {line} measured')))
    if not rows:
        raise ValueError('CSV must contain samples')
    return sorted(rows, key=lambda r: (r['timestamp_s'], r['joint']))


def analyze(text, config):
    config = validate_config(config)
    rows = parse_csv(text, config)
    faults, previous = [], {}
    stats = {j: dict(samples=0, squared_error=0.0, max_abs_error=0.0) for j in config['joints']}
    for row in rows:
        j, t = row['joint'], row['timestamp_s']
        error = row['measured'] - row['commanded']
        if not math.isfinite(error) or not math.isfinite(error * error):
            raise ValueError('angle magnitude too large for error statistics')
        row['error'] = error
        s = stats[j]
        s['samples'] += 1
        s['squared_error'] += error * error
        if not math.isfinite(s['squared_error']):
            raise ValueError('angle magnitude too large for error statistics')
        s['max_abs_error'] = max(s['max_abs_error'], abs(error))
        def fault(kind, **details):
            faults.append(dict(kind=kind, joint=j, timestamp_s=t, **details))
        if abs(error) > config['error_threshold']:
            fault('tracking_error', error=error)
        lo, hi = config['joints'][j]
        for field in ('commanded', 'measured'):
            if not lo <= row[field] <= hi:
                fault(field + '_limit', value=row[field], limits=[lo, hi])
        if j in previous:
            delta = t - previous[j]
            if delta > config['period_s'] + config['gap_tolerance_s'] + 1e-12:
                fault('missing_update', previous_timestamp_s=previous[j], gap_s=delta)
        previous[j] = t
    for j, s in stats.items():
        s['rmse'] = math.sqrt(s.pop('squared_error') / s['samples']) if s['samples'] else None
        if not s['samples']:
            faults.append(dict(kind='joint_absent', joint=j, timestamp_s=None))
    return dict(schema_version=1, simulation_only=True, config=config, samples=rows, faults=faults, summary=stats)


def render_html(report):
    template = Path(__file__).with_name('report.html').read_text(encoding='utf-8')
    # Do not allow CSV/config strings to terminate the inert JSON script element.
    data = json.dumps(report, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return template.replace('__REPORT_DATA__', data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv', type=Path)
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path, help='new output directory (must not exist)')
    args = p.parse_args()
    try:
        report = analyze(args.csv.read_text(encoding='utf-8-sig'), json.loads(args.config.read_text(encoding='utf-8')))
        html = render_html(report)
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / 'report.json').write_text(json.dumps(report, indent=2, allow_nan=False), encoding='utf-8')
        (args.out / 'index.html').write_text(html, encoding='utf-8')
        print(f"{len(report['samples'])} samples; {len(report['faults'])} fault events. Open {args.out / 'index.html'}")
    except (ValueError, OSError, AttributeError) as exc:
        p.exit(2, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
