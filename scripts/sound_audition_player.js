// Local audition only: cached decoding, one context, latest request wins.
// No filters, compression, equalisation, pitch changes or random variants.
class AuditionPlayer {
    constructor(files, changed) {
        this.files = files;
        this.changed = changed;
        this.buffers = new Map();
        this.context = null;
        this.active = null;
        this.request = 0;
        this.key = '';
        this.label = '';
        this.phase = 'idle';
        this.error = '';
        this.volume = 1;
        this.duration = 0;
        this.position = 0;
    }

    ensureContext() {
        if (this.context) return this.context;
        const Audio = window.AudioContext || window.webkitAudioContext;
        if (!Audio) throw new Error('此浏览器不支持 Web Audio，请用 Edge 或 Chrome 打开');
        this.context = new Audio({latencyHint: 'interactive'});
        this.master = this.context.createGain();
        this.master.gain.value = this.volume;
        this.master.connect(this.context.destination);
        // Keep the same output active between short clips; do not reopen it on
        // every click. This zero-valued source neither alters nor filters WAVs.
        this.silence = this.context.createConstantSource();
        this.silence.offset.value = 0;
        this.silence.connect(this.master);
        this.silence.start();
        return this.context;
    }

    decode(key) {
        if (!this.buffers.has(key)) {
            const pending = (async () => {
                if (!this.files[key]) throw new Error('找不到音效文件');
                const bytes = Uint8Array.from(atob(this.files[key]), c => c.charCodeAt(0));
                return this.context.decodeAudioData(bytes.buffer);
            })();
            this.buffers.set(key, pending);
            pending.catch(() => {
                if (this.buffers.get(key) === pending) this.buffers.delete(key);
            });
        }
        return this.buffers.get(key);
    }

    retire() {
        const old = this.active;
        this.active = null;
        if (!old) return;
        // Only an interrupted clip gets a 4ms release to avoid a hard cut click.
        // New clips start 50ms later, so releases never overlap the next sample.
        const now = this.context.currentTime;
        old.source.onended = () => { old.source.disconnect(); old.gain.disconnect(); };
        old.gain.gain.cancelScheduledValues(now);
        old.gain.gain.setValueAtTime(old.gain.gain.value, now);
        old.gain.gain.linearRampToValueAtTime(0, now + .004);
        old.source.stop(now + .004);
    }

    async play(key, label) {
        const request = ++this.request;
        this.retire();
        this.key = key;
        this.label = label;
        this.phase = 'loading';
        this.position = this.duration = 0;
        this.error = '';
        this.changed();
        try {
            const context = this.ensureContext();
            // resume is called synchronously inside the user gesture, while
            // decoding can finish later. Ignore every obsolete completion.
            const [, buffer] = await Promise.all([context.resume(), this.decode(key)]);
            if (request !== this.request) return false;
            const source = context.createBufferSource();
            const gain = context.createGain();
            source.buffer = buffer;
            source.loop = false;
            source.playbackRate.value = 1;
            source.connect(gain);
            gain.connect(this.master);
            const started = context.currentTime + .05;
            const voice = {source, gain, started};
            this.active = voice;
            this.duration = buffer.duration;
            source.onended = () => {
                source.disconnect();
                gain.disconnect();
                if (request !== this.request || this.active !== voice) return;
                this.active = null;
                this.position = buffer.duration;
                this.phase = 'ended';
                this.changed();
            };
            // Every row click and replay uses the same immutable buffer at zero.
            source.start(started, 0);
            this.phase = 'playing';
            this.changed();
            return true;
        } catch (error) {
            if (request !== this.request) return false;
            this.error = error.message;
            this.phase = 'error';
            this.changed();
            return false;
        }
    }

    stop() {
        ++this.request;
        this.retire();
        this.phase = 'stopped';
        this.position = 0;
        this.changed();
    }

    setVolume(percent) {
        this.volume = Math.max(0, Math.min(100, Number(percent))) / 100;
        if (this.master) this.master.gain.setValueAtTime(this.volume, this.context.currentTime);
    }

    elapsed() {
        return this.active ? Math.max(0, Math.min(this.duration, this.context.currentTime - this.active.started)) : this.position;
    }
}

let animation = 0;
function updateProgress() {
    document.querySelector('#progress').max = auditionPlayer.duration || 1;
    document.querySelector('#progress').value = auditionPlayer.elapsed();
    document.querySelector('#time').textContent = auditionPlayer.elapsed().toFixed(3) + ' / ' + auditionPlayer.duration.toFixed(3) + ' 秒';
}
function updatePlayback() {
    const player = auditionPlayer;
    const states = {loading: '准备中', playing: '播放中', ended: '已结束', stopped: '已停止', error: '无法播放'};
    document.querySelector('#playing').textContent = player.label + ' · ' + states[player.phase] + (player.error ? '：' + player.error : '');
    document.querySelector('#replay').disabled = !player.key;
    document.querySelector('#stop').disabled = !['loading', 'playing'].includes(player.phase);
    for (const button of document.querySelectorAll('[data-audio-key]')) button.setAttribute('aria-pressed', String(button.dataset.audioKey === player.key));
    cancelAnimationFrame(animation);
    function tick() {
        updateProgress();
        if (player.phase === 'playing') animation = requestAnimationFrame(tick);
    }
    tick();
}
const auditionPlayer = new AuditionPlayer(audioFiles, updatePlayback);
window.auditionPlayer = auditionPlayer;
function play(row, processed) {
    return auditionPlayer.play(processed ? 'processed/' + row.processed : 'wav/' + row.name, row.name + ' · ' + (processed ? '当前效果' : '原文件'));
}
document.querySelector('#replay').onclick = () => auditionPlayer.play(auditionPlayer.key, auditionPlayer.label);
document.querySelector('#stop').onclick = () => auditionPlayer.stop();
document.querySelector('#volume').oninput = event => {
    auditionPlayer.setVolume(event.target.value);
    document.querySelector('#volumeValue').textContent = event.target.value + '%';
};
window.addEventListener('pagehide', () => {
    auditionPlayer.stop();
    if (auditionPlayer.context) auditionPlayer.context.close();
});
