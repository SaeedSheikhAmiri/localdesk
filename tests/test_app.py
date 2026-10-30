import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"app"))
import unittest,sys,tempfile,json,threading,http.client,re,copy,urllib.error
from pathlib import Path
from unittest.mock import patch
import server,agents_backend as agents,security,state_store
import work_backend as work
import subprocess
import launch_assistant as launcher
class HTTPTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory();cls.state_patch=patch.object(security,'STATE',Path(cls.temp.name));cls.state_patch.start();cls.store_patch=patch.object(state_store,'STATE',Path(cls.temp.name));cls.store_patch.start();cls.http=server.Server(('127.0.0.1',0),server.Handler);cls.port=cls.http.server_address[1]
  cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
 @classmethod
 def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.thread.join();cls.store_patch.stop();cls.state_patch.stop();cls.temp.cleanup()
 def call(self,path='/',method='GET',body=None,headers=None):
  h={'Cookie':'localdesk_session='+security.session_value(),'Host':f'127.0.0.1:{self.port}','Origin':f'http://127.0.0.1:{self.port}','X-Chat-Token':server.TOKEN,'Content-Type':'application/json'}
  h.update(headers or {});raw=body if isinstance(body,(str,bytes)) else json.dumps(body) if body is not None else None
  c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3);c.request(method,path,body=raw,headers=h);r=c.getresponse();data=r.read();out=(r.status,dict(r.getheaders()),data);c.close();return out
 def test_pages_and_headers(self):
  for path in ['/','/assistant','/agents','/task-access','/work','/login']:
   with self.subTest(path=path):
    status,h,b=self.call(path);self.assertEqual(status,200);self.assertIn("frame-ancestors 'none'",h['Content-Security-Policy']);self.assertIn("base-uri 'none'",h['Content-Security-Policy']);self.assertEqual(h['X-Frame-Options'],'DENY');self.assertEqual(h['Referrer-Policy'],'no-referrer');self.assertNotIn(b'__TOKEN__',b);self.assertNotIn(b'http://fonts.',b)
 def test_csp_script_hashes(self):
  import hashlib,base64
  for path in ['/','/assistant','/agents','/task-access','/work','/login']:
   _,h,b=self.call(path)
   for script in re.findall(r'<script>(.*?)</script>',b.decode(),re.S):self.assertIn(base64.b64encode(hashlib.sha256(script.encode()).digest()).decode(),h['Content-Security-Policy'])
 def test_health(self):self.assertTrue(json.loads(self.call('/health')[2])['ok'])
 def test_host_rebinding(self):
  for method in ['GET','POST']:
   self.assertEqual(self.call('/chat' if method=='POST' else '/',method,{}, {'Host':f'evil.example:{self.port}'})[0],403)
 def test_origin_rejection(self):
  for origin in ['https://evil.example','null','http://127.0.0.1:9999','']:
   self.assertEqual(self.call('/chat','POST',{}, {'Origin':origin})[0],403)
 def test_missing_stale_csrf(self):
  for path in ['/api/agents','/chat','/api/tasks/access']:
   self.assertEqual(self.call(path,'GET' if path=='/api/agents' else 'POST',{}, {'X-Chat-Token':'bad'})[0],403)
 def test_cross_site_metadata(self):self.assertEqual(self.call('/api/agents',headers={'Sec-Fetch-Site':'cross-site'})[0],403)
 def test_sensitive_routes_absent(self):
  for path in ['/server.py','/.state/tasks-password','/../security.py','/%2e%2e/security.py','/agents.json','/assistant?x=1']:
   self.assertEqual(self.call(path)[0],404)
 def test_malformed_json(self):
  for raw in ['{','[]','null','1','"hello"']:
   self.assertEqual(self.call('/chat','POST',raw)[0],400)
 def test_chat_validation(self):
  payload={'requestId':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','model':'qwen2.5:7b-instruct','messages':[{'role':'user','content':'سلام'}]}
  for patcher in [{'model':'http://evil/'},{'model':[]},{'messages':[None]},{'messages':[{'role':'system','content':'x'}]},{'messages':[]},{'messages':[{'role':'assistant','content':'x'}]},{'messages':[{'role':'user','content':'x'*6001}]},{'requestId':'../bad'}]:
   with self.subTest(patcher=patcher):self.assertEqual(self.call('/chat','POST',{**payload,**patcher})[0],400)
 def test_non_json(self):self.assertEqual(self.call('/chat','POST','{}',{'Content-Type':'text/plain'})[0],400)
 def test_oversized(self):self.assertEqual(self.call('/chat','POST','x'*100001)[0],400)
 def test_options_no_cors(self):
  status,h,_=self.call('/','OPTIONS');self.assertEqual(status,403);self.assertNotIn('Access-Control-Allow-Origin',h)
 def test_unsupported_verb(self):self.assertEqual(self.call('/','PUT',{})[0],405)
 def test_agents_get(self):
  with patch.object(server,'profiles',return_value=[]):self.assertEqual(json.loads(self.call('/api/agents')[2]),{'agents':[]})
 def test_private_error_not_leaked(self):
  with patch.object(server,'profiles',side_effect=RuntimeError('secret-api-key')):
   status,_,b=self.call('/api/agents');self.assertEqual(status,500);self.assertNotIn(b'secret-api-key',b)
 def test_upstream_down(self):
  with patch.object(server,'save_profile',side_effect=urllib.error.URLError('private-detail')):
   status,_,b=self.call('/api/agents/save','POST',{});self.assertEqual(status,503);self.assertNotIn(b'private-detail',b)
 def test_cancel_unknown_is_safe(self):self.assertEqual(self.call('/chat/cancel','POST',{'requestId':'unknown'})[0],200)
 def test_active_chat_limit(self):
  self.assertTrue(server.CHAT_SLOT.acquire(False))
  try:self.assertEqual(self.call('/chat','POST',{'requestId':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','model':'qwen2.5:7b-instruct','messages':[{'role':'user','content':'hello'}]})[0],429)
  finally:server.CHAT_SLOT.release()

class AgentTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.tasks=self.root/'tasks';self.tasks.mkdir();self.state=self.root/'.state';self.state.mkdir();self.store=self.root/'agents.json';self.path=self.tasks/'opencode.json';self.old={'model':'keep','permission':{'bash':'ask'}};self.path.write_text(json.dumps(self.old))
  self.patches=[patch('state_store.recalled',return_value=''),patch.object(agents,'STORE',self.store),patch.object(agents,'TASKS',self.tasks),patch.object(agents,'STATE',self.state)]
  for p in self.patches:p.start()
  self.payload={'title':'نویسنده','description':'نوشتن متن','prompt':'Write clear natural Persian.','model':'openrouter/openrouter/free','access':'readonly'}
 def tearDown(self):
  for p in self.patches:p.stop()
  self.tmp.cleanup()
 def fake(self,path,body=None,method=None):
  if path=='/session/status':return {}
  if path=='/instance/dispose':return True
  if path=='/agent':return [{'name':k} for k in json.loads(self.path.read_text()).get('agent',{})]
  if path=='/session':return {'id':'ses_test123'}
  if path.endswith('/prompt_async'):return None
  self.fail('Unexpected native call '+path)
 def save(self):
  with patch.object(agents,'native',side_effect=self.fake):return agents.save_profile(self.payload)['agent']
 def test_save_native_and_permissions(self):
  item=self.save();self.assertEqual(agents.profiles()[0],item);d=json.loads(self.path.read_text());self.assertEqual(d['model'],'keep');self.assertEqual(d['agent'][item['id']]['permission']['bash'],'deny');self.assertEqual(d['agent'][item['id']]['permission']['task'],'deny');self.assertEqual(d['agent'][item['id']]['permission']['edit']['*'],'deny');self.assertEqual(self.store.stat().st_mode&0o777,0o600)
 def test_edit_updates_existing(self):
  a=self.save();self.payload.update(id=a['id'],title='ویرایش شده')
  self.save();self.assertEqual(len(agents.profiles()),1);self.assertEqual(agents.profiles()[0]['title'],'ویرایش شده')
 def test_invalid_inputs(self):
  for values in [{'title':None},{'prompt':True},{'access':'admin'},{'model':'paid/model'},{'id':'../secret'},{'description':'x'*301}]:
   with self.subTest(values=values):
    with self.assertRaises(ValueError):agents.save_profile({**self.payload,**values})
 def test_busy_does_not_mutate(self):
  with patch.object(agents,'native',return_value={'ses':{'type':'busy'}}):
   with self.assertRaises(ValueError):agents.save_profile(self.payload)
  self.assertEqual(json.loads(self.path.read_text()),self.old);self.assertFalse(self.store.exists())
 def test_failed_reload_rolls_back(self):
  with patch.object(agents,'native',side_effect=lambda p,*a:{} if p=='/session/status' else []):
   with self.assertRaises(ValueError):agents.save_profile(self.payload)
  self.assertEqual(json.loads(self.path.read_text()),self.old);self.assertFalse(self.store.exists())
 def test_idempotent_task(self):
  a=self.save();d={'id':a['id'],'task':'Test task','requestId':'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'}
  with patch.object(agents,'native',side_effect=self.fake) as native:
   one=agents.start_profile(d);two=agents.start_profile(d)
   self.assertTrue(one['accepted']);self.assertTrue(two['duplicate']);self.assertEqual(sum(c.args[0]=='/session' for c in native.call_args_list),1)
 def test_reused_request_with_changed_task_denied(self):
  a=self.save();d={'id':a['id'],'task':'Test','requestId':'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'}
  with patch.object(agents,'native',side_effect=self.fake):
   agents.start_profile(d)
   with self.assertRaises(ValueError):agents.start_profile({**d,'task':'different'})
 def test_uncertain_dispatch_not_repeated(self):
  a=self.save();d={'id':a['id'],'task':'Test','requestId':'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'}
  def fake(path,*args):
   if path.endswith('prompt_async'):raise TimeoutError()
   return self.fake(path,*args)
  with patch.object(agents,'native',side_effect=fake) as native:
   self.assertFalse(agents.start_profile(d)['accepted']);self.assertTrue(agents.start_profile(d)['duplicate']);self.assertEqual(sum(c.args[0]=='/session' for c in native.call_args_list),1)
 def test_security_sensitive_edits_denied(self):
  for access in ['files','confirm','readonly']:
   p=security.permissions(access);self.assertEqual(p['edit']['opencode.json'],'deny');self.assertEqual(p['read']['**/auth.json'],'deny');self.assertNotEqual(p['bash'],'allow')
 def test_atomic_symlink_denied(self):
  target=self.root/'private';target.write_text('keep');link=self.root/'link';link.symlink_to(target)
  with self.assertRaises(ValueError):security.atomic_json(link,{'bad':1})
  self.assertEqual(target.read_text(),'keep')

class CancellationTests(unittest.TestCase):
 def test_cancel_socket_and_event(self):
  from unittest.mock import Mock
  connection=Mock();event=threading.Event()
  with server.ACTIVE_LOCK:server.ACTIVE['test']={'cancel':event,'connection':connection}
  try:server.cancel_chat('test');self.assertTrue(event.is_set());connection.sock.shutdown.assert_called_once()
  finally:server.ACTIVE.pop('test',None)

class WorkTests(unittest.TestCase):
 def setUp(self):
  self.sid='ses_work123';self.directory=str(work.TASKS);self.recall=patch('state_store.recalled',return_value='');self.recall.start()
 def tearDown(self):self.recall.stop()
 def fake(self,path,body=None,method=None):
  if path=='/session/'+self.sid:return {'id':self.sid,'directory':self.directory,'agent':'build','model':{'providerID':'openrouter','id':'openrouter/free'}}
  if path=='/session/status':return {}
  if path=='/permission':return [{'id':'per_test','sessionID':self.sid,'permission':'bash','patterns':['echo test']}]
  if path.endswith('/reply') or path.endswith('/abort') or path.endswith('/prompt_async'):return True
  raise AssertionError(path)
 def test_foreign_session_rejected(self):
  with patch.object(work,'native',return_value={'directory':'/another/project'}):
   with self.assertRaises(ValueError):work.session_id({'session':self.sid})
 def test_traversal_sid_rejected(self):
  with self.assertRaises(ValueError):work.session_id({'session':'../../config'})
 def test_permission_always_disallowed(self):
  with patch.object(work,'native',side_effect=self.fake):
   with self.assertRaises(ValueError):work.work_action({'action':'permission','session':self.sid,'permission':'per_test','reply':'always'})
 def test_permission_other_session_rejected(self):
  def fake(path,*args):return [{'id':'per_other','sessionID':'ses_other'}] if path=='/permission' else self.fake(path,*args)
  with patch.object(work,'native',side_effect=fake):
   with self.assertRaises(ValueError):work.work_action({'action':'permission','session':self.sid,'permission':'per_other','reply':'once'})
 def test_permission_once_allowed(self):
  with patch.object(work,'native',side_effect=self.fake) as native:
   self.assertTrue(work.work_action({'action':'permission','session':self.sid,'permission':'per_test','reply':'once'})['ok']);self.assertEqual(native.call_args.args[0],'/permission/per_test/reply')
 def test_stop(self):
  with patch.object(work,'native',side_effect=self.fake):self.assertTrue(work.work_action({'action':'stop','session':self.sid})['ok'])
 def test_reply_uses_session_model_and_agent(self):
  with patch.object(work,'native',side_effect=self.fake) as native:
   work.work_action({'action':'reply','session':self.sid,'task':'hello','requestId':'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa','model':'paid/model','agent':'admin'})
   body=native.call_args.args[1];self.assertEqual(body['agent'],'build');self.assertEqual(body['model']['modelID'],'openrouter/free')
 def test_unknown_action_rejected(self):
  with patch.object(work,'native',side_effect=self.fake):
   with self.assertRaises(ValueError):work.work_action({'action':'arbitrary-http-proxy','session':self.sid})

class SessionHTTPTests(unittest.TestCase):
 setUpClass=classmethod(HTTPTests.setUpClass.__func__)
 tearDownClass=classmethod(HTTPTests.tearDownClass.__func__)
 call=HTTPTests.call
 def test_anonymous_api_denied(self):
  for path in ['/api/agents','/api/tasks/access','/api/work/state']:
   method='GET' if path=='/api/agents' else 'POST'
   self.assertEqual(self.call(path,method,{}, {'Cookie':''})[0],401)
 def test_anonymous_page_redirects(self):self.assertEqual(self.call('/',headers={'Cookie':''})[0],302)
 def test_login_bad_password(self):self.assertEqual(self.call('/api/login','POST',{'password':'wrong'}, {'Cookie':''})[0],401)
 def test_ticket_single_use_http(self):
  ticket=security.issue_ticket();status,h,_=self.call('/api/login','POST',{'ticket':ticket},{'Cookie':''});self.assertEqual(status,200);self.assertIn('HttpOnly',h['Set-Cookie']);self.assertIn('SameSite=Strict',h['Set-Cookie']);self.assertEqual(self.call('/api/login','POST',{'ticket':ticket},{'Cookie':''})[0],401)
 def test_login_foreign_origin_denied(self):self.assertEqual(self.call('/api/login','POST',{'password':'irrelevant'},{'Cookie':'','Origin':'https://evil.example'})[0],403)
 def test_cookie_forgery_rejected(self):self.assertEqual(self.call('/api/agents',headers={'Cookie':'localdesk_session=9999999999.nonce.forged'})[0],401)

 def test_non_ascii_login_password_rejected(self):
  for value in ['سلام','\ud800']:
   self.assertEqual(self.call('/api/login','POST',{'password':value},{'Cookie':''})[0],401)
 def test_non_ascii_csrf_rejected(self):self.assertEqual(self.call('/api/agents',headers={'X-Chat-Token':'é'})[0],403)

class SessionCryptoTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.patch=patch.object(security,'STATE',Path(self.tmp.name));self.patch.start()
 def tearDown(self):self.patch.stop();self.tmp.cleanup()
 def test_cookie_signature(self):
  value=security.session_value();self.assertTrue(security.valid_session('localdesk_session='+value));self.assertFalse(security.valid_session('localdesk_session='+value[:-1]+'X'))
 def test_expired_cookie(self):
  with patch.object(security.time,'time',return_value=1):value=security.session_value()
  self.assertFalse(security.valid_session('localdesk_session='+value))
 def test_ticket_expiry(self):
  ticket=security.issue_ticket()
  with patch.object(security.time,'time',return_value=10**12):self.assertFalse(security.consume_ticket(ticket))

class CancellationFallbackTests(unittest.TestCase):
 def test_cancel_response_when_connection_already_detached(self):
  from unittest.mock import Mock
  connection=Mock();connection.sock=None;response=Mock();event=threading.Event()
  with server.ACTIVE_LOCK:server.ACTIVE['fallback']={'cancel':event,'connection':connection,'response':response}
  try:server.cancel_chat('fallback');self.assertTrue(event.is_set());response.fp.raw._sock.shutdown.assert_called_once()
  finally:server.ACTIVE.pop('fallback',None)