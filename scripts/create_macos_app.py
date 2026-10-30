#!/usr/bin/env python3
"""Create a local launcher after installing dependencies; never distribute this path-bound build."""
import plistlib,shlex
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if not (ROOT/'.venv/bin/python').is_file():raise SystemExit('Install dependencies first')
app=ROOT/'build/LocalDesk.app/Contents';(app/'MacOS').mkdir(parents=True,exist_ok=True)
launcher=app/'MacOS/LocalDesk'
launcher.write_text('#!/bin/sh\nexec '+shlex.quote(str(ROOT/'.venv/bin/python'))+' '+shlex.quote(str(ROOT/'app/launch_assistant.py'))+' "$@"\n');launcher.chmod(0o755)
with (app/'Info.plist').open('wb') as file:plistlib.dump({'CFBundleName':'LocalDesk','CFBundleDisplayName':'LocalDesk','CFBundleIdentifier':'local.localdesk.launcher','CFBundleExecutable':'LocalDesk','CFBundlePackageType':'APPL','CFBundleShortVersionString':'0.1.0'},file)
print('Local launcher created in build/LocalDesk.app. It is not notarized and is not part of the source release.')
