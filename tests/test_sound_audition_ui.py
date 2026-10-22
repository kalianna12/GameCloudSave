"""Real Chromium Web Audio: repeat consistency and obsolete-request isolation.

Generate build/sound-audition/index.html first. Uses an in-memory browser profile,
muted hardware output and local files only; no game/profile data is opened.
"""
from pathlib import Path
import base64
import json
import os
import re
import time

os.environ['QTWEBENGINE_CHROMIUM_FLAGS'] = '--autoplay-policy=no-user-gesture-required --disable-gpu'
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
import shiboken6

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / 'build/sound-audition/index.html'
html = PATH.read_text(encoding='utf-8')
embedded = json.loads(re.search(r'audioFiles=(\{.*?\}),events=', html).group(1))
assert len(embedded) == 217
for key, encoded in embedded.items():
    assert base64.b64decode(encoded) == (PATH.parent / key).read_bytes(), key

app = QApplication([])
profile = QWebEngineProfile()
page = QWebEnginePage(profile)
page.setAudioMuted(True)
page.setLifecycleState(QWebEnginePage.LifecycleState.Active)


def wait(predicate, seconds=20):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return
        time.sleep(.002)
    raise AssertionError('Browser deadline')


def evaluate(code):
    result = []
    page.runJavaScript(code, lambda value: result.append(value))
    wait(lambda: len(result) > 0)
    return result[0]


loaded = []
page.loadFinished.connect(loaded.append)
try:
    page.load(QUrl.fromLocalFile(str(PATH)))
    wait(lambda: bool(loaded))
    assert loaded == [True]
    evaluate('''
window.testResult = null;
(async () => {
    const assert = (ok, text) => { if (!ok) throw new Error(text); };
    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
    const player = window.auditionPlayer;
    const original = rows.find(row => row.name === 'SeDialogOpen.wav');
    const another = rows.find(row => row.name === 'SeBtnDecide.wav');
    const context = player.ensureContext();
    const started = [];
    const create = context.createBufferSource.bind(context);
    context.createBufferSource = () => {
        const source = create();
        const start = source.start.bind(source);
        source.start = (...args) => { started.push({source, buffer: source.buffer, args}); start(...args); };
        return source;
    };
    context.createBiquadFilter = () => { throw new Error('No filters permitted'); };
    const decode = context.decodeAudioData.bind(context);
    let decoded = 0;
    context.decodeAudioData = (...args) => { ++decoded; return decode(...args); };

    // Completed replays use exactly one decoded buffer, unit speed and offset 0.
    for (let index = 0; index < 4; index++) {
        assert(await play(original, false), 'Replay did not start');
        await delay(160);
        assert(player.phase === 'ended', 'Clip did not end naturally');
    }
    assert(decoded === 1, 'Same WAV decoded again on replay');
    const buffer = started[0].buffer;
    assert(started.every(voice => voice.buffer === buffer && voice.args[1] === 0 && voice.source.playbackRate.value === 1), 'Replay buffer/offset/rate changed');

    // Render the cached buffer twice in the browser audio engine; PCM identical.
    async function render() {
        const offline = new OfflineAudioContext(buffer.numberOfChannels, buffer.length, buffer.sampleRate);
        const source = offline.createBufferSource();source.buffer = buffer;source.connect(offline.destination);source.start(0);
        return offline.startRendering();
    }
    const [first, second] = await Promise.all([render(), render()]);
    for (let channel = 0; channel < first.numberOfChannels; channel++) {
        const a = first.getChannelData(channel), b = second.getChannelData(channel);
        assert(a.length === b.length && a.every((value, i) => value === b[i]), 'Repeated output PCM differs');
    }

    // Rapid original/processed switching admits only the final decode completion.
    const before = started.length;
    const results = await Promise.all(Array.from({length: 30}, (_, index) => play(original, index % 2 === 0)));
    assert(results.filter(Boolean).length === 1 && started.length === before + 1, 'Obsolete rapid clicks played');
    assert(player.key === 'wav/' + original.name, 'Wrong final file');
    const rawBuffer = await player.decode('wav/' + original.name);
    const processedBuffer = await player.decode('processed/' + original.processed);
    assert(rawBuffer !== processedBuffer, 'Original and processed cache entries collided');

    // An old failed request must not overwrite a newer successful playback.
    const normalDecode = player.decode.bind(player);
    player.decode = key => key === 'late-failure' ? delay(90).then(() => {throw new Error('obsolete failure');}) : normalDecode(key);
    const old = player.play('late-failure', 'obsolete');
    assert(await play(another, false), 'Latest playback failed');
    await old;
    assert(player.key === 'wav/' + another.name && player.phase !== 'error' && !player.error, 'Old error overwrote current state');
    assert(!document.querySelector('#playing').textContent.includes('obsolete'), 'Stale error reached UI');

    // Stop during a decode invalidates it; it must never start later.
    player.decode = async key => {await delay(80); return normalDecode(key);};
    const count = started.length;
    const pending = play(original, false);document.querySelector('#stop').click();
    assert(!await pending && player.phase === 'stopped' && started.length === count, 'Stopped decode started later');
    player.decode = normalDecode;
    document.querySelector('#replay').click();await delay(160);
    assert(started.length === count + 1 && started.at(-1).args[1] === 0, 'Replay control did not restart at zero');
    const volume = document.querySelector('#volume');volume.value = '35';volume.dispatchEvent(new Event('input'));
    await delay(30); // AudioParam automation applies on the next render quantum.
    assert(Math.abs(player.master.gain.value - .35) < .00001, 'Volume control failed');
    assert(player.context === context, 'Output context was recreated');

    // All bundled WAVs, including sub-3ms clips and stereo samples, decode once.
    const all = await Promise.all(Object.keys(audioFiles).map(key => player.decode(key)));
    assert(all.length === 217 && all.every(audio => audio.length > 0), 'A bundled clip cannot decode');
    window.testResult = {ok: true, buffers: player.buffers.size, starts: started.length, decoded};
})().catch(error => window.testResult = {ok: false, error: error.stack});
''')
    end = time.monotonic() + 25
    result = None
    while time.monotonic() < end:
        result = evaluate('JSON.stringify(window.testResult)')
        if result and result != 'null':
            break
        time.sleep(.03)
    report = json.loads(result or 'null')
    assert report and report['ok'], report
    print('PASS: 217 embedded WAVs match files and decode; repeated render PCM identical; offset-zero replays, 30 rapid requests, stale errors, pending-stop, volume and one context; hardware muted', report)
finally:
    shiboken6.delete(page)
    shiboken6.delete(profile)
