"""Synthetic release boundaries: clean installs, provenance checks and confinement."""
import importlib.util,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'app'));sys.path.insert(0,str(ROOT/'scripts'))
import settings,security,launch_assistant as launcher,confinement,audit_public

class ReleaseBoundaries(unittest.TestCase):
 def test_startup_does_not_reuse_external_auth(self):
  with patch.dict(os.environ,{'OPENROUTER_API_KEY':'synthetic-value','HOME':'/unused'},clear=True),patch.object(launcher,'TASK_MODEL','ollama/example'),patch.object(launcher,'password',return_value='synthetic'):
   env=launcher.child_environment(True)
  self.assertEqual(env['HOME'],str(settings.ENGINE_HOME));self.assertNotIn('OPENROUTER_API_KEY',env)
 def test_online_requires_explicit_own_key(self):
  with patch.dict(os.environ,{},clear=True),patch.object(launcher,'TASK_MODEL','openrouter/openrouter/free'),patch.object(launcher,'password',return_value='synthetic'):
   with self.assertRaises(RuntimeError):launcher.child_environment(True)
 def test_data_outside_source(self):self.assertNotIn(settings.ROOT,settings.DATA.parents)
 def test_config_has_no_credentials_or_profiles(self):
  config=launcher.task_config();self.assertNotIn('agent',config);self.assertNotIn('apiKey',json.dumps(config));self.assertEqual(config['permission']['webfetch'],'ask');self.assertFalse(config['autoupdate'])
 def test_model_ids_cannot_inject_html(self):
  with patch.dict(os.environ,{'LOCALDESK_TEST_MODEL':'bad\"<script>'}):
   with self.assertRaises(ValueError):settings.model('LOCALDESK_TEST_MODEL','default')
 def test_audit_finds_a_secret_without_printing_it(self):
  with tempfile.TemporaryDirectory() as directory:
   path=Path(directory);(path/'note.md').write_text('synthetic-release-canary')
   findings=audit_public.inspect(path,[b'synthetic-release-canary'])
   self.assertEqual(findings,[('note.md','private-origin exact match')])
 def test_audit_rejects_runtime_files(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'agents.json').write_text('[]')
   self.assertTrue(audit_public.inspect(root))
 def test_release_app_sources_are_generic(self):
  for path in (ROOT/'app').rglob('*'):
   if path.suffix not in ('.py','.html','.js','.css','.svg'):continue
   raw=path.read_bytes();self.assertNotIn(b'data:font/',raw);self.assertLess(len(raw),100000)

@unittest.skipUnless(sys.platform=='darwin' and Path('/usr/bin/sandbox-exec').exists(),'macOS only')
class ConfinementTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
  self.state=self.base/'state';self.state.mkdir()
  self.tasks=self.base/'workspace';self.tasks.mkdir()
  self.engine=self.base/'engine';self.engine.mkdir()
  self.secret=self.base/'private-note';self.secret.write_text('synthetic canary only')
  self.patches=[patch.object(confinement,'STATE',self.state),patch.object(confinement,'DATA',self.base),patch.object(confinement,'TASKS',self.tasks),patch.object(confinement,'ENGINE_HOME',self.engine)]
  for item in self.patches:item.start()
 def tearDown(self):
  for item in reversed(self.patches):item.stop()
  self.temp.cleanup()
 def run_confined(self,kind,args):return subprocess.run(confinement.command(kind,args),capture_output=True,timeout=10)
 def test_parser_cannot_read_unapproved_data(self):
  result=self.run_confined('parser',['/bin/cat',str(self.secret)]);self.assertNotEqual(result.returncode,0);self.assertNotIn(b'synthetic canary',result.stdout)
 def test_task_cannot_read_private_data_through_alias(self):
  alias=self.tasks/'alias';alias.symlink_to(self.secret)
  result=self.run_confined('tasks',['/bin/cat',str(alias)]);self.assertNotEqual(result.returncode,0)
 def test_task_can_read_workspace_but_not_its_config(self):
  note=self.tasks/'note.txt';note.write_text('public fixture');result=self.run_confined('tasks',['/bin/cat',str(note)]);self.assertEqual(result.returncode,0)
  config=self.tasks/'opencode.json';config.write_text('{}')
  result=self.run_confined('tasks',['/bin/sh','-c','printf changed > "$1"','test',str(config)]);self.assertNotEqual(result.returncode,0);self.assertEqual(config.read_text(),'{}')
 def test_task_rejects_environment_file_alias(self):
  secret=self.tasks/'.env';secret.write_text('synthetic environment canary')
  alias=self.tasks/'notes.txt';alias.symlink_to(secret)
  result=self.run_confined('tasks',['/bin/cat',str(alias)]);self.assertNotEqual(result.returncode,0)
 def test_parser_cannot_write_a_file(self):
  destination=self.tasks/'created'
  result=self.run_confined('parser',['/bin/sh','-c','printf no > "$1"','test',str(destination)])
  self.assertNotEqual(result.returncode,0);self.assertFalse(destination.exists())

class CredentialRoutingTests(unittest.TestCase):
 def test_unknown_task_listener_never_receives_password(self):
  import agents_backend
  with patch.object(launcher,'trusted_task_listener',return_value=False),patch.object(agents_backend,'authorization',side_effect=AssertionError('must not request credential')):
   with self.assertRaises(ValueError):agents_backend.native('/session')


class PublicCredentialScanTests(unittest.TestCase):
 def test_fine_grained_github_token_is_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'settings.yml').write_text('github_'+'pat_'+('Z'*30))
   findings=audit_public.inspect(root)
   self.assertIn(('settings.yml','fine-grained GitHub token'),findings)
 def test_provider_token_is_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);(root/'settings.yml').write_text('sk-'+'or-v1-'+('Z'*30))
   self.assertIn(('settings.yml','provider token'),audit_public.inspect(root))


class RuntimeDataLocationTests(unittest.TestCase):
 def test_custom_data_inside_checkout_is_rejected_before_writing(self):
  forbidden=ROOT/'unapproved-runtime-data'
  env={**os.environ,'LOCALDESK_DATA_DIR':str(forbidden)}
  code='import sys; sys.path.insert(0,sys.argv[1]); import settings'
  result=subprocess.run([sys.executable,'-I','-B','-c',code,str(ROOT/'app')],env=env,capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0)
  self.assertIn('outside the source tree',result.stderr)
  self.assertFalse(forbidden.exists())
