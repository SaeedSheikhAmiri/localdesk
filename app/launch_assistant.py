#!/usr/bin/env python3
"""Start only owned loopback services; data and engine identity are installation-local."""
import argparse,fcntl,hmac,json,os,secrets,signal,socket,subprocess,sys,time,urllib.request,webbrowser
from pathlib import Path
from settings import ROOT,STATE,TASKS,ENGINE_HOME,LOGS,UI_PORT,TASK_PORT,UI_URL,TASK_URL,CHAT_MODEL,VISION_MODEL,TASK_MODEL,OLLAMA,OPENCODE,initialize_directories
from security import password,authorization,issue_ticket,health_proof,atomic_json,permissions,require_web_confirmation
from confinement import command as confined_command
OPENER=urllib.request.build_opener(urllib.request.ProxyHandler({}))

def trusted_task_listener(port):
 try:
  pids=subprocess.check_output(['/usr/sbin/lsof','-t','-iTCP:'+str(port),'-sTCP:LISTEN'],stderr=subprocess.DEVNULL,text=True,timeout=3).split()
  if len(pids)!=1 or not pids[0].isdigit():return False
  rows=subprocess.check_output(['/usr/sbin/lsof','-a','-p',pids[0],'-d','txt','-Fn'],stderr=subprocess.DEVNULL,text=True,timeout=3).splitlines()
  return any(row.startswith('n') and Path(row[1:]).resolve()==OPENCODE.resolve() for row in rows)
 except (OSError,subprocess.SubprocessError):return False

def ready(url,expected=None,auth=False):
 try:
  if auth and not trusted_task_listener(TASK_PORT):return False
  challenge=secrets.token_hex(32)
  headers={'Authorization':authorization()} if auth else {'X-LocalDesk-Challenge':challenge}
  with OPENER.open(urllib.request.Request(url,headers=headers),timeout=2) as response:data=json.load(response)
  if expected=='localdesk-chat':return data.get('app')==expected and hmac.compare_digest(str(data.get('proof','')),health_proof(challenge))
  if expected=='tasks':return data.get('healthy') is True
  return isinstance(data.get('version'),str)
 except Exception:return False

def occupied(port):
 with socket.socket() as sock:return sock.connect_ex(('127.0.0.1',port))==0

def task_config():
 return {'$schema':'https://opencode.ai/config.json','model':TASK_MODEL,'autoupdate':False,'share':'disabled','lsp':False,'formatter':False,'permission':permissions('confirm'),'provider':{'ollama':{'npm':'@ai-sdk/openai-compatible','name':'Ollama (local)','options':{'baseURL':'http://127.0.0.1:11434/v1'},'models':{CHAT_MODEL:{'name':'Local text','tools':True},VISION_MODEL:{'name':'Local vision','tools':True}}}}}

def prepare_tasks():
 initialize_directories()
 for folder in ('.config/opencode','.local/share/opencode','.local/state/opencode','.cache/opencode','Library/Caches/opencode','tmp'):
  path=ENGINE_HOME/folder;path.mkdir(parents=True,exist_ok=True,mode=0o700);path.chmod(0o700)
 for folder in (ENGINE_HOME/'.config/opencode',ENGINE_HOME/'.opencode'):
  folder.mkdir(parents=True,exist_ok=True,mode=0o700);folder.chmod(0o700)
  ignore=folder/'.gitignore'
  if not ignore.exists():ignore.write_text('node_modules/\npackage.json\nbun.lock*\n')
 # Never import another application's existing profiles, history or auth.json.
 path=TASKS/'opencode.json'
 if path.is_symlink():raise RuntimeError('Unsafe task configuration path')
 config=json.loads(path.read_text()) if path.exists() else task_config()
 config['model']=TASK_MODEL;config=require_web_confirmation(config);atomic_json(path,config)

