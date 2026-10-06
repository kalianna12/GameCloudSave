from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QTimer, qInstallMessageHandler
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from services import Store, ROOT, RESOURCES

class Bridge(QObject):
    changed = Signal()
    gamesChanged = Signal()
    settingsChanged = Signal()
    finished = Signal(str, object, str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=1)
        self._busy = False
        self._status = '准备就绪 · 本地备份优先'
        self._dirs = []
        self._history = []
        self._candidates = []
        self._running = {}
        self.finished.connect(self.complete)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(5000)

    @Property('QVariantList', notify=gamesChanged)
    def games(self):
        return [{**game, 'installed':self.store.local.get(game['id'], {}).get('installed', False),
                 'coverUrl': QUrl.fromLocalFile(str(self.store.root / 'covers' / Path(game['cover']).name)).toString() if game['cover'] else '',
                 'saveSet': bool(self.store.local.get(game['id'], {}).get('save_dir'))} for game in self.store.games]

    @Property('QVariantMap', notify=settingsChanged)
    def settings(self):
        return {**self.store.settings, 'machine_id': self.store.identity, 'has_password': (self.store.profile / 'credential.dpapi').exists(),
                'has_ai_key': (self.store.profile / 'ai-key.dpapi').exists()}

    @Property(str, notify=changed)
    def status(self): return self._status
    @Property(bool, notify=changed)
    def busy(self): return self._busy
    @Property('QVariantList', notify=changed)
    def directories(self): return self._dirs
    @Property('QVariantList', notify=changed)
    def snapshots(self): return self._history
    @Property('QVariantList', notify=changed)
    def candidates(self): return self._candidates

    def job(self, action, function):
        if self._busy:
            return
        self._busy = True
        self._status = {'import': '正在导入 Playnite 游戏与封面…', 'cloud': '先创建本地快照，再尝试上传…',
                        'list': '正在连接 DAV 并读取目录…', 'watch': '检查游戏运行状态…'}.get(action, '正在处理…')
        self.changed.emit()
        def work():
            try:
                self.finished.emit(action, function(), '')
            except Exception as error:
                message = str(error) if isinstance(error, ValueError) else f'操作失败（{type(error).__name__}），请检查本机设置'
                self.finished.emit(action, None, message)
        self.pool.submit(work)

    @Slot(str, object, str)
    def complete(self, action, result, error):
        self._busy = False
        if error:
            self._status = error
        elif action == 'import':
            self._status = f'已导入 {result} 款游戏 · 封面已缓存 · 重复导入不会产生重复项'
        elif action == 'list':
            self._dirs = result
            self._status = f'DAV 已连接 · 找到 {len(result)} 个子目录'
        elif action == 'history':
            self._history = result
            self._status = f'本机共 {len(result)} 条快照'
        elif action == 'candidates':
            self._candidates = result
            self._status = f'发现 {len(result)} 个候选目录，请核对后选择'
        else:
            self._status = str(result or '已完成')
        if action in ('import', 'remove', 'settings') and not error:
            self.gamesChanged.emit()
        if action == 'settings' and not error:
            self.settingsChanged.emit()
        self.changed.emit()

    @Slot()
    def importGames(self): self.job('import', self.store.import_playnite)

    @Slot('QVariantMap')
    def saveSettings(self, values):
        def save():
            self.store.save_settings(values)
            return '本机设置已保存 · 其他电脑使用独立设置'
        self.job('settings', save)

    @Slot(str, 'QVariantMap')
    def browseCloud(self, folder, values):
        self.job('list', lambda: self.store.rclone('list', folder, values))

    @Slot(str, result='QVariantMap')
    def gameSettings(self, ident): return self.store.local.get(ident, {})

    @Slot(str, 'QVariantMap')
    def saveGame(self, ident, values):
        def save():
            cover = values.pop('cover', '')
            if cover:
                import shutil
                source = Path(cover)
                if not source.is_file(): raise ValueError('封面文件不存在')
                target = self.store.root / 'covers' / (ident + source.suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                if source.resolve() != target.resolve(): shutil.copy2(source, target)
                for game in self.store.games:
                    if game['id'] == ident: game['cover'] = str(target)
                from services import write_json
                write_json(self.store.root / 'library.json', self.store.games)
            self.store.save_game(ident, values)
            return '该游戏的本机设置已保存'
        self.job('settings', save)

    @Slot(str)
    def launch(self, ident):
        self.job('launch', lambda: (self.store.launch(ident), '启动请求已发送')[1])

    @Slot(str)
    def remove(self, ident):
        self.job('remove', lambda: (self.store.remove(ident), '已移除游戏条目；游戏文件和快照已保留')[1])

    @Slot(str)
    def cloudSave(self, ident):
        def save():
            archive = self.store.backup(ident)
            try:
                self.store.upload(ident, archive)
                return '本地快照已保存，云端上传成功'
            except Exception:
                return '本地快照已保存；云端上传未成功，可在快照历史中重试'
        self.job('cloud', save)

    @Slot(str)
    def localSave(self, ident): self.job('backup', lambda: '本地快照已保存：' + str(self.store.backup(ident)))
    @Slot(str)
    def history(self, ident):
        self._history = []
        self.changed.emit()
        self.job('history', lambda: self.store.history(ident))
    @Slot(str)
    def retry(self, ident): self.job('retry', lambda: f'已补传 {self.store.retry(ident)} 条快照')
    @Slot(str, int)
    def restore(self, ident, snapshot):
        self.job('restore', lambda: (self.store.restore(ident, snapshot), '已恢复，恢复前存档已另行备份')[1])
    @Slot(str)
    def findSaves(self, ident):
        self._candidates = []
        self.job('candidates', lambda: self.store.candidates(ident))
    @Slot(str, result=str)
    def pickFolder(self, current): return QFileDialog.getExistingDirectory(None, '选择本机目录', current)
    @Slot(str, result=str)
    def pickFile(self, kind):
        return QFileDialog.getOpenFileName(None, '选择文件', '', '图片 (*.jpg *.png *.webp *.jpeg)' if kind == 'cover' else '程序 (*.exe)')[0]

    def poll(self):
        if self._busy or not self.store.settings.get('watch'): return
        def check():
            import psutil
            names = {p.info['name'].casefold() for p in psutil.process_iter(['name']) if p.info.get('name')}
            count = 0
            for ident, local in list(self.store.local.items()):
                if not local.get('exe') or not local.get('save_dir') or not any(g['id'] == ident for g in self.store.games): continue
                running = Path(local['exe']).name.casefold() in names
                previous = self._running.get(ident, False)
                self._running[ident] = running
                if running != previous:
                    archive = self.store.backup(ident, 'game_start' if running else 'game_stop')
                    try: self.store.upload(ident, archive)
                    except Exception: pass
                    count += 1
            return f'监听中 · 本次完成 {count} 个自动快照' if count else '监听中 · 本地备份优先'
        self.job('watch', check)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot')
    parser.add_argument('--quit-after', type=int, default=0)
    parser.add_argument('--self-test')
    args = parser.parse_args()
    if args.self_test:
        import gc, json, tempfile, uuid
        from services import run_process
        (ROOT / 'test-data').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / 'test-data') as temporary:
            fixture = Store(Path(temporary), 'packaged-test')
            ident = str(uuid.uuid4())
            fixture.games = [{'id':ident,'name':'中文打包测试','installed':True,'cover':''}]
            save = Path(temporary) / 'save'
            save.mkdir()
            (save / 'data.json').write_text('{"进度":42}', encoding='utf-8')
            fixture.save_game(ident, {'save_dir':str(save)})
            archive = fixture.backup(ident)
            snapshot = fixture.history(ident)[0]['id']
            (save / 'data.json').write_text('{}', encoding='utf-8')
            fixture.restore(ident, snapshot)
            assert json.loads((save / 'data.json').read_text(encoding='utf-8')) == {'进度':42}
            fixture.save_settings({'password':'packaged-dummy'})
            assert fixture.password() == 'packaged-dummy'
            assert run_process([fixture.settings['rclone'],'version'], timeout=10).returncode == 0
            gc.collect()
        Path(args.self_test).write_text('PASS: packaged core backup, restore, SQLite, Chinese JSON, DPAPI, bundled rclone',encoding='utf-8')
        return 0
    qInstallMessageHandler(lambda kind, context, message: print(message, file=sys.stderr, flush=True))
    app = QApplication(sys.argv)
    app.setApplicationName('GameCloudSave')
    app.setOrganizationName('GameCloudSave')
    app.setWindowIcon(QIcon(str(RESOURCES / 'ui/icons/app.svg')))
    app.setStyle('Fusion')
    QQuickStyle.setStyle('Material')
    app.setStyleSheet('QWidget { background: #18201d; color: #f2f5f3; } QPushButton { padding: 8px; }')
    bridge = Bridge(Store())
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', bridge)
    engine.load(QUrl.fromLocalFile(str(RESOURCES / 'ui/Main.qml')))
    if not engine.rootObjects():
        bridge.pool.shutdown(wait=False)
        return 1
    window = engine.rootObjects()[0]
    if args.screenshot:
        def capture():
            path = Path(args.screenshot)
            path.parent.mkdir(parents=True, exist_ok=True)
            window.grabWindow().save(str(path))
        QTimer.singleShot(3000, capture)
    if args.quit_after: QTimer.singleShot(args.quit_after, app.quit)
    result = app.exec()
    bridge.timer.stop()
    bridge.pool.shutdown(wait=True)
    import shiboken6
    shiboken6.delete(engine)
    return result

if __name__ == '__main__': sys.exit(main())
