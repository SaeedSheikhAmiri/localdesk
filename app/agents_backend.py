import json,re,uuid,threading,urllib.request,urllib.parse,urllib.error,fcntl
from contextlib import contextmanager
from pathlib import Path
from security import ROOT,STATE,authorization,atomic_json,permissions
WEB_GUIDANCE='Tool compatibility: whenever calling webfetch, ALWAYS provide timeout: 30 and format: markdown explicitly. Never omit these fields. Tool permission decisions still apply.\n\n'
from settings import TASKS,TASK_URL,TASK_MODEL,TASK_MODELS,CHAT_MODEL,VISION_MODEL
STORE=STATE/'agents.json';LOCK=threading.RLock()
MODELS=TASK_MODELS
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))
@contextmanager
def locked():
 STATE.mkdir(mode=0o700,exist_ok=True)
 with LOCK:
  with (STATE/'agents.lock').open('a') as f:
   (STATE/'agents.lock').chmod(0o600);fcntl.flock(f,fcntl.LOCK_EX)
   try:yield
   finally:fcntl.flock(f,fcntl.LOCK_UN)
def profiles():
 if STORE.is_symlink():raise ValueError('مسیر داده امن نیست.')
 items=json.loads(STORE.read_text()) if STORE.exists() else []
 if not isinstance(items,list) or any(not isinstance(a,dict) for a in items):raise ValueError('فایل ایجنت‌ها معتبر نیست؛ نسخهٔ اصلی حفظ شده است.')
 return items
def native(path,body=None,method=None):
 url=TASK_URL+path+'?'+urllib.parse.urlencode({'directory':str(TASKS)})
 from launch_assistant import trusted_task_listener
 from settings import TASK_PORT
 if not trusted_task_listener(TASK_PORT):raise ValueError('موتور تسک معتبر در دسترس نیست؛ راه‌انداز را اجرا کن.')
 headers={'Content-Type':'application/json','Authorization':authorization()}
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
 with OPENER.open(req,timeout=20) as r:
  data=r.read(8000001)
  if len(data)>8000000:raise ValueError('پاسخ سرویس بیش از حد بزرگ است.')
  return json.loads(data) if data else None
def field(d,key,minimum,maximum):
 v=d.get(key)
 if not isinstance(v,str) or not minimum<=len(v.strip())<=maximum:raise ValueError('فیلد '+key+' کامل یا معتبر نیست.')
 return v.strip()
def save_profile(d):
 if not isinstance(d,dict):raise ValueError('ورودی معتبر نیست.')
 title=field(d,'title',1,70);desc=field(d,'description',1,300);prompt=field(d,'prompt',10,16000)
 model=d.get('model');access=d.get('access')
 if not isinstance(model,str) or model not in MODELS or access not in ('readonly','files','confirm'):raise ValueError('مدل یا سطح دسترسی نامعتبر است.')
 with locked():
  items=profiles();agent_id=d.get('id')
  if agent_id is not None and (not isinstance(agent_id,str) or not re.fullmatch(r'localdesk-[a-f0-9]{10}',agent_id) or not any(a.get('id')==agent_id for a in items)):raise ValueError('ایجنت پیدا نشد.')
  if not agent_id:
   if len(items)>=100:raise ValueError('حداکثر ۱۰۰ ایجنت قابل ساخت است.')
   agent_id='localdesk-'+uuid.uuid4().hex[:10]
  statuses=native('/session/status')
  if not isinstance(statuses,dict):raise ValueError('وضعیت سرویس مشخص نیست؛ دوباره تلاش کنید.')
  if any(v.get('type') in ('busy','retry') for v in statuses.values()):raise ValueError('یک تسک در حال اجراست؛ پس از پایان آن ذخیره کنید.')
  path=TASKS/'opencode.json'
  if path.is_symlink():raise ValueError('مسیر تنظیمات امن نیست.')
  old=json.loads(path.read_text());config=json.loads(json.dumps(old))
  definition={'description':title+' — '+desc,'mode':'all','model':model,'prompt':prompt,'permission':permissions(access)}
  config.setdefault('agent',{})[agent_id]=definition
  for provider,models in {'ollama':{CHAT_MODEL:{'name':'Local text model','tools':True},VISION_MODEL:{'name':'Local vision model','tools':True}},'openrouter':{'openrouter/free':{'name':'OpenRouter Free Router','tools':True}}}.items():
   config.setdefault('provider',{}).setdefault(provider,{}).setdefault('models',{}).update(models)
  item={'id':agent_id,'title':title,'description':desc,'prompt':prompt,'model':model,'access':access}
  changed=[item if a.get('id')==agent_id else a for a in items] if any(a.get('id')==agent_id for a in items) else items+[item]
  atomic_json(STATE/'agents-backup.json',items);atomic_json(STATE/'config-backup.json',old)
  atomic_json(path,config)
  try:
   native('/instance/dispose',{},'POST')
   found=native('/agent')
   if not isinstance(found,list) or not any(a.get('name')==agent_id for a in found):raise ValueError('ایجنت در سرویس شناسایی نشد.')
   atomic_json(STORE,changed)
  except Exception:
   atomic_json(path,old)
   try:native('/instance/dispose',{},'POST')
   except Exception:pass
   raise
  return {'agent':item}
