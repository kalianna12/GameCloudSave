from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import threading
import os
from pathlib import Path
import sys
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QTimer, qInstallMessageHandler, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from services import Store, ROOT, RESOURCES

class Bridge(QObject):
    changed = Signal()
    gamesChanged = Signal()
    settingsChanged = Signal()
    cloudChanged = Signal()
    directoriesChanged = Signal()
    matchesChanged = Signal()
    transfersChanged = Signal()
    matchReady = Signal(object)
    transferReady = Signal(str,str)
    finished = Signal(str, object, str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.pool = ThreadPoolExecutor(max_workers=1)
        self._busy = False
        self._status = '就绪'
        self._dirs = []
        self._history = []
        self._candidates = []
        self._running = {}
        self._games_cache = None
        self._cloud_path = ''
        self._preview = {}
        self._matches = list(store.match_report)
        self._transfers = {}
        self._transfer_ident = ''
        self._cancel_match = threading.Event()
        self._matching = False
        self._ai_connection = ''
        self._layout_values = {}
        self.layoutTimer = QTimer(self)
        self.layoutTimer.setSingleShot(True)
        self.layoutTimer.timeout.connect(self.flushLayout)
        self.matchReady.connect(self.receiveMatch)
        self.transferReady.connect(self.setTransfer)
        self.finished.connect(self.complete)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        self.timer.start(5000)

    @Property('QVariantList', notify=gamesChanged)
    def games(self):
        if self._games_cache is None:
            self._games_cache = [{**game, 'installed':self.store.local.get(game['id'], {}).get('installed', False),
                     'coverUrl': QUrl.fromLocalFile(str(self.store.root / 'thumbnails' / self.store.thumbnails[game['id']])).toString() if game['id'] in self.store.thumbnails else QUrl.fromLocalFile(str(self.store.root / 'covers' / Path(game['cover']).name)).toString() if game['cover'] else '',
                     'coverHighUrl': QUrl.fromLocalFile(str(self.store.root / 'thumbnails' / self.store.high_thumbnails[game['id']])).toString() if game['id'] in self.store.high_thumbnails else '',
                     'saveSet': bool(self.store.local.get(game['id'], {}).get('save_dir'))} for game in self.store.games]
        return self._games_cache

    @Property('QVariantMap', notify=settingsChanged)
    def settings(self):
        return {**self.store.settings, 'machine_id': self.store.identity, 'has_password': (self.store.profile / 'credential.dpapi').exists(),
                'has_ai_key': (self.store.profile / 'ai-key.dpapi').exists()}

    @Property(str, notify=changed)
    def status(self): return self._status
    @Property(bool, notify=changed)
    def busy(self): return self._busy
    @Property('QVariantList', notify=directoriesChanged)
    def directories(self): return self._dirs
    @Property(str, notify=cloudChanged)
    def cloudPath(self): return self._cloud_path
    @Property('QVariantMap', notify=cloudChanged)
    def cloudPreview(self): return self._preview
    @Property('QVariantList', notify=matchesChanged)
    def matchResults(self): return self._matches
    @Property(str, notify=matchesChanged)
    def aiConnection(self): return self._ai_connection
    @Property(bool, notify=changed)
    def matching(self): return self._matching
    @Property('QVariantMap', notify=transfersChanged)
    def transferStates(self): return self._transfers
    @Property('QVariantList', notify=changed)
    def snapshots(self): return self._history
    @Property('QVariantList', notify=changed)
    def candidates(self): return self._candidates

    def job(self, action, function):
        if self._busy:
            return
        self._busy = True
        self._status = {'import': '正在导入 Playnite 游戏与封面…', 'cloud': '先创建本地快照，再尝试上传…',
                        'list': '正在连接 DAV 并读取目录…', 'watch': '检查游戏运行状态…',
                        'cloud-organize':'正在整理旧备份并校验文件…','cloud-mkdir':'正在创建文件夹…',
                        'cloud-download':'正在下载文件…'}.get(action, '正在处理…')
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
        elif action in ('list','cloud-mkdir'):
            self._dirs = result['entries']
            self._cloud_path = result['path']
            self._preview = {}
            self._status = f'DAV 已连接 · {len(self._dirs)} 个目录与文件'
            self.directoriesChanged.emit()
            self.cloudChanged.emit()
        elif action == 'preview':
            self._preview = result
            if result.get('image'): self._preview['image']=QUrl.fromLocalFile(result['image']).toString()
            self.cloudChanged.emit()
            self._status = '预览已加载'
        elif action == 'cloud':
            self.setTransfer(result['id'],result['state'])
            self._status=result['message']
            if getattr(self,'_history_ident','')==result['id']:
                self._history=self.store.history(result['id'])
        elif action == 'ai-test':
            self._ai_connection=result
            self._status=result
            self.matchesChanged.emit()
        elif action == 'apply-match':
            self.receiveMatch(result)
            self._status=result['message']
        elif action == 'history':
            self._history = result
            self._status = f'本机共 {len(result)} 条快照'
        elif action == 'candidates':
            self._candidates = result
            self._status = f'发现 {len(result)} 个候选目录，请核对后选择'
        else:
            self._status = str(result or '已完成')
        if action in ('backup','restore') and not error and getattr(self,'_history_ident',''):
            self._history=self.store.history(self._history_ident)
        if action == 'cloud' and error:
            self.setTransfer(self._transfer_ident,'failed')
        if action == 'match': self._matching=False
        if action=='workflow': self._matching=False
        if action in ('import', 'remove', 'game-settings','apply-match','workflow') and not error:
            self._games_cache=None
            self.gamesChanged.emit()
        if action in ('settings','ai-test','cloud-config','workflow') and not error:
            self.settingsChanged.emit()
        if action=='ai-test' and error:
            self._ai_connection=error
            self.matchesChanged.emit()
        self.changed.emit()

    @Slot('QVariantMap')
    def saveLayout(self,values):
        self._layout_values.update(dict(values))
        self.layoutTimer.start(250)

    def flushLayout(self):
        if self._busy:
            self.layoutTimer.start(250)
            return
        if self._layout_values:
            self.store.save_settings(self._layout_values)
            self._layout_values={}
            self.settingsChanged.emit()

    @Slot(str,str)
    def setTransfer(self,ident,state):
        self._transfers={**self._transfers,ident:state}
        self.transfersChanged.emit()

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
        self.job('list', lambda: {'path':folder.strip('/'),'entries':self.store.rclone('list', folder, values)})

    @Slot('QVariantMap')
    def configureCloud(self,values): self.job('cloud-config',lambda:self.store.configure_cloud(values))

    @Slot(str,'QVariantMap',result=str)
    def cloudGamePath(self,ident,values):
        try: return self.store.cloud_directory(ident,values=values)
        except ValueError: return ''

    @Slot(str,str,'QVariantMap')
    def createCloudFolder(self,parent,name,values):
        self.job('cloud-mkdir',lambda:self.store.create_cloud_folder(parent,name,values))

    @Slot(str,'QVariantMap','QVariantMap')
    def downloadCloud(self,folder,entry,values):
        if self._busy:return
        destination=QFileDialog.getSaveFileName(None,'保存云端文件',str(Path.home()/'Downloads'/entry['Name']))[0]
        if destination:self.job('cloud-download',lambda:self.store.download_cloud(folder,entry,destination,values))

    @Slot(str,str,'QVariantMap')
    def organizeCloud(self,ident,folder,values):
        self.job('cloud-organize',lambda:self.store.organize_cloud(ident,folder,values))

    @Slot()
    def retryAll(self):
        if self._busy:return
        def retry():
            count=0; failed=0
            for game in self.store.games:
                ident=game['id']
                if not any(not r['uploaded'] and Path(r['archive_path']).exists() for r in self.store.history(ident)):continue
                self.transferReady.emit(ident,'uploading')
                try:
                    count+=self.store.retry(ident);self.transferReady.emit(ident,'success')
                except Exception:
                    failed+=1;self.transferReady.emit(ident,'failed')
            return f'批量补传完成：成功 {count} 条，失败 {failed} 个游戏；失败快照仍保留本地'
        self.job('retry-all',retry)

    @Slot('QVariantList',bool)
    @Slot('QVariantList',bool,'QVariantMap')
    def autoWorkflow(self,idents,upload,values=None):
        if self._busy:return
        self._cancel_match.clear(); self._matching=True
        def run():
            from save_workflow import run_workflow
            if values:self.store.save_settings(values)
            totals=run_workflow(self.store,idents,self.matchReady.emit,self._cancel_match,upload)
            return f"批量完成：云端成功 {totals['uploaded']}，本地保留 {totals['local_only']}，待核对 {totals['review']}，失败 {totals['failed']}"
        self.job('workflow',run)

    @Slot(str,'QVariantMap','QVariantMap')
    def previewCloud(self,folder,entry,values):
        if entry.get('IsDir'):
            self._preview={'name':entry['Name'],'size':-1,'modified':entry.get('ModTime',''),'text':'双击该文件夹进入，查看里面的目录与文件。','image':''}
            self.cloudChanged.emit()
            return
        self.job('preview',lambda:self.store.preview_cloud(folder,entry,values))

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
                self.store.prepare_thumbnails()
            self.store.save_game(ident, values)
            return '该游戏的本机设置已保存'
        self.job('game-settings', save)

    @Slot(str)
    def launch(self, ident):
        self.job('launch', lambda: (self.store.launch(ident), '启动请求已发送')[1])

    @Slot(str)
    def remove(self, ident):
        self.job('remove', lambda: (self.store.remove(ident), '已移除游戏条目；游戏文件和快照已保留')[1])

    @Slot(str)
    def cloudSave(self, ident):
        if self._busy: return
        self._transfer_ident=ident
        self.setTransfer(ident,'saving')
        def save():
            archive = self.store.backup(ident)
            self.transferReady.emit(ident,'uploading')
            try:
                self.store.upload(ident, archive)
                return {'id':ident,'state':'success','message':'本地快照已保存，云端上传成功'}
            except Exception as error:
                message=str(error) if isinstance(error,ValueError) else '云端网络操作失败'
                return {'id':ident,'state':'failed','message':'本地快照已保存；'+message+'，可补传'}
        self.job('cloud', save)

    @Slot(str)
    def localSave(self, ident): self.job('backup', lambda: '本地快照已保存：' + str(self.store.backup(ident)))
    @Slot(str)
    def history(self, ident):
        self._history_ident=ident
        self._history = []
        self.changed.emit()
        self.job('history', lambda: self.store.history(ident))
    @Slot(str)
    def retry(self, ident):
        if self._busy: return
        self._transfer_ident=ident
        self.setTransfer(ident,'uploading')
        def retry():
            try:
                count=self.store.retry(ident)
                return {'id':ident,'state':'success' if count else 'idle','message':f'已补传 {count} 条快照' if count else '没有需要补传的本机快照'}
            except Exception as error:
                return {'id':ident,'state':'failed','message':str(error) if isinstance(error,ValueError) else '补传失败，本地快照仍保留'}
        self.job('cloud',retry)
    @Slot(str, int)
    def restore(self, ident, snapshot):
        self.job('restore', lambda: (self.store.restore(ident, snapshot), '已恢复，恢复前存档已另行备份')[1])
    @Slot(str)
    def findSaves(self, ident):
        self._candidates = []
        self.job('candidates', lambda: self.store.candidates(ident))

    @Slot(object)
    def receiveMatch(self,result):
        if result.get('upload_requested'):
            mapped={'saving':'saving','uploading':'uploading','uploaded':'success','local_only':'failed','failed':'failed'}
            if result['status'] in mapped:self.setTransfer(result['id'],mapped[result['status']])
        existing={row['id']:row for row in self._matches}
        existing[result['id']]=result
        self._matches=list(existing.values())
        self.matchesChanged.emit()

    @Slot('QVariantList')
    def matchGames(self,idents):
        if self._busy: return
        idents=list(dict.fromkeys(idents))
        self._cancel_match.clear()
        self._matching=True
        def match():
            count=0
            results={row['id']:row for row in self.store.match_report}
            for ident in idents:
                if self._cancel_match.is_set(): break
                game=next((g for g in self.store.games if g['id']==ident),None)
                if game is None: continue
                self.matchReady.emit({'id':ident,'name':game['name'],'status':'running','message':'正在识别名称、查询存档规则并验证本地目录…','candidates':[],'checked':[],'aliases':[],'english_name':'','note':''})
                try: result=self.store.match_game(ident)
                except Exception as error:
                    result={'id':ident,'name':game['name'],'status':'failed','message':str(error) if isinstance(error,ValueError) else '本地扫描失败，请检查目录权限','candidates':[],'checked':[],'aliases':[],'english_name':'','note':''}
                self.matchReady.emit(result)
                results[ident]=result
                self.store.save_match_report(list(results.values()))
                count+=1
            return f'匹配已停止，已完成 {count} 个游戏' if self._cancel_match.is_set() else f'匹配完成：{count} 个游戏，结果已保存'
        self.job('match',match)

    @Slot()
    def cancelMatching(self): self._cancel_match.set()

    @Slot(str,str)
    def applyMatch(self,ident,path):
        allowed=[c['path'] for r in self._matches if r['id']==ident for c in r['candidates']]
        if path not in allowed:
            self._status='该路径不在本次已验证候选中'
            self.changed.emit()
            return
        if not Path(path).is_dir():
            self._status='候选目录已不存在，请重新匹配'
            self.changed.emit()
            return
        def apply():
            self.store.save_game(ident,{'save_dir':path})
            row=next(row for row in self._matches if row['id']==ident)
            result={**row,'status':'applied','message':'已确认并设置本机存档目录：'+path,'applied_path':path}
            reports={row['id']:row for row in self.store.match_report}
            reports[ident]=result
            self.store.save_match_report(list(reports.values()))
            return result
        self.job('apply-match',apply)

    @Slot('QVariantMap')
    def testAi(self,values):
        def test():
            from urllib.request import Request,urlopen
            from urllib.error import HTTPError
            from services import protect
            import json
            self.store.save_settings(values)
            key_path=self.store.profile/'ai-key.dpapi'
            if not key_path.exists(): raise ValueError('请填写 DeepSeek API Key')
            key=protect(key_path.read_bytes(),True).decode()
            try:
                with urlopen(Request('https://api.deepseek.com/models',headers={'Authorization':'Bearer '+key}),timeout=20) as response: models=json.load(response)['data']
            except HTTPError as error: raise ValueError(f'DeepSeek 连接失败：HTTP {error.code}') from None
            if self.store.settings['ai_model'] not in [m['id'] for m in models]: raise ValueError('当前模型不可用，请修改模型名称')
            return 'DeepSeek 连接成功 · '+self.store.settings['ai_model']
        self.job('ai-test',test)
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
                    try:
                        if self.store.settings.get('watch_upload',True): self.store.upload(ident, archive)
                    except Exception: pass
                    count += 1
            return f'监听中 · 本次完成 {count} 个自动快照' if count else '监听中 · 本地备份优先'
        self.job('watch', check)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot')
    parser.add_argument('--quit-after', type=int, default=0)
    parser.add_argument('--self-test')
    parser.add_argument('--self-test-online')
    parser.add_argument('--show',choices=('library','cloud','match'),default='library')
    args = parser.parse_args()
    if args.self_test_online:
        import json
        from services import protect
        from ai_match import identify_game
        from matching import scan
        store=Store()
        try:
            entries=store.rclone('list')
            key=protect((store.profile/'ai-key.dpapi').read_bytes(),True).decode()
            identity=identify_game('艾尔登法环','ELDEN RING',key,store.settings['ai_model'])
            game=next(g for g in store.games if g['name']=='ELDEN RING')
            candidates,_=scan(game['name'],store.local.get(game['id'],{}),identity)
            result={'passed':True,'dav_entries':len(entries),'english_name':identity['english_name'],'candidate_count':len(candidates)}
            assert 'elden' in identity['english_name'].casefold() and len(entries)>0
        except Exception as error:
            result={'passed':False,'error':str(error) if isinstance(error,ValueError) else type(error).__name__}
        Path(args.self_test_online).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return 0 if result['passed'] else 1
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
    app.setStyleSheet('QWidget { background: #242629; color: #f0f1f2; } QPushButton { padding: 8px; }')
    bridge = Bridge(Store())
    bridge.store.prepare_thumbnails()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', bridge)
    engine.load(QUrl.fromLocalFile(str(RESOURCES / 'ui/Main.qml')))
    if not engine.rootObjects():
        bridge.pool.shutdown(wait=False)
        return 1
    root_window = engine.rootObjects()[0]
    window = root_window
    if args.show=='cloud':
        QMetaObject.invokeMethod(window,'openCloud')
        window=window.findChild(QObject,'cloudWindow')
    elif args.show=='match':
        ident=bridge.matchResults[0]['id'] if bridge.matchResults else ''
        QMetaObject.invokeMethod(window,'openMatch',Q_ARG('QVariant',ident))
        window=window.findChild(QObject,'matchWindow')
    if args.screenshot:
        def capture():
            path = Path(args.screenshot)
            path.parent.mkdir(parents=True, exist_ok=True)
            window.grabWindow().save(str(path))
        QTimer.singleShot(3000, capture)
    if args.quit_after: QTimer.singleShot(args.quit_after, app.quit)
    result = app.exec()
    bridge.timer.stop()
    bridge.flushLayout()
    bridge.pool.shutdown(wait=True)
    import shiboken6
    shiboken6.delete(engine)
    return result

if __name__ == '__main__': sys.exit(main())
