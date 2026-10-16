"""Smoke-test the existing portable EXE with isolated, generated library artwork."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from services import Store, write_json
from PySide6.QtGui import QImage, QColor

parser = argparse.ArgumentParser()
parser.add_argument('--version', default='2.5.0')
version = parser.parse_args().version
test = ROOT / 'test-data' / ('portable-v' + version)
test.mkdir(parents=True, exist_ok=True)
program = ROOT / 'dist/GameCloudSave'
exe = program / 'GameCloudSave.exe'
data = test / 'data'
store = Store(data)
store.save_settings({'setup_completed':True, 'guide_dismissed':True, 'watch':False,
                     'close_to_tray':False, 'playnite':'', 'library':'', 'fullscreen':False})
art = data / 'covers'
art.mkdir(exist_ok=True)
games = []
for index, color in enumerate(('#346c89', '#796088', '#9c7354', '#567856')):
    image = QImage(360, 540, QImage.Format_RGB32)
    image.fill(QColor(color))
    cover = 'fixture-' + str(index) + '.png'
    assert image.save(str(art / cover))
    games.append({'id':str(index), 'name':'Release fixture ' + str(index+1), 'cover':cover,
                  'category':'Adventure', 'tags':['Adventure'], 'series':'Release fixtures',
                  'release_date':'2020-01-0' + str(index+1)})
write_json(data / 'library.json', games)
environment = {**os.environ, 'GAMECLOUD_DATA':str(data)}
report = {'version':version, 'layouts':{}}


def run(arguments):
    started = time.monotonic()
    result = subprocess.run([str(exe), *map(str, arguments)], env=environment,
                            capture_output=True, timeout=40, creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, (arguments, result.returncode, result.stderr[-2000:])
    return round(time.monotonic() - started, 3)


report['selftest_seconds'] = run(['--self-test', test / 'selftest.txt'])
assert (test / 'selftest.txt').read_text(encoding='utf-8').startswith('PASS')
for design in ('classic', 'shelf', 'cinema', 'atlas'):
    store.save_settings({'library_design':design})
    screenshot = test / (design + '.png')
    startup = test / (design + '-startup.txt')
    elapsed = run(['--quit-after', 4300, '--screenshot', screenshot, '--startup-report', startup])
    assert screenshot.is_file() and not QImage(str(screenshot)).isNull(), design
    report['layouts'][design] = {'startup_seconds':float(startup.read_text()), 'total_seconds':elapsed}
    log = data / 'logs/app.log'
    content = log.read_text(encoding='utf-8') if log.exists() else ''
    errors = [line for line in content.splitlines() if any(word in line for word in (
        'ReferenceError', 'TypeError', 'is not installed', 'failed to load component',
        'Unhandled ', 'Cannot assign', 'Unable to assign'))]
    assert not errors, (design, errors)
for name in ('ExperienceData.js', 'WoodMaterials.js', 'InlineImageBrowser.qml', 'CinemaVideo.qml'):
    assert (program / '_internal/ui' / name).is_file(), name
for name in ('QtWebEngineProcess.exe', 'Qt6WebEngineQuick.dll', 'Qt6Multimedia.dll'):
    assert any((program / '_internal').rglob(name)), name
report['passed'] = True
(test / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('PASS: portable self-test, four layouts, screenshots, Qt web/video resources, isolated data')
print(json.dumps(report))
