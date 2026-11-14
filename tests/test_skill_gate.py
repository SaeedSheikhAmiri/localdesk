"""Skill gate stays static, fail-closed and never turns a warning into approval."""
import json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import skill_gate
def report(recommendation,score=0,severity='LOW',issues=()):
 return json.dumps({'risk_assessment':{'score':score,'severity':severity,'recommendation':recommendation},'issues':list(issues)}).encode()
class SkillGateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.skill=Path(self.tmp.name)/'demo-skill';self.skill.mkdir();(self.skill/'SKILL.md').write_text('# demo\n')
 def tearDown(self):self.tmp.cleanup()
 def run_scan(self,returncode=0,stdout=b'',scanner='/fake/skillspector'):
  with patch.object(skill_gate,'scanner',return_value=scanner),patch.object(skill_gate.subprocess,'run',return_value=subprocess.CompletedProcess([],returncode,stdout,b'')) as run:
   return skill_gate.scan(self.skill),run
 def test_static_scan_reports_score(self):
  result,run=self.run_scan(stdout=report('SAFE',4,issues=[{'id':'x'}]))
  self.assertEqual((result['recommendation'],result['score'],result['issues']),('SAFE',4,1))
  command=run.call_args.args[0];self.assertEqual(command[1:3],['scan',str(self.skill)]);self.assertIn('--no-llm',command)
 def test_llm_is_never_requested(self):
  for code in (0,1):self.assertIn('--no-llm',self.run_scan(returncode=code,stdout=report('SAFE'))[1].call_args.args[0])
 def test_do_not_install_is_refused(self):
  with patch.object(skill_gate,'scanner',return_value='/fake/skillspector'),patch.object(skill_gate.subprocess,'run',return_value=subprocess.CompletedProcess([],1,report('DO_NOT_INSTALL',78,'HIGH'),b'')):
   with self.assertRaises(ValueError) as error:skill_gate.require_safe(self.skill)
  self.assertIn('78',str(error.exception))
 def test_caution_is_refused_not_auto_approved(self):
  self.assertEqual(self.run_scan(returncode=1,stdout=report('CAUTION',35,'MEDIUM'))[0]['recommendation'],'CAUTION')
  with patch.object(skill_gate,'scanner',return_value='/fake/skillspector'),patch.object(skill_gate.subprocess,'run',return_value=subprocess.CompletedProcess([],1,report('CAUTION',35,'MEDIUM'),b'')):
   with self.assertRaises(ValueError):skill_gate.require_safe(self.skill)
 def test_missing_scanner_fails_closed(self):
  with patch.object(skill_gate,'scanner',return_value=''):
   with self.assertRaises(ValueError):skill_gate.scan(self.skill)
 def test_malformed_report_fails_closed(self):
  for stdout in (b'',b'not-json',json.dumps({'risk_assessment':{'score':'high','recommendation':'SAFE'}}).encode(),json.dumps({'risk_assessment':{'score':1,'recommendation':'ALLOW'}}).encode()):
   with self.subTest(stdout=stdout):
    with self.assertRaises(ValueError):self.run_scan(stdout=stdout)
 def test_scanner_failure_fails_closed(self):
  for code in (2,3,-9):
   with self.subTest(code=code):
    with self.assertRaises(ValueError):self.run_scan(returncode=code)
 def test_missing_or_symlinked_target_rejected(self):
  with self.assertRaises(ValueError):skill_gate.scan(self.skill/'missing')
  link=Path(self.tmp.name)/'linked';link.symlink_to(self.skill)
  with self.assertRaises(ValueError):skill_gate.scan(link)
