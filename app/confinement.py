"""Generate macOS file-access policies from this installation's runtime paths."""
import json,sys
from pathlib import Path
from settings import ROOT,STATE,DATA,TASKS,ENGINE_HOME,OPENCODE
from security import atomic_json

def quote(path):return json.dumps(str(Path(path).resolve()),ensure_ascii=False)
def rules(operation,paths,kind='subpath'):
 return '('+operation+'\n '+'\n '.join('('+kind+' '+quote(p)+')' for p in dict.fromkeys(paths))+')\n'
def parser_profile():
 import tempfile
 from settings import HOME
 blocked=[HOME,DATA,Path('/Users'),Path('/Volumes'),Path('/private/tmp'),Path(tempfile.gettempdir())]
 allowed=[ROOT,Path(sys.prefix),Path(sys.base_prefix)]
 return '(version 1)\n(allow default)\n(deny network*)\n(deny file-write*)\n'+rules('deny file-read-data',blocked)+rules('allow file-read-data',allowed)
def task_profile():
 binary=OPENCODE.resolve()
 read=[TASKS,ENGINE_HOME,binary.parent,binary.parent.parent/'node_modules',Path('/usr'),Path('/bin'),Path('/sbin'),Path('/System'),Path('/opt/homebrew'),Path('/Library/Apple'),Path('/private/etc'),Path('/dev'),Path('/private/var/db/timezone')]
 write=[TASKS,ENGINE_HOME/'.local/share',ENGINE_HOME/'.local/state',ENGINE_HOME/'.cache',ENGINE_HOME/'Library/Caches',ENGINE_HOME/'tmp']
 deny=[STATE,ROOT,ENGINE_HOME/'.config',TASKS/'opencode.json']
 from settings import HOME
 import tempfile
 blocked=[HOME,DATA,Path('/Users'),Path('/Volumes'),Path('/private/tmp'),Path(tempfile.gettempdir())]
 env_rules=r'(deny file-read-data (regex #"/\.env($|\.)"))'+'\n'+r'(deny file-write* (regex #"/\.env($|\.)"))'+'\n'
 return '(version 1)\n(allow default)\n(deny file-write*)\n'+rules('deny file-read-data',blocked)+rules('allow file-read-data',read)+rules('allow file-write*',write)+rules('deny file-write*',deny)+rules('allow file-write*',[Path('/dev/null'),ENGINE_HOME/'.config/opencode/.gitignore',ENGINE_HOME/'.opencode/.gitignore'],'literal')+env_rules

def profile_path(kind):
 if sys.platform!='darwin' or not Path('/usr/bin/sandbox-exec').is_file():raise RuntimeError('This preview requires macOS sandbox-exec; refusing unconfined execution')
 STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
 path=STATE/('parser.sb' if kind=='parser' else 'tasks.sb')
 if path.is_symlink():raise RuntimeError('Unsafe policy path')
 content=parser_profile() if kind=='parser' else task_profile()
 import os,tempfile
 fd,name=tempfile.mkstemp(prefix='.policy-',dir=STATE)
 try:
  with os.fdopen(fd,'w') as file:file.write(content)
  Path(name).chmod(0o600);os.replace(name,path)
 finally:
  if Path(name).exists():Path(name).unlink()
 return path
def command(kind,args):return ['/usr/bin/sandbox-exec','-f',str(profile_path(kind)),*map(str,args)]
