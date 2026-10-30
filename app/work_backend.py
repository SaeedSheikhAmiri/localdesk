"""Restricted task UI adapter; never accepts arbitrary upstream URLs or paths."""
import re,time
from agents_backend import native,profiles,start_profile,TASKS,MODELS,WEB_GUIDANCE

def session_id(d):
 sid=d.get('session')
 if not isinstance(sid,str) or not re.fullmatch(r'ses_[A-Za-z0-9]+',sid):raise ValueError('جلسه معتبر نیست.')
 info=native('/session/'+sid)
 if info.get('directory')!=str(TASKS):raise ValueError('این جلسه متعلق به پوشهٔ کارهای دستیار محلی نیست.')
 return sid,info

def work_state(d):
 items=native('/session')
 view=d.get('filter','active')
 if view not in ('active','archived','trash'):raise ValueError('فیلتر گفتگو معتبر نیست.')
 def status(s):return 'trash' if s.get('metadata',{}).get('localdeskTrash') else ('archived' if s.get('time',{}).get('archived') else 'active')
 sessions=[{'id':s['id'],'title':s.get('title','گفتگو'),'status':status(s)} for s in items if s.get('directory')==str(TASKS) and status(s)==view][:100]
 result={'sessions':sessions,'agents':[{'id':a['id'],'title':a['title']} for a in profiles()]}
 if not d.get('session'):return result
 sid,info=session_id(d)
 result['instructions']=info.get('metadata',{}).get('localdeskInstructions','')
 result['title']=info.get('title','گفتگو')
 result['archived']=bool(info.get('time',{}).get('archived'))
 result['selectedAgent']=info.get('agent') or 'build'
 model=info.get('model') or {}
 result['selectedModel']=str(model.get('providerID',''))+'/'+str(model.get('id',''))
 messages=native('/session/'+sid+'/message')
 result['messages']=[]
 for m in messages[-100:]:
  entry={'id':m.get('info',{}).get('id'),'role':m.get('info',{}).get('role'),'parts':[]}
  error=m.get('info',{}).get('error')
  if error:entry['error']='مدل پاسخ نداد؛ سهمیه، اتصال اینترنت یا انتخاب مدل را بررسی کنید.'
  for p in m.get('parts',[]):
   if p.get('type')=='text':
    text=p.get('text','')
    if entry['role']=='user' and text.startswith(WEB_GUIDANCE):text=text[len(WEB_GUIDANCE):]
    entry['parts'].append({'type':'text','text':text[:100000]})
   elif p.get('type')=='tool':
    state=p.get('state',{});entry['parts'].append({'type':'tool','tool':p.get('tool'),'status':state.get('status'),'input':str(state.get('input',''))[:8000],'output':str(state.get('output',state.get('error','')))[:12000]})
  result['messages'].append(entry)
 result['status']=native('/session/status').get(sid,{'type':'idle'})
 try:pending=native('/permission')
 except Exception as e:
  import urllib.error
  if not isinstance(e,urllib.error.HTTPError) or e.code!=400:raise
  pending=[]
  result['permissionError']='موتور نتوانست درخواست تأیید ابزار را نمایش دهد. تسک را متوقف کن و درخواست را دوباره بفرست؛ هیچ مجوزی خودکار صادر نشد.'
 result['permissions']=[{'id':p['id'],'permission':p.get('permission'),'patterns':p.get('patterns',[])} for p in pending if p.get('sessionID')==sid]
 return result

