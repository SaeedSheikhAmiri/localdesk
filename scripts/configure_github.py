#!/usr/bin/env python3
"""Preview repository governance; --apply requires the real committed code owners."""
import argparse,base64,json,re,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def policy():
 return {'required_status_checks':{'strict':True,'contexts':['Quality (macOS)']},'enforce_admins':True,'required_pull_request_reviews':{'dismiss_stale_reviews':True,'require_code_owner_reviews':True,'required_approving_review_count':1,'require_last_push_approval':True},'restrictions':None,'required_linear_history':True,'allow_force_pushes':False,'allow_deletions':False,'required_conversation_resolution':True}
def api(path,method='GET',body=None):
 args=['gh','api','--method',method,path]
 if body is not None:args+=['--input','-']
 result=subprocess.run(args,input=json.dumps(body) if body is not None else None,text=True,capture_output=True,check=True)
 return json.loads(result.stdout) if result.stdout.strip() else None

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',required=True);p.add_argument('--reviewer',action='append',required=True);p.add_argument('--apply',action='store_true');args=p.parse_args()
 if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',args.repo):p.error('Expected OWNER/REPO')
 owners=[]
 for owner in args.reviewer:
  if not re.fullmatch(r'[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)?',owner):p.error('Invalid reviewer handle')
  owners.append('@'+owner)
 print('Repository: '+args.repo+'; required code owners: '+', '.join(owners))
 print(json.dumps(policy(),indent=2))
 if not args.apply:
  print('Preview only. Commit CODEOWNERS, wait for CI, then explicitly use --apply.');return
 info=api('repos/'+args.repo)
 if not info.get('permissions',{}).get('admin'):raise RuntimeError('Repository administration permission required')
 branch=info.get('default_branch')
 if branch!='main':raise RuntimeError('Preview expects default branch main; review policy for your branch')
 content=api('repos/'+args.repo+'/contents/.github/CODEOWNERS?ref=main')
 text=base64.b64decode(content['content']).decode()
 if not any(line.split()==['*',*owners] for line in text.splitlines() if not line.lstrip().startswith('#')):raise RuntimeError('Remote CODEOWNERS does not match the requested maintainers')
 api('repos/'+args.repo+'/branches/main/protection','PUT',policy())
 api('repos/'+args.repo,'PATCH',{'allow_auto_merge':False,'delete_branch_on_merge':True})
 api('repos/'+args.repo+'/private-vulnerability-reporting','PUT')
 print('Protection configured; verify behavior with an unapproved PR. Visibility was not changed.')
if __name__=='__main__':
 try:main()
 except (RuntimeError,subprocess.CalledProcessError,KeyError) as error:print('Governance setup failed: '+str(error),file=sys.stderr);raise SystemExit(1)
