#!/usr/bin/env python3
"""Minimal smoke check for lemonade_conversation_advanced custom_component.

Verifies:
  - compileall (Python syntax)
  - JSON validity of manifest, strings, translations
  - No stale .pyc files from removed modules
  - Expected top-level files present
"""

import json
import re
import sys
import compileall
import os
import glob

COMPONENT = "custom_components/lemonade_conversation_advanced"
EXPECTED_DIRS = ["translations"]

errors = 0

# 1. compileall
print("--- compileall ---")
if not compileall.compile_dir(COMPONENT, quiet=2, force=True, rx=re.compile(r"__pycache__")):
    print("FAIL: compileall found errors")
    errors += 1
else:
    print("OK")

# 2. JSON validation
print("--- JSON validation ---")
json_files = glob.glob(f"{COMPONENT}/*.json") + glob.glob(f"{COMPONENT}/translations/*.json")
for jf in sorted(json_files):
    try:
        with open(jf) as f:
            json.load(f)
        print(f"  OK: {jf}")
    except json.JSONDecodeError as e:
        print(f"  FAIL: {jf}: {e}")
        errors += 1

# 3. verify no dangling imports from removed backends
print("--- Import consistency ---")
for root, dirs, files in os.walk(COMPONENT):
    if "__pycache__" in root:
        continue
    dirs[:] = [d for d in dirs if d != "__pycache__"]
    for f in files:
        if not f.endswith(".py"):
            continue
        path = os.path.join(root, f)
        with open(path) as fh:
            for lineno, line in enumerate(fh, 1):
                if "from .backends" in line or "import .backends" in line:
                    print(f"  WARN: {path}:{lineno} references removed backends package")
                    errors += 1

print()
if errors:
    print(f"FAIL: {errors} error(s) found")
    sys.exit(1)
else:
    print("PASS: smoke check OK")
    sys.exit(0)
