"""Exact-event comparison on the labelled synthetic fixture only."""
import json
from pathlib import Path
from robotlog import analyze
root=Path(__file__).parent
report=analyze((root/'examples/simulation.csv').read_text(),json.loads((root/'examples/config.json').read_text()))
truth={tuple(x) for x in json.loads((root/'examples/expected.json').read_text())['events']}
pred={(f['kind'],f['joint'],f['timestamp_s']) for f in report['faults']}
tp=len(truth&pred)
print(json.dumps(dict(dataset='hand-authored synthetic fixture; not real-world validation',samples=len(report['samples']),true_positives=tp,false_positives=len(pred-truth),false_negatives=len(truth-pred),precision=tp/len(pred) if pred else None,recall=tp/len(truth) if truth else None),indent=2))
