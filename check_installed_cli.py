"""Check the installed command from a clean working directory."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

name = 'array-alias-map'
source = Path(__file__).parent
with tempfile.TemporaryDirectory() as root:
    work = Path(root)
    for fixture in source.glob('*.json'):
        shutil.copy2(fixture, work / fixture.name)
    if (source / 'make_fixture.py').exists():
        shutil.copy2(source / 'make_fixture.py', work / 'make_fixture.py')
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    if name == 'parquet-cast-preflight':
        subprocess.run([os.environ.get('EXAMPLE_PYTHON', 'python'), 'make_fixture.py'], cwd=work, env=env, check=True)
    result = subprocess.run([name, 'views.json', '--html', 'report.html'], cwd=work, env=env, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    assert data and (work / 'report.html').is_file()
    expected = {'array-alias-map': 'mutation_propagation', 'parquet-cast-preflight': 'files', 'alias-migration-matrix': 'cases', 'resample-boundary-diff': 'rows', 'figure-bounds-audit': 'labels'}[name]
    assert data[expected], (name, data)
    if name == 'array-alias-map':
        changes = {r['view']: r['coordinates'] for r in data['mutation_propagation']}
        assert changes == {'base': [[2, 2]], 'reverse': [[0, 1]], 'transpose': [[1, 0]]}
    elif name == 'parquet-cast-preflight':
        assert data['files'][0]['columns'][0]['failed_values'] == 1
        assert data['files'][0]['columns'][0]['witnesses'][0]['value'] == 'oops'
    elif name == 'alias-migration-matrix':
        assert data['counts']['VALUE_CHANGED'] == 1
    elif name == 'resample-boundary-diff':
        assert data['membership_changed_rows'] == 2
    else:
        assert data['clipped_labels'] >= 1
        labels = {r['text']: r['id'] for r in data['labels']}
        assert any({x['first'], x['second']} == {labels['Forecast'], labels['Actual']} for x in data['overlaps'])

    (work / 'bad.json').write_text('{}' if name != 'figure-bounds-audit' else '{"size_inches":[0,10000]}')
    bad = subprocess.run([name, 'bad.json'], cwd=work, env=env, capture_output=True, text=True)
    assert bad.returncode == 2 and 'error:' in bad.stderr
    if name == 'figure-bounds-audit':
        assert (work / 'diagnostic.png').stat().st_size > 1000
        malicious = {'labels': [{'text': '<script>alert(1)</script>', 'xy': [0.2, 0.5]}]}
        (work / 'escaped.json').write_text(json.dumps(malicious))
        subprocess.run([name, 'escaped.json', '--html', 'escaped.html'], cwd=work, env=env, capture_output=True, check=True)
        document = (work / 'escaped.html').read_text()
        assert '<script>' not in document and '&lt;script&gt;' in document
print('Installed command and example passed outside the checkout')
