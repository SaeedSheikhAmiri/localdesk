"""Validated runtime configuration; no workstation-specific paths or credentials."""
import os,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
HOME=Path.home().resolve()
def absolute_env(name,default):
 value=Path(os.environ.get(name,str(default))).expanduser()
 if not value.is_absolute():raise ValueError(name+' must be an absolute path')
 return value.resolve()
DATA=absolute_env('LOCALDESK_DATA_DIR',HOME/'Library/Application Support/LocalDesk' if sys.platform=='darwin' else HOME/'.local/share/localdesk')
if DATA==HOME or DATA==Path('/') or DATA==ROOT or ROOT in DATA.parents:
 raise ValueError('Runtime data must be a dedicated directory outside the source tree')
STATE=DATA/'state';TASKS=DATA/'workspace';ENGINE_HOME=DATA/'engine-home';LOGS=DATA/'logs'
def port(name,default):
 value=int(os.environ.get(name,default))
 if not 1024<=value<=65535:raise ValueError(name+' must be an unprivileged TCP port')
 return value
UI_PORT=port('LOCALDESK_PORT',8876);TASK_PORT=port('LOCALDESK_TASK_PORT',8877)
if UI_PORT==TASK_PORT or 11434 in (UI_PORT,TASK_PORT):raise ValueError('Service ports must be distinct')
UI_URL=f'http://127.0.0.1:{UI_PORT}';TASK_URL=f'http://127.0.0.1:{TASK_PORT}'
def model(name,default):
 value=os.environ.get(name,default)
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:/-]{0,160}',value):raise ValueError('Invalid model identifier: '+name)
 return value
CHAT_MODEL=model('LOCALDESK_CHAT_MODEL','qwen2.5:7b-instruct')
VISION_MODEL=model('LOCALDESK_VISION_MODEL','qwen3-vl:8b')
TASK_MODEL=model('LOCALDESK_TASK_MODEL','ollama/'+CHAT_MODEL)
if TASK_MODEL.split('/',1)[0] not in ('ollama','openrouter') or '/' not in TASK_MODEL:raise ValueError('Task model must use ollama/ or openrouter/')
CHAT_MODELS={CHAT_MODEL,VISION_MODEL}
TASK_MODELS={'ollama/'+CHAT_MODEL,'ollama/'+VISION_MODEL,'openrouter/openrouter/free',TASK_MODEL}
OLLAMA=Path(os.environ.get('LOCALDESK_OLLAMA',shutil.which('ollama') or 'ollama')).expanduser()
OPENCODE=Path(os.environ.get('LOCALDESK_OPENCODE',shutil.which('opencode') or str(HOME/'.opencode/bin/opencode'))).expanduser()
def initialize_directories():
 for path in (DATA,STATE,TASKS,ENGINE_HOME,LOGS):
  if path.is_symlink():raise ValueError('Runtime directory cannot be a symlink')
  path.mkdir(parents=True,exist_ok=True,mode=0o700);path.chmod(0o700)