def work_action(d):
 action=d.get('action')
 if action=='purge-trash':
  if d.get('confirm') is not True:raise ValueError('حذف دائمی به تأیید نیاز دارد.')
  if any(v.get('type') in ('busy','retry') for v in native('/session/status').values()):raise ValueError('ابتدا منتظر پایان تسک‌ها بمان.')
  count=0
  for item in native('/session'):
   if item.get('directory')==str(TASKS) and item.get('metadata',{}).get('localdeskTrash'):
    native('/session/'+item['id'],None,'DELETE');count+=1
  return {'ok':True,'count':count}
 if action=='start':return start_profile({'id':d.get('agent','build'),'task':d.get('task'),'requestId':d.get('requestId'),'instructions':d.get('instructions','')})
 sid,info=session_id(d)
 if action in ('rename','archive','trash','restore'):
  if native('/session/status').get(sid,{}).get('type') in ('busy','retry'):raise ValueError('ابتدا منتظر پایان تسک بمانید.')
  if action=='rename':
   title=d.get('title')
   if not isinstance(title,str) or not 1<=len(title.strip())<=120:raise ValueError('نام گفتگو معتبر نیست.')
   native('/session/'+sid,{'title':title.strip()},'PATCH')
  else:
   metadata=dict(info.get('metadata') or {});metadata['localdeskTrash']=action=='trash'
   native('/session/'+sid,{'metadata':metadata,'time':{'archived':0 if action=='restore' else int(time.time()*1000)}},'PATCH')
  return {'ok':True}
 if action=='fork':
  mid=d.get('messageId')
  if not isinstance(mid,str) or not re.fullmatch(r'msg_[A-Za-z0-9]+',mid):raise ValueError('پیام شاخه معتبر نیست.')
  if not any(m.get('info',{}).get('id')==mid for m in native('/session/'+sid+'/message')):raise ValueError('این پیام متعلق به گفتگو نیست.')
  if native('/session/status').get(sid,{}).get('type') in ('busy','retry'):raise ValueError('ابتدا منتظر پایان تسک بمانید.')
  fork=native('/session/'+sid+'/fork',{'messageID':mid},'POST')
  return {'session':fork['id']}
 if action=='stop':native('/session/'+sid+'/abort',{},'POST');return {'ok':True}
 if action=='reply':
  if info.get('time',{}).get('archived'):raise ValueError('ابتدا گفتگو را از آرشیو یا سطل برگردان.')
  task=d.get('task');rid=d.get('requestId')
  if not isinstance(task,str) or not 1<=len(task.strip())<=24000 or not isinstance(rid,str) or not re.fullmatch(r'[a-f0-9-]{36}',rid):raise ValueError('پیام معتبر نیست.')
  if native('/session/status').get(sid,{}).get('type') in ('busy','retry'):raise ValueError('ابتدا منتظر پایان پاسخ بمانید یا آن را متوقف کنید.')
  agent=info.get('agent') or 'build'
  if agent!='build' and not any(p['id']==agent for p in profiles()):raise ValueError('ایجنت این جلسه دیگر در دسترس نیست.')
  model=info.get('model') or {'providerID':'openrouter','id':'openrouter/free'}
  if model['providerID']+'/'+model['id'] not in MODELS:raise ValueError('مدل این جلسه در رابط دستیار محلی پشتیبانی نمی‌شود؛ از رابط پیشرفته استفاده کنید.')
  from state_store import recalled
  instructions=info.get('metadata',{}).get('localdeskInstructions','')
  approved=recalled(task,agent)
  request_text=(('دستورالعمل این گفتگو:\n'+instructions+'\n\n') if instructions else '')+(('نکته‌های تأییدشدهٔ کاربر:\n'+approved+'\n\n') if approved else '')+'درخواست کاربر:\n'+task
  native('/session/'+sid+'/prompt_async',{'messageID':'msg_'+rid.replace('-',''),'agent':agent,'model':{'providerID':model['providerID'],'modelID':model['id']},'parts':[{'type':'text','text':WEB_GUIDANCE+request_text}]},'POST');return {'ok':True}
 if action=='permission':
  pid=d.get('permission');reply=d.get('reply')
  if not isinstance(pid,str) or not re.fullmatch(r'per_[A-Za-z0-9]+',pid) or reply not in ('once','reject'):raise ValueError('درخواست تأیید معتبر نیست.')
  pending=native('/permission')
  if not any(p.get('id')==pid and p.get('sessionID')==sid for p in pending):raise ValueError('درخواست تأیید پیدا نشد یا منقضی شده است.')
  native('/permission/'+pid+'/reply',{'reply':reply},'POST');return {'ok':True}
 raise ValueError('عملیات ناشناخته است.')
