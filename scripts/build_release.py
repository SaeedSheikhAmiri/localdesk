#!/usr/bin/env python3
"""Build an allowlisted source ZIP; no git metadata or runtime files are included."""
import argparse,hashlib,json,sys,zipfile
from pathlib import Path,PurePosixPath
from audit_public import ROOT,inspect

def build(output):
 findings=inspect()
 if findings:raise ValueError('Public audit failed; no archive produced')
 entries=json.loads((ROOT/'PUBLIC_FILES.json').read_text())
 if not isinstance(entries,list) or len(entries)!=len(set(entries)):raise ValueError('Invalid public manifest')
 allowed=set(entries)
 actual={str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file() and not any(part in {'.git','.venv','venv','__pycache__','.pytest_cache'} for part in p.relative_to(ROOT).parts)}
 if actual!=allowed:raise ValueError('Source tree and public allowlist differ; review the manifest')
 output=output.resolve()
 if output==ROOT or ROOT in output.parents:raise ValueError('Archive must be outside the public source tree')
 version=(ROOT/'VERSION').read_text().strip();prefix='localdesk-'+version
 output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
  for name in sorted(entries):
   path=PurePosixPath(name)
   if path.is_absolute() or '..' in path.parts or (ROOT/name).is_symlink():raise ValueError('Unsafe manifest entry')
   raw=(ROOT/name).read_bytes();info=zipfile.ZipInfo(prefix+'/'+name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(0o100755 if name.endswith('.sh') or name.endswith('.command') else 0o100644)<<16
   archive.writestr(info,raw)
 digest=hashlib.sha256(output.read_bytes()).hexdigest();output.with_suffix(output.suffix+'.sha256').write_text(digest+'  '+output.name+'\n')
 print(output.name+' built from '+str(len(entries))+' reviewed files; SHA-256 '+digest)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
 try:build(args.output)
 except (ValueError,OSError) as error:print(str(error),file=sys.stderr);raise SystemExit(1)
