"""Local service credentials and explicit agent permission policy."""
import os, secrets, json, tempfile, base64
from pathlib import Path
from settings import ROOT,STATE
def password():
 STATE.mkdir(mode=0o700,exist_ok=True);STATE.chmod(0o700)
 path=STATE/'tasks-password'
 if path.is_symlink():raise RuntimeError('Unsafe credential path')
 try:
  fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 except FileExistsError:pass
 else:
  with os.fdopen(fd,'w') as f:f.write(secrets.token_urlsafe(32))
 path.chmod(0o600)
 value=path.read_text().strip()
 if len(value)<32:raise RuntimeError('Invalid service credential')
 return value
def authorization():return 'Basic '+base64.b64encode(('opencode:'+password()).encode()).decode()
def atomic_json(path,data):
 path=Path(path)
 if path.is_symlink():raise ValueError('مسیر ذخیره‌سازی امن نیست.')
 fd,name=tempfile.mkstemp(prefix='.'+path.name+'-',dir=path.parent)
 try:
  with os.fdopen(fd,'w') as f:
   os.fchmod(f.fileno(),0o600);json.dump(data,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
  os.replace(name,path)
 finally:
  if os.path.exists(name):os.unlink(name)
def permissions(access='confirm'):
 sensitive=['**/.env','**/.env.*','**/*.pem','**/*.key','**/id_rsa*','**/id_ed25519*','**/.ssh/**','**/.aws/**','**/auth.json','**/.state/**','**/.config/opencode/**','**/.local/share/opencode/**']
 read={'*':'allow',**{p:'deny' for p in sensitive}}
 edits={'*':'deny' if access=='readonly' else ('allow' if access=='files' else 'ask')}
 for p in sensitive+['opencode.json','config.json','**/opencode.json','**/opencode.jsonc','**/.opencode/**']:
  edits[p]='deny'
 return {'webfetch':'ask','websearch':'ask','question':'deny','read':read,'edit':edits,'bash':'deny' if access=='readonly' else 'ask','task':'deny' if access=='readonly' else 'ask','external_directory':'ask'}

# The UI has its own authenticated, HttpOnly session, independent of CSRF.
import time,hmac,hashlib,fcntl
from http.cookies import SimpleCookie

def ui_secret():
 STATE.mkdir(mode=0o700,exist_ok=True);STATE.chmod(0o700);p=STATE/'ui-secret'
 if p.is_symlink():raise RuntimeError('Unsafe session key path')
 try:fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 except FileExistsError:pass
 else:
  with os.fdopen(fd,'w') as f:f.write(secrets.token_hex(32))
 p.chmod(0o600);value=p.read_text().strip()
 if len(value)!=64:raise RuntimeError('Invalid session key')
 return value.encode()
def session_value():
 payload=str(int(time.time())+28800)+'.'+secrets.token_urlsafe(24)
 return payload+'.'+hmac.new(ui_secret(),payload.encode(),hashlib.sha256).hexdigest()
def valid_session(header):
 try:
  cookie=SimpleCookie();cookie.load(header or '');value=cookie['localdesk_session'].value
  expires,nonce,signature=value.split('.')
  if not int(time.time())<int(expires)<=int(time.time())+28801:return False
  payload=expires+'.'+nonce
  return hmac.compare_digest(signature,hmac.new(ui_secret(),payload.encode(),hashlib.sha256).hexdigest())
 except (ValueError,KeyError,TypeError):return False

def issue_ticket():
 token=secrets.token_urlsafe(32);_tickets(token,False);return token

def consume_ticket(token):
 if not isinstance(token,str) or len(token)!=43:return False
 return _tickets(token,True)
def _tickets(token,consume):
 ui_secret();path=STATE/'login-tickets.json';lock=STATE/'tickets.lock'
 with lock.open('a') as f:
  lock.chmod(0o600);fcntl.flock(f,fcntl.LOCK_EX)
  try:
   records=json.loads(path.read_text()) if path.exists() else {}
   now=time.time();records={k:v for k,v in records.items() if v>now}
   key=hashlib.sha256(token.encode()).hexdigest()
   if consume:ok=records.pop(key,None) is not None
   else:
    records=dict(list(records.items())[-9:]);records[key]=now+120;ok=True
   atomic_json(path,records);return ok
  finally:fcntl.flock(f,fcntl.LOCK_UN)
def login(data):
 if not isinstance(data,dict):return False
 if 'ticket' in data:return consume_ticket(data['ticket'])
 value=data.get('password')
 if not isinstance(value,str):return False
 try:return hmac.compare_digest(value.encode('utf-8'),password().encode('utf-8'))
 except UnicodeError:return False

def health_proof(challenge):
 if not isinstance(challenge,str) or len(challenge)!=64 or any(c not in '0123456789abcdef' for c in challenge):return ''
 return hmac.new(ui_secret(),('localdesk-health:'+challenge).encode(),hashlib.sha256).hexdigest()


def require_web_confirmation(config):
 """Migrate engine policy including existing agent overrides; preserve explicit deny."""
 scopes=[config]+[agent for agent in config.get('agent',{}).values() if isinstance(agent,dict)]
 for scope in scopes:
  policy=scope.get('permission')
  if policy is None:policy={};scope['permission']=policy
  if not isinstance(policy,dict):raise ValueError('Unsupported permission policy; refusing unsafe migration')
  for tool in ('webfetch','websearch'):
   if policy.get(tool)!='deny':policy[tool]='ask'
 return config
