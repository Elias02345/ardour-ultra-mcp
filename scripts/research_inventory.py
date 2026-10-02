"""Capture source evidence from separately cloned, unmodified upstream repositories."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT.parent / 'research'
records = []
for folder in sorted(UPSTREAM.iterdir()):
    if not (folder / '.git').exists():
        continue
    def git(*args):
        return subprocess.check_output(['git', '-C', str(folder), *args], text=True).strip()
    records.append({'repository': git('remote', 'get-url', 'origin'), 'commit': git('rev-parse', 'HEAD'), 'commit_date': git('show', '-s', '--format=%cI', 'HEAD'), 'checkout': folder.name})
(ROOT / 'research/sources.json').write_text(json.dumps(records, indent=2) + '\n')
for version in ['ardour', 'ardour-9.8']:
    text = (UPSTREAM / version / 'libs/ardour/luabindings.cc').read_text()
    bindings = []
    context = ''
    for line, value in enumerate(text.splitlines(), 1):
        if re.search(r'\.(?:begin|derive).*Class', value):
            context = value.strip()
        match = re.search(r'\.add(?:Ref|Static|ExtC|C)?Function\s*\(\s*"([^"]+)"', value)
        if match:
            bindings.append({'binding': match[1], 'context': context, 'line': line})
    (ROOT / ('research/' + version + '-lua-bindings.json')).write_text(json.dumps(bindings, indent=2) + '\n')
    osc = (UPSTREAM / version / 'libs/surfaces/osc/osc.cc').read_text()
    entries = re.findall(r'REGISTER_CALLBACK\s*\(serv,\s*X_\("([^"]+)"\),\s*"([^"]*)",\s*(\w+)', osc)
    (ROOT / ('research/' + version + '-osc-methods.json')).write_text(json.dumps(sorted(set(entries)), indent=2) + '\n')
