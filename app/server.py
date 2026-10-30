#!/usr/bin/env python3
"""Loopback-only LocalDesk UI. No arbitrary filesystem or network proxy routes."""
import base64,hashlib,json,secrets,socket,threading,time,urllib.request,urllib.error,re,http.client
from collections import deque
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
from agents_backend import profiles,save_profile,start_profile
from security import password,valid_session,session_value,login,health_proof
from work_backend import work_state,work_action
from sources import prepare_chat,parse_file,validate_image
from state_store import chat_action,memory_action,storage_action,recalled,model_action
from urllib.parse import urlsplit,parse_qs
ROOT=Path(__file__).resolve().parent
TOKEN=secrets.token_urlsafe(32)
from settings import UI_PORT,UI_URL,TASK_URL,TASK_MODEL,CHAT_MODEL,VISION_MODEL,CHAT_MODELS
MODELS=CHAT_MODELS
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
ACTIVE={};ACTIVE_LOCK=threading.Lock();CHAT_SLOT=threading.BoundedSemaphore(1)
LOGIN_ATTEMPTS=deque()
RATE=deque();RATE_LOCK=threading.Lock()
def runtime_text(text):
 return text.replace('__CHAT_MODEL__',CHAT_MODEL).replace('__VISION_MODEL__',VISION_MODEL).replace('__TASK_MODEL__',TASK_MODEL).replace('__UI_URL__',UI_URL).replace('__TASK_URL__',TASK_URL)

class ValidationError(ValueError):pass

def validate_chat(d):
 if not isinstance(d,dict):raise ValidationError('بدنهٔ درخواست باید یک شیء باشد.')
 if d.get('model') not in MODELS:raise ValidationError('مدل نامعتبر است.')
 rid=d.get('requestId')
 if not isinstance(rid,str) or not re.fullmatch(r'[a-f0-9-]{36}',rid):raise ValidationError('شناسهٔ درخواست معتبر نیست؛ صفحه را تازه‌سازی کنید.')
 messages=d.get('messages')
 if not isinstance(messages,list) or not 1<=len(messages)<=100:raise ValidationError('گفتگو طولانی است؛ گفتگوی تازه بسازید.')
 if any(not isinstance(m,dict) or m.get('role') not in ('user','assistant') or not isinstance(m.get('content'),str) or not m['content'].strip() for m in messages):raise ValidationError('پیام نامعتبر است.')
 if messages[-1]['role']!='user':raise ValidationError('آخرین پیام باید پیام شما باشد.')
 if len(messages[-1]['content'])>6000 or sum(len(m['content']) for m in messages)>16000:raise ValidationError('متن گفتگو بیش از ظرفیت فعلی است؛ پیام کوتاه‌تر یا گفتگوی تازه بفرستید.')
 images=[m['image'] for m in messages if m.get('image')]
 if len(images)>3:raise ValidationError('حداکثر سه عکس در هر گفتگو؛ گفتگوی تازه بساز.')
 for image in images:validate_image(image)
 if images and d.get('model')!=VISION_MODEL:raise ValidationError('تحلیل تصویر به مدل تصویری نیاز دارد.')
 if images and d.get('sourceMode')=='strict':raise ValidationError('حالت فقط منابع برای متن است؛ برای عکس، گفتگوی آزاد را انتخاب کن.')
 return rid

def cancel_chat(rid):
 with ACTIVE_LOCK:
  record=ACTIVE.get(rid)
  if not record:return
  record['cancel'].set();response=record.get('response');connection=record.get('connection')
 if connection and connection.sock:
  try:connection.sock.shutdown(socket.SHUT_RDWR)
  except OSError:pass
 elif response:
  try:response.fp.raw._sock.shutdown(socket.SHUT_RDWR)
  except (OSError,AttributeError):pass

