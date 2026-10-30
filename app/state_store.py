"""Owner-only durable chat, approved memory and feedback store."""
import sqlite3,json,time,re,uuid,threading,shutil
from contextlib import contextmanager
from pathlib import Path
from security import STATE,ROOT
from settings import LOGS,CHAT_MODELS
from sources import context_settings,tokens,validate_image
LOCK=threading.RLock()
def key(value):
 if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',value):raise ValueError('شناسه معتبر نیست.')
 return value
@contextmanager
def db():
 STATE.mkdir(mode=0o700,exist_ok=True);path=STATE/'chats.sqlite'
 if path.is_symlink():raise ValueError('مسیر داده امن نیست.')
 with LOCK:
  con=sqlite3.connect(path,timeout=10);path.chmod(0o600);con.row_factory=sqlite3.Row
  con.execute('CREATE TABLE IF NOT EXISTS chats(id TEXT PRIMARY KEY,data TEXT NOT NULL,status TEXT NOT NULL DEFAULT "active",updated REAL NOT NULL)')
  con.execute('CREATE TABLE IF NOT EXISTS tombstones(id TEXT PRIMARY KEY,deleted REAL NOT NULL)')
  con.execute('CREATE TABLE IF NOT EXISTS memory(id TEXT PRIMARY KEY,text TEXT NOT NULL,scope TEXT NOT NULL,created REAL NOT NULL)')
  con.execute('CREATE TABLE IF NOT EXISTS feedback(id TEXT PRIMARY KEY,question TEXT NOT NULL,answer TEXT NOT NULL,created REAL NOT NULL)')
  try:yield con;con.commit()
  except Exception:con.rollback();raise
  finally:con.close()
def chat_validate(value):
 if not isinstance(value,dict):raise ValueError('گفتگو معتبر نیست.')
 key(value.get('id'))
 if not isinstance(value.get('title'),str) or not 1<=len(value['title'])<=120:raise ValueError('نام گفتگو باید بین ۱ تا ۱۲۰ حرف باشد.')
 messages=value.get('messages')
 if not isinstance(messages,list) or len(messages)>500 or any(not isinstance(m,dict) or m.get('role') not in ('user','assistant') or not isinstance(m.get('content'),str) or len(m['content'])>100000 for m in messages):raise ValueError('پیام‌های گفتگو معتبر یا بیش از حد بزرگ هستند.')
 for m in messages:
  if m.get('image'):validate_image(m['image'])
 context_settings({**value,'sourceMode':'off'})
 if len(json.dumps(value,ensure_ascii=False).encode())>1000000:raise ValueError('این گفتگو بیش از حد بزرگ است؛ یک شاخه یا گفتگوی تازه بساز.')
 if value.get('parentId'):key(value['parentId'])
 return value