def child_environment(tasks=False):
 env={key:os.environ[key] for key in ('PATH','HOME','USER','LOGNAME','LANG','LC_ALL','TERM','SSL_CERT_FILE','LOCALDESK_DATA_DIR','LOCALDESK_PORT','LOCALDESK_TASK_PORT','LOCALDESK_CHAT_MODEL','LOCALDESK_VISION_MODEL','LOCALDESK_TASK_MODEL','LOCALDESK_OPENCODE','LOCALDESK_OLLAMA') if key in os.environ}
 env['PATH']=os.pathsep.join(dict.fromkeys([str(Path(sys.executable).parent),'/opt/homebrew/bin','/usr/local/bin','/usr/bin','/bin','/usr/sbin','/sbin',os.environ.get('PATH','')]))
 if Path('/etc/ssl/cert.pem').is_file():env.setdefault('SSL_CERT_FILE','/etc/ssl/cert.pem');env['NODE_EXTRA_CA_CERTS']=env['SSL_CERT_FILE']
 if tasks:
  env.update(HOME=str(ENGINE_HOME),TMPDIR=str(ENGINE_HOME/'tmp'),XDG_CONFIG_HOME=str(ENGINE_HOME/'.config'),XDG_DATA_HOME=str(ENGINE_HOME/'.local/share'),XDG_STATE_HOME=str(ENGINE_HOME/'.local/state'),XDG_CACHE_HOME=str(ENGINE_HOME/'.cache'),OPENCODE_SERVER_USERNAME='opencode',OPENCODE_SERVER_PASSWORD=password(),OPENCODE_ENABLE_EXA='1',NPM_CONFIG_CACHE=str(ENGINE_HOME/'.cache/npm'),PIP_CACHE_DIR=str(ENGINE_HOME/'.cache/pip'))
  if TASK_MODEL.startswith('openrouter/'):
   key=os.environ.get('OPENROUTER_API_KEY')
   if not key:raise RuntimeError('Online task mode requires your own OPENROUTER_API_KEY')
   env['OPENROUTER_API_KEY']=key
 return env

def protected_command(args):return confined_command('tasks',args)

def start(args,cwd,log,tasks=False):
 if tasks:prepare_tasks();args=protected_command(args)
 path=LOGS/log
 with path.open('a') as file:
  path.chmod(0o600)
  process=subprocess.Popen(args,cwd=cwd,env=child_environment(tasks),stdin=subprocess.DEVNULL,stdout=file,stderr=file,start_new_session=True)
 atomic_json(STATE/('tasks-process.json' if tasks else 'ui-process.json'),{'pid':process.pid})

def stop():
 for port,url,kind,tasks in [(UI_PORT,UI_URL+'/health','localdesk-chat',False),(TASK_PORT,TASK_URL+'/global/health','tasks',True)]:
  record=STATE/('tasks-process.json' if tasks else 'ui-process.json')
  if not record.exists() or not ready(url,kind,tasks):continue
  pid=json.loads(record.read_text()).get('pid')
  listeners=subprocess.check_output(['/usr/sbin/lsof','-t','-iTCP:'+str(port),'-sTCP:LISTEN'],text=True).split()
  if str(pid) in listeners:os.kill(pid,signal.SIGTERM)
 print('Owned LocalDesk UI/task services stopped. Shared Ollama was not stopped.')

def launch(path='/assistant',open_browser=True,chat_only=False):
 if sys.platform!='darwin':raise RuntimeError('LocalDesk preview supports macOS only')
 initialize_directories();password()
 lock=(STATE/'launcher.lock').open('a');(STATE/'launcher.lock').chmod(0o600)
 with lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  if not ready('http://127.0.0.1:11434/api/version'):
   raise RuntimeError('Start Ollama first (ollama serve). Model downloads are never automatic.')
  services=[]
  if not chat_only:
   if not OPENCODE.is_file():raise RuntimeError('Install OpenCode or set LOCALDESK_OPENCODE; use --chat for chat only')
   services.append((TASK_PORT,TASK_URL+'/global/health','tasks',[str(OPENCODE),'serve','--hostname','127.0.0.1','--port',str(TASK_PORT)],TASKS,'tasks.log',True))
  services.append((UI_PORT,UI_URL+'/health','localdesk-chat',[sys.executable,str(ROOT/'server.py')],ROOT,'server.log',False))
  for port,url,kind,args,cwd,log,tasks in services:
   if ready(url,kind,tasks):continue
   if occupied(port):raise RuntimeError('Configured port is occupied by an unverified service; choose another port')
   start(args,cwd,log,tasks)
   for _ in range(80):
    if ready(url,kind,tasks):break
    time.sleep(.25)
   else:raise RuntimeError('Service did not become ready; inspect private runtime logs')
 if open_browser:webbrowser.open(UI_URL+'/login#'+issue_ticket()+('~chat' if path=='/' else ''))
 print('LocalDesk ready at '+UI_URL)

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--chat',action='store_true');parser.add_argument('--headless',action='store_true');parser.add_argument('--stop',action='store_true');parser.add_argument('--show-password',action='store_true')
 args=parser.parse_args()
 try:
  if args.show_password:initialize_directories();print(password())
  elif args.stop:stop()
  else:launch('/' if args.chat else '/assistant',not args.headless,args.chat)
 except (RuntimeError,ValueError,OSError) as error:print('LocalDesk: '+str(error),file=sys.stderr);return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