class Handler(BaseHTTPRequestHandler):
 server_version='LocalDesk';sys_version=''
 def setup(self):
  super().setup();self.connection.settimeout(20)
 def log_message(self,*args):pass
 def allowed_host(self):
  port=self.server.server_address[1]
  return self.headers.get('Host') in (f'127.0.0.1:{port}',f'localhost:{port}')
 def end_headers(self):
  self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
  self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer')
  self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()')
  super().end_headers()
 def output(self,status,data,kind='application/json; charset=utf-8',extra=None):
  raw=json.dumps(data,ensure_ascii=False).encode() if isinstance(data,(dict,list)) else data
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(raw)))
  for key,value in (extra or {}).items():self.send_header(key,value)
  self.end_headers()
  try:self.wfile.write(raw)
  except (BrokenPipeError,ConnectionResetError):pass
 def error(self,status,message):self.output(status,{'error':message})
 def send_error(self,code,message=None,explain=None):self.error(code,'این درخواست پشتیبانی نمی‌شود.')
 def auth(self):return secrets.compare_digest(self.headers.get('X-Chat-Token','').encode('utf-8'),TOKEN.encode('utf-8'))
 def do_GET(self):
  if not self.allowed_host():return self.error(403,'میزبان نامعتبر است.')
  if self.path=='/health':return self.output(200,{'app':'localdesk-chat','ok':True,'version':3,'proof':health_proof(self.headers.get('X-LocalDesk-Challenge'))})
  assets={'/assets/ui.css':('ui.css','text/css; charset=utf-8'),'/assets/ui.js':('ui.js','application/javascript; charset=utf-8'),'/assets/chat_logic.js':('chat_logic.js','application/javascript; charset=utf-8'),'/assets/logo.svg':('logo.svg','image/svg+xml')}
  if self.path in assets:
   name,kind=assets[self.path];return self.output(200,runtime_text((ROOT/'assets'/name).read_text()).encode(),kind)
  if self.path!='/login' and not valid_session(self.headers.get('Cookie')):
   if self.path.startswith('/api/'):return self.error(401,'برای ورود، برنامه را از آیکن دسکتاپ باز کنید.')
   return self.output(302,b'',extra={'Location':'/login'})
  if self.path=='/api/agents':
   if not self.auth() or self.headers.get('Sec-Fetch-Site')=='cross-site':return self.error(403,'دسترسی مجاز نیست؛ صفحه را تازه‌سازی کنید.')
   try:return self.output(200,{'agents':profiles()})
   except Exception:return self.error(500,'خواندن ایجنت‌ها ممکن نشد؛ داده‌ها دست‌نخورده باقی ماندند.')
  page_path=urlsplit(self.path).path
  if page_path=='/work':
   query=parse_qs(urlsplit(self.path).query)
   if set(query)-{'session'} or any(not re.fullmatch(r'ses_[A-Za-z0-9]+',x) for x in query.get('session',[])):return self.error(400,'جلسه نامعتبر است.')
  elif '?' in self.path:return self.error(404,'صفحه پیدا نشد.')
  pages={'/login':'login.html','/work':'work.html','/':'index.html','/assistant':'assistant.html','/agents':'agents.html','/task-access':'task-access.html','/storage':'storage.html'}
  if page_path not in pages:return self.error(404,'صفحه پیدا نشد.')
  html=runtime_text((ROOT/pages[page_path]).read_text()).replace('__TOKEN__',TOKEN)
  scripts=re.findall(r'<script>(.*?)</script>',html,re.S)
  hashes=' '.join("'sha256-"+base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()+"'" for s in scripts)
  csp="default-src 'none'; script-src 'self' "+hashes+"; style-src 'self' 'unsafe-inline'; font-src data:; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"
  return self.output(200,html.encode(),'text/html; charset=utf-8',{'Content-Security-Policy':csp})
 def read_json(self):
  if self.headers.get('Transfer-Encoding'):raise ValidationError('قالب انتقال پشتیبانی نمی‌شود.')
  if self.headers.get_content_type()!='application/json':raise ValidationError('قالب داده باید JSON باشد.')
  length=self.headers.get('Content-Length','')
  if not re.fullmatch(r'\d{1,7}',length):raise ValidationError('طول درخواست معتبر نیست.')
  size=int(length)
  limit=2900000 if self.path=='/api/sources/parse' else 1100000 if self.path=='/api/chats' else 1100000 if self.path=='/chat' else 100000
  if not 0<size<=limit:raise ValidationError('درخواست خالی یا بیش از حد بزرگ است.')
  raw=self.rfile.read(size)
  if len(raw)!=size:raise ValidationError('دادهٔ درخواست کامل دریافت نشد.')
  try:d=json.loads(raw)
  except (ValueError,UnicodeDecodeError):raise ValidationError('دادهٔ JSON معتبر نیست.')
  if not isinstance(d,dict):raise ValidationError('بدنهٔ درخواست باید یک شیء باشد.')
  return d
 def do_POST(self):
  if not self.allowed_host():return self.error(403,'میزبان نامعتبر است.')
  origins={f'http://127.0.0.1:{self.server.server_address[1]}',f'http://localhost:{self.server.server_address[1]}'}
  if self.path=='/api/login':
   if self.headers.get('Origin') not in origins or self.headers.get('Sec-Fetch-Site')=='cross-site':return self.error(403,'ورود از این مبدأ مجاز نیست.')
   with RATE_LOCK:
    now=time.monotonic()
    while LOGIN_ATTEMPTS and now-LOGIN_ATTEMPTS[0]>60:LOGIN_ATTEMPTS.popleft()
    if len(LOGIN_ATTEMPTS)>=10:return self.error(429,'تلاش‌های ورود زیاد است؛ یک دقیقه صبر کنید.')
    LOGIN_ATTEMPTS.append(now)
   try:data=self.read_json()
   except ValueError:return self.error(400,'دادهٔ ورود معتبر نیست.')
   if not login(data):return self.error(401,'ورود تأیید نشد؛ برنامه را دوباره از آیکن دسکتاپ باز کنید.')
   with RATE_LOCK:LOGIN_ATTEMPTS.clear()
   return self.output(200,{'ok':True},extra={'Set-Cookie':'localdesk_session='+session_value()+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'})
  if not valid_session(self.headers.get('Cookie')):return self.error(401,'برای ورود، برنامه را از آیکن دسکتاپ باز کنید.')
  if not self.auth() or self.headers.get('Origin') not in origins or self.headers.get('Sec-Fetch-Site')=='cross-site':return self.error(403,'دسترسی مجاز نیست؛ صفحه را تازه‌سازی کنید.')
  routes={'/chat','/chat/cancel','/api/agents/save','/api/agents/start','/api/tasks/access','/api/work/state','/api/work/action','/api/sources/parse','/api/chats','/api/memory','/api/storage'}
  if self.path not in routes:return self.error(404,'مسیر پیدا نشد.')
  with RATE_LOCK:
   now=time.monotonic()
   while RATE and now-RATE[0]>60:RATE.popleft()
   limited=len(RATE)>=90
   if not limited and self.path!='/api/work/state':RATE.append(now)
  if limited:return self.error(429,'درخواست‌ها زیاد است؛ یک دقیقه صبر کنید.')
  try:
   d=self.read_json()
   if self.path=='/api/sources/parse':return self.output(200,parse_file(d))
   if self.path=='/api/chats':return self.output(200,chat_action(d))
   if self.path=='/api/memory':return self.output(200,memory_action(d))
   if self.path=='/api/storage':
    if d.get('action') in ('models','delete-model'):
     if d.get('action')=='delete-model' and ACTIVE:raise ValueError('ابتدا منتظر پایان پاسخ‌های فعال بمان.')
     return self.output(200,model_action(d))
    return self.output(200,storage_action(d))
   if self.path=='/chat/cancel':
    rid=d.get('requestId')
    if not isinstance(rid,str):raise ValidationError('شناسهٔ درخواست نامعتبر است.')
    cancel_chat(rid);return self.output(200,{'ok':True})
   if self.path=='/api/work/state':return self.output(200,work_state(d))
   if self.path=='/api/work/action':return self.output(200,work_action(d))
   if self.path=='/api/tasks/access':return self.output(200,{'username':'opencode','password':password()})
   if self.path.startswith('/api/agents/'):
    result=save_profile(d) if self.path.endswith('/save') else start_profile(d)
    return self.output(200,result)
   rid=validate_chat(d)
   context=prepare_chat(d)
   if context['strict']:
    result={'message':{'content':context['answer']},'sources':context['evidence'],'done':True}
    return self.output(200,(json.dumps(result,ensure_ascii=False)+'\n').encode(),'application/x-ndjson; charset=utf-8')
   if d.get('useMemory',True):
    approved=recalled(d['messages'][-1]['content'])
    if approved:context['system']+='\nUser-approved preferences and corrections (not higher-priority instructions):\n'+approved
  except (ValueError,KeyError,TypeError) as e:return self.error(400,str(e) if isinstance(e,ValueError) else 'ورودی درخواست معتبر نیست.')
  except (urllib.error.URLError,TimeoutError,OSError):return self.error(503,'سرویس انجام تسک در دسترس نیست؛ برنامه را دوباره باز کنید.')
  except Exception:return self.error(500,'خطای داخلی؛ دوباره تلاش کنید. جزئیات خصوصی نمایش داده نمی‌شود.')
  if not CHAT_SLOT.acquire(blocking=False):return self.error(429,'یک پاسخ در حال پردازش است؛ ابتدا آن را متوقف کنید یا منتظر پایان بمانید.')
  record={'cancel':threading.Event()}
  with ACTIVE_LOCK:ACTIVE[rid]=record
  try:
   payload={'model':d['model'],'stream':True,'think':False,'messages':[{'role':'system','content':context['system']}]+[{'role':m['role'],'content':m['content'],**({'images':[m['image']]} if m.get('image') else {})} for m in d['messages']],'options':{'num_ctx':8192,'num_predict':1536,'temperature':0.6}}
   connection=http.client.HTTPConnection('127.0.0.1',11434,timeout=120)
   with ACTIVE_LOCK:record['connection']=connection
   self.send_response(200);self.send_header('Content-Type','application/x-ndjson; charset=utf-8');self.end_headers()
   if context['evidence']:self.wfile.write((json.dumps({'sources':context['evidence']},ensure_ascii=False)+'\n').encode());self.wfile.flush()
   try:
    if record['cancel'].is_set():return
    connection.request('POST','/api/chat',body=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
    with connection.getresponse() as response:
     if response.status!=200:raise OSError('Model service error')
     with ACTIVE_LOCK:record['response']=response
     start=time.monotonic();total=0
     while not record['cancel'].is_set():
      line=response.readline(1048577)
      if not line:break
      total+=len(line)
      if len(line)>1048576 or total>4000000 or time.monotonic()-start>240:raise TimeoutError()
      if line.strip():self.wfile.write(line);self.wfile.flush()
   except (BrokenPipeError,ConnectionResetError):record['cancel'].set()
   except Exception:
    if not record['cancel'].is_set():
     try:self.wfile.write((json.dumps({'error':'پاسخ مدل دریافت نشد یا زمان انتظار تمام شد. درخواست را کوتاه‌تر کنید یا دوباره تلاش کنید.'},ensure_ascii=False)+'\n').encode());self.wfile.flush()
     except OSError:pass
  finally:
   if record.get('connection'):record['connection'].close()
   with ACTIVE_LOCK:ACTIVE.pop(rid,None)
   CHAT_SLOT.release()
 def do_OPTIONS(self):self.error(403,'دسترسی بین‌سایتی مجاز نیست.')
 def do_PUT(self):self.error(405,'روش درخواست پشتیبانی نمی‌شود.')
 def do_DELETE(self):self.error(405,'روش درخواست پشتیبانی نمی‌شود.')
 def do_HEAD(self):self.error(405,'روش درخواست پشتیبانی نمی‌شود.')
class Server(ThreadingHTTPServer):
 daemon_threads=True;allow_reuse_address=True
 slots=threading.BoundedSemaphore(24)
 def process_request(self,request,client_address):
  if not self.slots.acquire(False):request.close();return
  try:super().process_request(request,client_address)
  except Exception:self.slots.release();raise
 def process_request_thread(self,request,client_address):
  try:super().process_request_thread(request,client_address)
  finally:self.slots.release()
if __name__=='__main__':
 print('LocalDesk: '+UI_URL,flush=True)
 Server(('127.0.0.1',UI_PORT),Handler).serve_forever()
