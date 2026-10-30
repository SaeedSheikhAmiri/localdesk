#!/usr/bin/env python3
"""Audit only public source. Output paths/categories, never matching secret values."""
import argparse,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SKIP={'.git','.venv','venv','__pycache__','.pytest_cache'}
BANNED_NAMES={'auth.json','agents.json','tasks-password','ui-secret','login-tickets.json','task-runs.json','.DS_Store'}
BANNED_SUFFIXES={'.db','.sqlite','.log','.png','.jpg','.jpeg','.ttf','.woff','.woff2','.pem','.key','.p12','.icns','.dylib','.so','.zip','.whl','.pyc'}
PATTERNS={
 'absolute workstation home':re.compile(rb'/(?:Users|home)/[A-Za-z0-9_.-]+/'),
 'private key block':re.compile(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----'),
 'provider token':re.compile(rb'\b(?:sk-or-v1-|gh[pousr]_)[A-Za-z0-9_-]{16,}'),
 'fine-grained GitHub token':re.compile(rb'\bgithub_pat_[A-Za-z0-9_]{20,}'),
 'embedded commercial/font payload':re.compile(rb'data:font/[^;,]+;base64,'),
 'email address':re.compile(rb'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'),
}
def inspect(root=ROOT,private_values=()):
 failures=[]
 for path in sorted(root.rglob('*')):
  relative=path.relative_to(root)
  if any(part in SKIP for part in relative.parts):continue
  if path.is_symlink():failures.append((str(relative),'symlink'));continue
  if not path.is_file():continue
  if path.name in BANNED_NAMES or path.suffix.lower() in BANNED_SUFFIXES or (path.name.startswith('.env') and path.name!='.env.example'):
   failures.append((str(relative),'runtime/private/binary file'));continue
  raw=path.read_bytes()
  if len(raw)>500000:failures.append((str(relative),'unexpected large file'))
  for category,pattern in PATTERNS.items():
   if pattern.search(raw):failures.append((str(relative),category))
  for value in private_values:
   if value and value in raw:failures.append((str(relative),'private-origin exact match'));break
 return failures

def private_markers(origin):
 """Optional local-only comparison. Origin paths/values are not written to reports."""
 values=[];origin=Path(origin)
 for name in ('tasks-password','ui-secret'):
  path=origin/'.state'/name
  if path.is_file():values.append(path.read_bytes().strip())
 for path in (origin/'agents.json',Path.home()/'.local/share/opencode/auth.json'):
  if not path.is_file():continue
  try:data=json.loads(path.read_text())
  except Exception:continue
  def walk(value):
   if isinstance(value,str) and len(value)>=32:values.append(value.encode())
   elif isinstance(value,dict):
    for child in value.values():walk(child)
   elif isinstance(value,list):
    for child in value:walk(child)
  walk(data)
 return values

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--private-origin',type=Path);parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args()
 failures=inspect(args.root.resolve(),private_markers(args.private_origin) if args.private_origin else ())
 for path,category in failures:print(category+': '+path)
 print('Public source audit: '+('FAIL' if failures else 'PASS')+' ('+str(len(failures))+' findings)')
 return bool(failures)
if __name__=='__main__':raise SystemExit(main())
