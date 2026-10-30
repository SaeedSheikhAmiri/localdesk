#!/usr/bin/env python3
"""Syntax-check Python and inline/external JavaScript without executing app code."""
import ast,re,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
for folder in ('app','scripts','tests'):
 for path in (ROOT/folder).rglob('*.py'):ast.parse(path.read_text(),filename=str(path.relative_to(ROOT)))
node=shutil.which('node')
if not node:raise SystemExit('Node.js is required for JavaScript syntax checks')
for path in (ROOT/'app/assets').glob('*.js'):subprocess.run([node,'--check',str(path)],check=True)
for path in (ROOT/'app').glob('*.html'):
 for source in re.findall(r'<script(?:\s[^>]*)?>(.*?)</script>',path.read_text(),re.S):
  if not source.strip():continue
  with tempfile.NamedTemporaryFile(suffix='.js',mode='w') as file:
   file.write(source);file.flush();subprocess.run([node,'--check',file.name],check=True)
print('Python and JavaScript syntax: PASS')
