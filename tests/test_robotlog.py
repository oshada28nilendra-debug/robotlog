import copy
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from robotlog import analyze, render_html

ROOT=Path(__file__).resolve().parents[1]
CONFIG=json.loads((ROOT/'examples/config.json').read_text())
HEADER='timestamp_s,joint,commanded,measured\n'

class AnalysisTests(unittest.TestCase):
    def test_seeded_faults_exact(self):
        report=analyze((ROOT/'examples/simulation.csv').read_text(),CONFIG)
        actual=[[f['kind'],f['joint'],f['timestamp_s']] for f in report['faults']]
        self.assertEqual(actual,json.loads((ROOT/'examples/expected.json').read_text())['events'])
        self.assertAlmostEqual(report['summary']['shoulder']['rmse'], math.sqrt(69/7))
    def test_per_joint_timing(self):
        r=analyze(HEADER+'0,shoulder,0,0\n0,elbow,0,0\n0.1,shoulder,0,0\n0.1,elbow,0,0\n',CONFIG)
        self.assertEqual(r['faults'],[])
    def test_absent_joint(self):
        r=analyze(HEADER+'0,shoulder,0,0\n',CONFIG)
        self.assertEqual(r['faults'][0]['kind'],'joint_absent')
        self.assertIsNone(r['summary']['elbow']['rmse'])
    def test_boundaries_inclusive(self):
        r=analyze(HEADER+'0,shoulder,90,85\n0.12,shoulder,-90,-85\n0,elbow,0,0\n',CONFIG)
        self.assertEqual(r['faults'],[])
    def test_invalid_rows(self):
        for row in ['0,unknown,0,0','-1,shoulder,0,0','0,shoulder,nan,0','0,shoulder,0,inf','0,shoulder,0','0,shoulder,0,0,extra','0,shoulder,1e308,-1e308']:
            with self.subTest(row=row),self.assertRaises(ValueError):analyze(HEADER+row,CONFIG)
    def test_duplicate_and_reversed_times(self):
        for t in ['0','-0.1']:
            with self.assertRaises(ValueError):analyze(HEADER+'0,shoulder,0,0\n'+t+',shoulder,0,0',CONFIG)
    def test_empty_and_wrong_header(self):
        for text in ['',HEADER,'time,joint,commanded,measured\n0,shoulder,0,0']:
            with self.assertRaises(ValueError):analyze(text,CONFIG)
    def test_invalid_config(self):
        for key,value in [('units','grads'),('period_s',0),('period_s',True),('gap_tolerance_s',.1),('error_threshold',-1),('joints',{}),('joints',{'j':[1,0]})]:
            c=copy.deepcopy(CONFIG);c[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError):analyze(HEADER+'0,shoulder,0,0',c)
    def test_radians_equivalence(self):
        c=copy.deepcopy(CONFIG);c['units']='radians';c['error_threshold']=math.radians(5);c['joints']={j:list(map(math.radians,v))for j,v in c['joints'].items()}
        r=analyze(HEADER+f'0,shoulder,0,{math.radians(6)}\n0,elbow,0,0',c)
        self.assertEqual(r['faults'][0]['kind'],'tracking_error')
        self.assertAlmostEqual(r['summary']['shoulder']['rmse'],math.radians(6))
    def test_html_escape(self):
        c=copy.deepcopy(CONFIG);c['joints']={'</script><script>alert(1)</script>':[-1,1]}
        r=analyze(HEADER+'0,</script><script>alert(1)</script>,0,0',c)
        html=render_html(r)
        self.assertNotIn('<script>alert(1)</script>',html)
        self.assertIn('\\u003c/script',html)
    def test_cli_export_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'report';cmd=[sys.executable,str(ROOT/'robotlog.py'),str(ROOT/'examples/simulation.csv'),'--config',str(ROOT/'examples/config.json'),'--out',str(out)]
            result=subprocess.run(cmd,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(len(json.loads((out/'report.json').read_text())['faults']),4)
            self.assertIn('RobotLog',(out/'index.html').read_text())
            self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,2)

if __name__=='__main__':unittest.main()
