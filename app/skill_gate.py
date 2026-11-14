"""Fail-closed gate for third-party agent skills. The scanner inspects, never executes."""
import json,shutil,subprocess
from pathlib import Path
TIMEOUT=180
VERDICTS=('SAFE','CAUTION','DO_NOT_INSTALL')
def scanner():
 local=Path(__file__).resolve().parents[1]/'.venv/bin/skillspector'
 if local.is_file():return str(local)
 return shutil.which('skillspector') or ''
def scan(target):
 """Static-only scan. No LLM receives skill contents; dependency names go to OSV.dev."""
 path=Path(target).expanduser()
 if path.is_symlink():raise ValueError('اسکن اسکیل از مسیر symlink مجاز نیست.')
 if not path.exists():raise ValueError('مسیر اسکیل پیدا نشد.')
 cli=scanner()
 if not cli:raise ValueError('اسکنر امنیت اسکیل نصب نیست؛ scripts/scan-skill.sh را نصب و اجرا کن.')
 try:result=subprocess.run([cli,'scan',str(path),'--no-llm','--format','json'],capture_output=True,timeout=TIMEOUT)
 except subprocess.TimeoutExpired:raise ValueError('اسکن امنیتی اسکیل بیش از حد طول کشید.')
 if result.returncode not in (0,1):raise ValueError('اسکن امنیتی اسکیل ناموفق بود.')
 try:data=json.loads(result.stdout)
 except (TypeError,ValueError):raise ValueError('گزارش اسکن امنیتی قابل خواندن نیست.')
 risk=data.get('risk_assessment') if isinstance(data,dict) else None
 score=risk.get('score') if isinstance(risk,dict) else None
 if not isinstance(risk,dict) or risk.get('recommendation') not in VERDICTS or not isinstance(score,(int,float)) or isinstance(score,bool):raise ValueError('گزارش اسکن امنیتی کامل نیست.')
 issues=data.get('issues')
 return {'score':score,'severity':risk.get('severity'),'recommendation':risk['recommendation'],'issues':len(issues) if isinstance(issues,list) else 0}
def require_safe(target):
 verdict=scan(target)
 if verdict['recommendation']!='SAFE':raise ValueError('نصب این اسکیل تأیید نشد: امتیاز خطر '+str(verdict['score'])+' از ۱۰۰ ('+str(verdict['severity'])+').')
 return verdict