def start_profile(d):
 if not isinstance(d,dict):raise ValueError('ورودی معتبر نیست.')
 task=field(d,'task',1,24000);instructions=d.get('instructions','')
 if not isinstance(instructions,str) or len(instructions)>2500:raise ValueError('دستورالعمل گفتگو معتبر نیست.')
 request_id=d.get('requestId')
 if not isinstance(request_id,str) or not re.fullmatch(r'[a-f0-9-]{36}',request_id):raise ValueError('شناسهٔ تسک نامعتبر است؛ صفحه را تازه‌سازی کنید.')
 with locked():
  agent=({'id':'build','title':'دستیار کارهای دستیار محلی','model':TASK_MODEL} if d.get('id')=='build' else next((a for a in profiles() if a.get('id')==d.get('id')),None))
  if not agent:raise ValueError('ایجنت پیدا نشد.')
  path=STATE/'task-runs.json';runs=json.loads(path.read_text()) if path.exists() else {}
  if request_id in runs:
   record=runs[request_id]
   if record.get('agent')!=agent['id'] or record.get('task')!=task:raise ValueError('شناسهٔ تسک قبلاً استفاده شده است.')
   return {'url':record['url'],'session':record['session'],'duplicate':True,'accepted':record.get('accepted',False)}
  provider,model=agent['model'].split('/',1)
  session=native('/session',{'title':agent['title']+' · '+task[:45],'agent':agent['id'],'model':{'providerID':provider,'id':model},'metadata':{'localdeskInstructions':instructions}},'POST');sid=session['id']
  if not re.fullmatch(r'ses_[A-Za-z0-9]+',sid):raise ValueError('شناسهٔ جلسه معتبر نیست.')
  url='/work?session='+sid
  runs[request_id]={'session':sid,'url':url,'agent':agent['id'],'task':task,'accepted':False}
  runs=dict(list(runs.items())[-500:]);atomic_json(path,runs)
  from state_store import recalled
  approved=recalled(task,agent['id'])
  request_text=(('دستورالعمل این گفتگو (در چارچوب مجوز ابزارها):\n'+instructions+'\n\n') if instructions else '')+(('نکته‌های تأییدشدهٔ کاربر:\n'+approved+'\n\n') if approved else '')+'درخواست کاربر:\n'+task
  try:native('/session/'+sid+'/prompt_async',{'agent':agent['id'],'model':{'providerID':provider,'modelID':model},'parts':[{'type':'text','text':WEB_GUIDANCE+request_text}]},'POST')
  except Exception:return {'url':url,'session':sid,'accepted':False}
  runs[request_id]['accepted']=True;atomic_json(path,runs)
  return {'url':url,'session':sid,'accepted':True}