def chat_action(d):
 action=d.get('action')
 with db() as con:
  if action=='list':
   result=[]
   for r in con.execute('SELECT * FROM chats ORDER BY updated DESC'):
    value=json.loads(r['data']);result.append({k:value.get(k) for k in ('id','title','parentId')}|{'messages':[],'_summary':True,'status':r['status'],'serverUpdated':r['updated']})
   return {'chats':result,'deletedIds':[r[0] for r in con.execute('SELECT id FROM tombstones')]}
  if action=='get':
   r=con.execute('SELECT * FROM chats WHERE id=?',(key(d.get('id')),)).fetchone()
   if not r:raise ValueError('گفتگو پیدا نشد.')
   return {'chat':json.loads(r['data'])|{'status':r['status'],'serverUpdated':r['updated']}}
  if action=='save':
   chat=chat_validate(d.get('chat'));identity=chat['id'];old=con.execute('SELECT * FROM chats WHERE id=?',(identity,)).fetchone()
   if con.execute('SELECT id FROM tombstones WHERE id=?',(identity,)).fetchone():raise ValueError('این گفتگو حذف شده است و دوباره ذخیره نمی‌شود.')
   if old and old['status']!='active':raise ValueError('برای ویرایش، گفتگو را ابتدا از آرشیو یا سطل برگردان.')
   expected=d.get('expected')
   if old and (not isinstance(expected,(int,float)) or expected!=old['updated']):raise ValueError('این گفتگو در تب دیگری تغییر کرده؛ صفحه را تازه‌سازی کن تا نسخهٔ جدید را ببینی.')
   if not old and con.execute('SELECT count(*) FROM chats').fetchone()[0]>=1000:raise ValueError('ظرفیت گفتگوها پر شده؛ از مدیریت فضا کمک بگیر.')
   total=con.execute('SELECT coalesce(sum(length(cast(data as blob))),0) FROM chats').fetchone()[0]
   if total-(len(old['data'].encode()) if old else 0)+len(json.dumps(chat,ensure_ascii=False).encode())>40*1024*1024:raise ValueError('فضای دادهٔ گفتگوها به ۴۰ مگابایت رسیده؛ از داشبورد فضا، موارد غیرضروری را پاک کن.')
   stamp=time.time_ns()/1000000;copy=dict(chat);copy.pop('status',None);copy.pop('serverUpdated',None);copy.pop('_summary',None);copy.pop('pendingSync',None)
   con.execute('INSERT INTO chats(id,data,status,updated) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,updated=excluded.updated',(identity,json.dumps(copy,ensure_ascii=False),'active',stamp))
   return {'updated':stamp}
  identity=key(d.get('id'));old=con.execute('SELECT * FROM chats WHERE id=?',(identity,)).fetchone()
  if not old:raise ValueError('گفتگو پیدا نشد.')
  if action=='rename':
   title=d.get('title')
   if not isinstance(title,str) or not 1<=len(title.strip())<=120:raise ValueError('نام معتبر نیست.')
   value=json.loads(old['data']);value['title']=title.strip();value['customTitle']=True
   con.execute('UPDATE chats SET data=?,updated=? WHERE id=?',(json.dumps(value,ensure_ascii=False),time.time_ns()/1000000,identity))
  elif action in ('archive','trash','restore'):
   con.execute('UPDATE chats SET status=?,updated=? WHERE id=?',({'archive':'archived','trash':'trash','restore':'active'}[action],time.time_ns()/1000000,identity))
  else:raise ValueError('عملیات گفتگو ناشناخته است.')
 return {'ok':True}

def memory_action(d):
 action=d.get('action')
 with db() as con:
  if action=='list':return {'notes':[dict(r) for r in con.execute('SELECT * FROM memory ORDER BY created DESC')]}
  if action=='save':
   text=d.get('text');scope=d.get('scope','global')
   if not isinstance(text,str) or not 1<=len(text.strip())<=2000 or not isinstance(scope,str) or (scope!='global' and not re.fullmatch(r'agent:localdesk-[a-f0-9]{10}',scope)):raise ValueError('متن حافظه یا محدوده معتبر نیست.')
   if con.execute('SELECT count(*) FROM memory').fetchone()[0]>=100:raise ValueError('حداکثر ۱۰۰ یادداشت؛ ابتدا موارد قدیمی را حذف کن.')
   con.execute('INSERT INTO memory VALUES(?,?,?,?)',(uuid.uuid4().hex,text.strip(),scope,time.time()))
  elif action=='delete':con.execute('DELETE FROM memory WHERE id=?',(key(d.get('id')),))
  elif action=='feedback':
   q=d.get('question');a=d.get('answer')
   if not isinstance(q,str) or not isinstance(a,str) or not 1<=len(q)<=6000 or not 1<=len(a)<=10000:raise ValueError('پرسش و پاسخ اصلاح‌شده معتبر نیستند.')
   if con.execute('SELECT count(*) FROM feedback').fetchone()[0]>=1000:raise ValueError('ظرفیت اصلاحات پر است.')
   con.execute('INSERT INTO feedback VALUES(?,?,?,?)',(uuid.uuid4().hex,q,a,time.time()))
  elif action=='export':return {'text':'\n'.join(json.dumps({'messages':[{'role':'user','content':r['question']},{'role':'assistant','content':r['answer']}]},ensure_ascii=False) for r in con.execute('SELECT question,answer FROM feedback ORDER BY created'))}
  else:raise ValueError('عملیات حافظه ناشناخته است.')
 return {'ok':True}

def recalled(question,agent=None):
 query=tokens(question)
 with db() as con:
  notes=[r['text'] for r in con.execute('SELECT * FROM memory WHERE scope=? OR scope=? ORDER BY created DESC LIMIT 100',('global','agent:'+str(agent or '')))]
  corrections=[(len(query & tokens(r['question'])),r) for r in con.execute('SELECT question,answer FROM feedback ORDER BY created DESC LIMIT 500')]
 ranked=sorted(corrections,key=lambda v:v[0],reverse=True)
 notes.sort(key=lambda text:len(query & tokens(text)),reverse=True)
 facts=notes[:8]+['اصلاح تأییدشدهٔ کاربر — پرسش: '+r['question']+'؛ پاسخ درست: '+r['answer'] for score,r in ranked[:2] if score>=2]
 return '\n'.join(facts)[:5000]

def folder_size(path):
 total=0
 if not path.exists():return 0
 for p in path.rglob('*'):
  try:
   if not p.is_symlink() and p.is_file():total+=p.stat().st_size
  except OSError:pass
 return total

def storage_action(d):
 action=d.get('action')
 if action=='status':
  disk=shutil.disk_usage(ROOT)
  with db() as con:
   counts={r[0]:r[1] for r in con.execute('SELECT status,count(*) FROM chats GROUP BY status')}
   notes=con.execute('SELECT count(*) FROM memory').fetchone()[0];feedback=con.execute('SELECT count(*) FROM feedback').fetchone()[0]
  return {'disk':{'total':disk.total,'free':disk.free,'used':disk.used},'appBytes':folder_size(ROOT),'modelsBytes':folder_size(Path.home()/'.ollama/models'),'databaseBytes':sum(p.stat().st_size for p in STATE.glob('chats.sqlite*') if p.is_file() and not p.is_symlink()),'logsBytes':sum(p.stat().st_size for p in LOGS.glob('*.log') if not p.is_symlink()),'chats':counts,'memoryCount':notes,'feedbackCount':feedback}
 if d.get('confirm') is not True:raise ValueError('این پاک‌سازی به تأیید نیاز دارد.')
 if action=='purge-trash':
  with db() as con:
   ids=[r[0] for r in con.execute('SELECT id FROM chats WHERE status="trash"')]
   con.executemany('INSERT OR REPLACE INTO tombstones VALUES(?,?)',[(i,time.time()) for i in ids]);con.execute('DELETE FROM chats WHERE status="trash"')
  with db() as con:con.execute('VACUUM')
  return {'ok':True,'count':len(ids)}
 if action=='clear-logs':
  for name in ['server.log','tasks.log','ollama-start.log','sandbox-smoke.log']:
   p=LOGS/name
   if p.exists() and not p.is_symlink():
    with p.open('w'):pass
  return {'ok':True}
 raise ValueError('عملیات پاک‌سازی ناشناخته است.')

# Model cleanup is through Ollama's own API, never arbitrary file deletion.
import urllib.request
MODEL_OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
def model_request(path,body=None,method=None):
 req=urllib.request.Request('http://127.0.0.1:11434'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'},method=method)
 with MODEL_OPENER.open(req,timeout=10) as response:
  raw=response.read(1000000);return json.loads(raw) if raw else {}
def model_action(d):
 tags=model_request('/api/tags').get('models',[]);loaded={m['name'] for m in model_request('/api/ps').get('models',[])}
 allowed=CHAT_MODELS
 if d.get('action')=='models':return {'models':[{'name':m['name'],'size':m.get('size',0),'loaded':m['name'] in loaded,'removable':m['name'] in allowed} for m in tags]}
 name=d.get('name')
 if d.get('action')!='delete-model' or d.get('confirm') is not True or not isinstance(name,str) or name not in allowed or name not in {m['name'] for m in tags}:raise ValueError('مدل یا تأیید حذف معتبر نیست.')
 if name in loaded:raise ValueError('مدل در حافظه است؛ تا پایان استفاده و آزادشدن آن صبر کن.')
 model_request('/api/delete',{'name':name},'DELETE');return {'ok':True}
