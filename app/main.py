from __future__ import annotations
import time
_PROCESS_START=time.perf_counter()
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import threading
import os
from pathlib import Path
import sys
from PySide6.QtCore import QObject, Property, Signal, Slot, QUrl, QTimer, qInstallMessageHandler, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QSystemTrayIcon, QMenu
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
    watchReady = Signal(object)
    notificationReady = Signal(str,str,bool)
    finished = Signal(str, object, str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        store.reweight_matches()
        self.pool = ThreadPoolExecutor(max_workers=1)
        self._busy = False
        self._status = '就绪'
        self._dirs = []
        self._history = []
        self._cloud_history = []
        self._imports = []
        self._import_mode=''
        self._cover_results=[]
        self._import_reference=[]
        self._picked_save_folders=set()
        self._organizer=[]
        self._icon_cache={}
        self._candidates = []
        self._running = {}
        self._watch_pending=False
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
        self.watchReady.connect(self.receiveWatch)
        self.finished.connect(self.complete)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.poll)
        if store.settings.get('watch'):self.timer.start(max(5,int(store.settings.get('watch_interval',10)))*1000)

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
    def cloudSnapshots(self):return self._cloud_history
    @Property('QVariantList', notify=changed)
    def importCandidates(self):return self._imports
    @Property('QVariantList',notify=changed)
    def coverResults(self):return self._cover_results
    @Property('QVariantList',constant=True)
    def coverProviders(self):
        from cover_sources import PROVIDERS
        return PROVIDERS
    @Property('QVariantMap',notify=settingsChanged)
    def theme(self):
        from themes import resolve
        return resolve(self.store.settings)
    @Property('QVariantList',notify=gamesChanged)
    def groups(self):return self.store.groups
    @Property('QVariantList',notify=changed)
    def organizerResults(self):return self._organizer
    @Property(str,constant=True)
    def openSourceNotice(self):
        file=RESOURCES/'ui/OPEN_SOURCE_NOTICE.txt'
        return file.read_text(encoding='utf-8') if file.exists() else 'GameCloudSave：MIT 开源许可。'
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
        elif action == 'apply-matches':
            for row in result['rows']: self.receiveMatch(row)
            self._status=result['message']
        elif action == 'history':
            self._history = result
            self._status = f'本机共 {len(result)} 条快照'
        elif action in ('scan-import','platform-preview','playnite-preview','ai-launchers','auto-covers'):
            self._imports=result['rows']
            duplicates=sum(bool(row.get('duplicate_id')) for row in self._imports)
            self._status=f"预览 {len(self._imports)} 项，已排除 {duplicates} 个重复项"+('；扫描达到数量限制，请缩小范围' if result.get('truncated') else '')+result.get('warning','')
        elif action=='cover-search':
            self._cover_results=result
            self._status=f'找到 {len(result)} 个封面结果，请选择'
        elif action=='cover-apply':
            if result['scope']=='import':
                self._imports=result['rows']
            else:self._games_cache=None;self.gamesChanged.emit()
            self._status='封面已设置'
        elif action=='organizer-preview':
            self._organizer=result;self._status='分类建议已生成，请核对后应用'
        elif action=='cloud-history':
            self._cloud_history=result
            self._status=f'云端共 {len(result)} 份备份，选择后下载并恢复'
        elif action == 'candidates':
            self._candidates = result
            self._status = f'发现 {len(result)} 个候选目录，请核对后选择'
        else:
            self._status = str(result or '已完成')
        if action in ('backup','restore','snapshot-note','cloud-restore') and not error and getattr(self,'_history_ident',''):
            self._history=self.store.history(self._history_ident)
        if action == 'cloud' and error:
            self.setTransfer(self._transfer_ident,'failed')
        if action == 'match': self._matching=False
        if action=='workflow': self._matching=False
        if action in ('import','import-selected','library-edit','group-edit','launch','watch', 'remove', 'game-settings','apply-match','apply-matches','workflow') and not error:
            self._games_cache=None
            self.gamesChanged.emit()
            if action=='import-selected':
                from library_sources import annotate_duplicates
                self._imports=annotate_duplicates(self.store,self._imports,self._import_reference)
        if action=='watch' and error and self.store.settings.get('tray_notifications',True):self.notificationReady.emit('自动备份失败',error,True)
        if action in ('settings','ai-test','cloud-config','workflow','match') and not error:
            if self._matches!=self.store.match_report:
                self._matches=list(self.store.match_report);self.matchesChanged.emit()
            self.settingsChanged.emit()
            if self.store.settings.get('watch'):self.timer.start(max(5,min(60,int(self.store.settings.get('watch_interval',10))))*1000)
            else:self.timer.stop()
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

    @Slot('QVariantList')
    def importPlaynitePlatforms(self,platforms):self.job('import',lambda:self.store.import_playnite(platforms))

    @Slot('QVariantList')
    def previewPlatforms(self,platforms):
        from library_sources import installed
        self._import_mode='platform'
        self.job('platform-preview',lambda:self.prepareImportPreview(installed(platforms)))

    def prepareImportPreview(self,rows,truncated=False):
        from library_sources import annotate_duplicates
        from services import read_json
        warning=''
        if self._import_mode=='playnite':self._import_reference=[]
        elif (Path(self.store.settings['library'])/'games.db').is_file():
            try:self._import_reference=self.store.playnite_candidates()
            except ValueError:
                self._import_reference=read_json(self.store.profile/'playnite-reference.json',[])
                warning='；Playnite 正在占用或不可读取，仅核对缓存和现有库，新条目可能未检出'
        else:self._import_reference=[]
        return {'rows':annotate_duplicates(self.store,rows,self._import_reference),'truncated':truncated,'warning':warning}

    @Slot(bool)
    def previewPlaynite(self,installed_only=True):
        self._import_mode='playnite'
        def preview():
            rows=self.store.playnite_candidates()
            return self.prepareImportPreview([row for row in rows if not installed_only or row['installed']])
        self.job('playnite-preview',preview)

    @Slot()
    def clearImportPreview(self):
        if self._busy:return
        self._imports=[];self._cover_results=[];self.changed.emit()

    @Slot()
    def clearCoverSearch(self):
        if not self._busy:self._cover_results=[];self.changed.emit()

    @Slot(str,int)
    def scanImports(self,folder,depth):
        from library_sources import scan
        self._import_mode='scan'
        def preview():
            result=scan(folder,max(1,min(10,depth)))
            return self.prepareImportPreview(result['rows'],result['truncated'])
        self.job('scan-import',preview)

    @Slot()
    def reviewImportLaunchers(self):
        from library_sources import review_launchers
        self.job('ai-launchers',lambda:self.prepareImportPreview(review_launchers(self.store,self._imports,self._import_reference)))

    @Slot('QVariantList')
    def importSelected(self,selected):
        def run():
            from library_sources import import_rows
            allowed={row['id']:row for row in self._imports}
            if any(ident not in allowed for ident in selected):raise ValueError('候选已更新，请重新选择')
            rows=[allowed[ident] for ident in dict.fromkeys(selected)]
            from library_sources import annotate_duplicates
            rows=annotate_duplicates(self.store,rows,self._import_reference)
            skipped=sum(bool(row.get('duplicate_id')) for row in rows)
            rows=[row for row in rows if not row.get('duplicate_id')]
            directories=[row['install_dir'].casefold() for row in rows]
            if len(set(directories))!=len(directories):raise ValueError('同一游戏请选择一个启动文件')
            count=import_rows(self.store,rows,skip_duplicates=True)
            return f'已导入 {count} 款游戏；排除 {skipped+len(rows)-count} 个重复或失效条目'
        self.job('import-selected',run)

    @Slot(str,str,bool)
    def searchCovers(self,query,provider,use_ai=False):
        from cover_sources import search
        self._cover_results=[]
        self.job('cover-search',lambda:search(self.store,query,provider,use_ai))

    @Slot(str,str,result=str)
    def coverBrowserUrl(self,query,provider):
        from cover_sources import PROVIDERS
        from urllib.parse import quote
        source=next((row for row in PROVIDERS if row['id']==provider),{})
        return source.get('url','').replace('{query}',quote(query[:200]+' game cover'))

    @Slot(str,str,str)
    def useCoverUrl(self,scope,ident,url):
        import hashlib
        record={'id':'manual:'+hashlib.sha256(url.encode()).hexdigest(),'image':url,'fallback':'','user_authorized':True}
        self._cover_results=[record];self.applyCover(scope,ident,record['id'])

    @Slot(str,str)
    def useLocalCover(self,scope,ident):
        if self._busy:return
        path=self.pickFile('cover')
        if not path:return
        if scope=='game':self.saveGame(ident,{'cover':path})
        else:
            rows=[dict(row) for row in self._imports]
            for row in rows:
                if row['id']==ident:row.update(cover=path,cover_state='本地图片');row.pop('metadata_steam_appid',None)
            self._imports=rows;self.changed.emit()

    @Slot(str,str,result=str)
    def iconSource(self,name,color):
        import re,base64
        if not re.fullmatch(r'[a-z0-9_-]+',name) or not re.fullmatch(r'#[0-9a-fA-F]{6}',color):return ''
        cache_key=name+color
        if cache_key not in self._icon_cache:
            file=RESOURCES/'ui/icons'/(name+'.svg')
            if not file.is_file():return ''
            content=file.read_text(encoding='utf-8')
            content=re.sub(r'((?:fill|stroke)=")#[0-9a-fA-F]{6}("\s*)',lambda match:match.group(1)+color+match.group(2),content)
            self._icon_cache[cache_key]='data:image/svg+xml;base64,'+base64.b64encode(content.encode()).decode()
        return self._icon_cache[cache_key]

    @Slot()
    def importTheme(self):
        file=QFileDialog.getOpenFileName(None,'导入主题 JSON','','主题 (*.json)')[0]
        if not file:return
        def read():
            import json
            from themes import validate
            path=Path(file)
            if path.stat().st_size>65536:raise ValueError('主题文件过大')
            palette=validate(json.loads(path.read_text(encoding='utf-8-sig')))
            self.store.save_settings({'custom_theme':palette,'theme':'custom','accent_color':''});return '主题已导入'
        self.job('settings',read)

    @Slot('QVariantList')
    def updateLibrary(self,updates):self.job('library-edit',lambda:(self.store.update_library(updates),'游戏库分类已更新')[1])
    @Slot(str)
    def toggleFavorite(self,ident):
        game=next(game for game in self.store.games if game['id']==ident)
        self.updateLibrary([{'id':ident,'favorite':not game.get('favorite',False)}])
    @Slot(str,str)
    def editGroup(self,old,new):self.job('group-edit',lambda:(self.store.edit_group(old,new),'分类已更新')[1])
    @Slot(bool)
    def previewOrganizer(self,use_ai):
        from library_organizer import suggestions
        self.job('organizer-preview',lambda:suggestions(self.store,use_ai))

    @Slot(str,str,str)
    def applyCover(self,scope,ident,result_id):
        def apply():
            from cover_sources import download
            record=next((row for row in self._cover_results if row['id']==result_id),None)
            if record is None:raise ValueError('封面结果已改变，请重新搜索')
            path=download(self.store,record)
            if scope=='import':
                rows=[dict(row) for row in self._imports]
                row=next(row for row in rows if row['id']==ident);row.update(cover=path,cover_state='已选择',cover_confirmed=True)
                if record.get('appid'):row['metadata_steam_appid']=record['appid']
                else:row.pop('metadata_steam_appid',None)
                return {'scope':scope,**self.prepareImportPreview(rows)}
            game=next(game for game in self.store.games if game['id']==ident);game['cover']=path
            from services import write_json
            write_json(self.store.root/'library.json',self.store.games);self.store.prepare_thumbnails()
            return {'scope':'game'}
        self.job('cover-apply',apply)

    @Slot('QVariantList',str,bool)
    def autoImportCovers(self,selected,provider,use_ai):
        def apply():
            from cover_sources import search,download
            rows=[dict(row) for row in self._imports];allowed=set(selected)
            for row in rows:
                if row['id'] not in allowed or row.get('duplicate_id') or row.get('playnite'):continue
                try:
                    results=search(self.store,row['name'],provider,use_ai)
                    if results and results[0]['score']>=.93 and (len(results)==1 or results[0]['score']-results[1]['score']>=.12):
                        record=results[0];row.update(cover=download(self.store,record),cover_state='已自动匹配',cover_confirmed=False)
                        if record.get('appid'):row['metadata_steam_appid']=record['appid']
                        else:row.pop('metadata_steam_appid',None)
                    else:row['cover_state']='需手动搜索'
                except ValueError as error:row['cover_state']=str(error)
            return self.prepareImportPreview(rows)
        self.job('auto-covers',apply)

    @Slot(result=bool)
    def closeToTray(self):return self.store.settings.get('close_to_tray',True) and QSystemTrayIcon.isSystemTrayAvailable()

    @Slot('QVariantMap')
    def saveSettings(self, values):
        def save():
            self.store.save_settings(values)
            return '本机设置已保存 · 其他电脑使用独立设置'
        self.job('settings', save)

    @Slot('QVariantMap')
    def saveSetup(self,values):
        def save():
            snapshots=values.get('snapshots',self.store.settings['snapshots'])
            if not snapshots or not Path(snapshots).is_absolute():raise ValueError('请填写完整的本地备份目录')
            Path(snapshots).mkdir(parents=True,exist_ok=True)
            self.store.save_settings(values)
            return '基础设置已完成，可以导入游戏'
        self.job('settings',save)

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

    @Slot('QVariantList',bool)
    def backupConfigured(self,idents,upload):
        if self._busy:return
        self._cancel_match.clear();self._matching=True
        def run():
            from save_workflow import run_workflow
            totals=run_workflow(self.store,idents,self.matchReady.emit,self._cancel_match,upload,recheck=False)
            return f"批量备份完成：上传 {totals['uploaded']}，本地 {totals['local_only']}，核对 {totals['review']}，失败 {totals['failed']}"
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
        self._cloud_history=[]
        self._history = []
        self.changed.emit()
        self.job('history', lambda: self.store.history(ident))
    @Slot(str)
    def refreshCloudHistory(self,ident):
        self._cloud_history=[]
        self.job('cloud-history',lambda:self.store.cloud_history(ident))
    @Slot(str,int,str)
    def setSnapshotNote(self,ident,snapshot,note):self.job('snapshot-note',lambda:(self.store.set_snapshot_note(ident,snapshot,note),'备注已保存')[1])
    @Slot(str,'QVariantMap')
    def restoreCloudSnapshot(self,ident,record):
        def restore():
            allowed=next((row for row in self._cloud_history if row['remote']==record.get('remote')),None)
            if allowed is None:raise ValueError('云端记录已更新，请重新刷新')
            snapshot=self.store.receive_cloud_snapshot(ident,allowed)
            self.store.restore(ident,snapshot)
            return '云端备份已下载并恢复，原存档已另行备份'
        self.job('cloud-restore',restore)
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
    @Slot('QVariantList','QVariantMap')
    def matchGames(self,idents,values=None):
        if self._busy: return
        idents=list(dict.fromkeys(idents))
        self._cancel_match.clear()
        self._matching=True
        def match():
            if values:self.store.save_settings(values)
            from local_index import clear
            clear()
            count=0
            results={row['id']:row for row in self.store.match_report}
            games={game['id']:game for game in self.store.games if game['id'] in idents}
            def one(ident):
                if self._cancel_match.is_set():return None
                game=games[ident]
                self.matchReady.emit({'id':ident,'name':game['name'],'status':'running','message':'本地、联网资料和 DeepSeek 并行查找…','candidates':[],'checked':[],'aliases':[],'english_name':'','note':''})
                try:return self.store.match_game(ident,self.matchReady.emit,self._cancel_match)
                except Exception as error:return {'id':ident,'name':game['name'],'status':'failed','message':str(error) if isinstance(error,ValueError) else '本地扫描失败，请检查目录权限','candidates':[],'checked':[],'aliases':[],'english_name':'','note':''}
            with ThreadPoolExecutor(max_workers=max(1,min(3,int(self.store.settings.get('match_workers',2))))) as workers:
                pending={workers.submit(one,ident):ident for ident in games}
                for future in as_completed(pending):
                    if self._cancel_match.is_set():
                        for queued in pending:queued.cancel()
                    if future.cancelled():continue
                    result=future.result()
                    if result is None:continue
                    self.matchReady.emit(result);results[result['id']]=result
                    self.store.save_match_report(list(results.values()));count+=1
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
            applied=self.store.local[ident]['save_dir']
            result={**row,'status':'applied','message':'已确认并设置本机存档目录：'+applied,'applied_path':applied}
            reports={row['id']:row for row in self.store.match_report}
            reports[ident]=result
            self.store.save_match_report(list(reports.values()))
            return result
        self.job('apply-match',apply)

    @Slot('QVariantList')
    def applyMatches(self, selections):
        def apply():
            from save_groups import complete_directory
            reports={row['id']:row for row in self._matches}
            prepared=[]; occupied={}
            selected={item['id'] for item in selections}
            for ident,local in self.store.local.items():
                if ident not in selected and local.get('save_dir'):
                    occupied[str(complete_directory(local['save_dir']).resolve()).casefold()]=ident
            for item in selections:
                ident=item['id']; path=item['path']; row=reports.get(ident,{})
                if not any(game['id']==ident for game in self.store.games):raise ValueError('游戏条目已不存在')
                row={**next(game for game in self.store.games if game['id']==ident),**row}
                row.setdefault('candidates',[]);row.setdefault('checked',[])
                if path not in [c['path'] for c in row.get('candidates',[])] and path not in self._picked_save_folders and path!=self.store.local.get(ident,{}).get('save_dir'):
                    raise ValueError('选中的目录已不在候选结果中，请重新选择')
                if not Path(path).is_dir():raise ValueError('选中的目录已不存在，请重新查找')
                complete=str(complete_directory(path).resolve())
                key=complete.casefold()
                if key in occupied and occupied[key]!=ident:
                    raise ValueError('多个游戏使用同一存档目录，请分别核对后确认')
                if any(other!=ident and (Path(complete).is_relative_to(Path(other_path)) or Path(other_path).is_relative_to(Path(complete))) for other_path,other in occupied.items()):
                    raise ValueError('所选存档目录有包含关系，请分别核对后确认')
                occupied[key]=ident; prepared.append((ident,complete,row))
            rows=[]
            updated_local={ident:dict(value) for ident,value in self.store.local.items()}
            for ident,path,row in prepared:
                updated_local[ident]={**updated_local.get(ident,{}),'save_dir':path}
                updated={**row,'status':'applied','applied_path':path,'message':'已设置存档目录：'+path}
                reports[ident]=updated; rows.append(updated)
            from services import write_json
            write_json(self.store.profile/'games.json',updated_local)
            self.store.local=updated_local
            self.store.save_match_report(list(reports.values()))
            return {'rows':rows,'message':f'已确认 {len(rows)} 款游戏的存档目录'}
        self.job('apply-matches',apply)

    @Slot(str,result=str)
    def recommendedMatchPath(self,ident):
        current=self.store.local.get(ident,{}).get('save_dir','')
        if current and Path(current).is_dir():return current
        from save_workflow import select_candidate
        result=next((row for row in self._matches if row['id']==ident),{})
        candidate=select_candidate(result)
        return candidate['path'] if candidate else ''

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
    @Slot(str,result=str)
    def pickSaveFolder(self,current):
        chosen=QFileDialog.getExistingDirectory(None,'选择游戏存档目录（包含所有存档槽）',current)
        if not chosen:return ''
        from save_groups import complete_directory
        complete=str(complete_directory(chosen))
        self._picked_save_folders.add(complete)
        if complete!=chosen:
            self._status='检测到多个存档槽，已选择完整存档目录：'+complete
            self.changed.emit()
        return complete
    @Slot(str, result=str)
    def pickFile(self, kind):
        return QFileDialog.getOpenFileName(None, '选择文件', '', '图片 (*.jpg *.png *.webp *.jpeg)' if kind == 'cover' else '启动文件 (*.exe *.bat *.cmd)')[0]

    def poll(self):
        if self._busy or self._watch_pending or not self.store.settings.get('watch'): return
        configured={ident:local for ident,local in self.store.local.items() if local.get('save_dir') and Path(local.get('monitor_exe') or local.get('exe','')).suffix.casefold()=='.exe' and any(game['id']==ident for game in self.store.games)}
        if not configured:return
        self._watch_pending=True
        def check():
            import psutil
            try:
                processes=[p.info for p in psutil.process_iter(['name','exe'])]
                paths={str(Path(p['exe']).resolve()).casefold() for p in processes if p.get('exe')}
                names={p['name'].casefold() for p in processes if p.get('name') and not p.get('exe')}
                configured_names=[Path(local.get('monitor_exe') or local.get('exe','')).name.casefold() for local in configured.values()]
                states={}
                for ident,local in configured.items():
                    file=Path(local.get('monitor_exe') or local['exe']);name=file.name.casefold()
                    states[ident]=str(file.resolve()).casefold() in paths or (configured_names.count(name)==1 and name in names)
                self.watchReady.emit(states)
            except Exception:self.watchReady.emit(None)
        self.pool.submit(check)

    @Slot(object)
    def receiveWatch(self,states):
        self._watch_pending=False
        if states is None or self._busy or not self.store.settings.get('watch'):return
        transitions=[(ident,running) for ident,running in states.items() if running!=self._running.get(ident,False)]
        self._running.update(states)
        if not transitions:return
        def backup():
            failed=0
            if self.store.settings.get('tray_notifications',True):self.notificationReady.emit('自动备份','正在备份 '+str(len(transitions))+' 款游戏存档',False)
            for ident,running in transitions:
                if running:self.store.mark_played(ident)
                archive=self.store.backup(ident,'game_start' if running else 'game_stop')
                if self.store.settings.get('watch_upload',True):
                    try:self.store.upload(ident,archive)
                    except Exception:failed+=1
            message=f'自动备份完成：{len(transitions)} 份'+(f'，{failed} 份上传失败，已保留本地' if failed else '')
            if self.store.settings.get('tray_notifications',True):self.notificationReady.emit('自动备份完成',message,bool(failed))
            return message
        self.job('watch',backup)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshot')
    parser.add_argument('--startup-report')
    parser.add_argument('--quit-after', type=int, default=0)
    parser.add_argument('--self-test')
    parser.add_argument('--self-test-online')
    parser.add_argument('--show',choices=('library','cloud','match','settings','import','batch','setup'),default='library')
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
            from library_sources import scan
            from cloud_history import digest
            launch_folder=Path(temporary)/'ScanFixture';launch_folder.mkdir()
            (launch_folder/'ScanFixture.exe').write_bytes(b'not executable fixture')
            assert len(scan(launch_folder)['rows'])==1 and len(digest(archive))==64
            gc.collect()
        Path(args.self_test).write_text('PASS: packaged backup/restore, SQLite, Chinese JSON, DPAPI, rclone, launcher scan, cloud hash module',encoding='utf-8')
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
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty('backend', bridge)
    engine.load(QUrl.fromLocalFile(str(RESOURCES / 'ui/Main.qml')))
    if not engine.rootObjects():
        bridge.pool.shutdown(wait=False)
        return 1
    root_window = engine.rootObjects()[0]
    if args.startup_report:
        def ready():
            Path(args.startup_report).write_text(str(round(time.perf_counter()-_PROCESS_START,3)),encoding='utf-8')
        QTimer.singleShot(0,ready)
    tray = QSystemTrayIcon(app.windowIcon(),app)
    if tray.isSystemTrayAvailable():
        app.setQuitOnLastWindowClosed(False)
        menu=QMenu()
        def show_window():root_window.show();root_window.raise_();root_window.requestActivate()
        menu.addAction('打开游戏库',show_window)
        def toggle_watch():bridge.saveSettings({'watch':not bridge.store.settings.get('watch')})
        menu.addAction('开启 / 暂停监听',toggle_watch)
        menu.addSeparator();menu.addAction('退出',app.quit)
        tray.setContextMenu(menu);tray.setToolTip('GameCloudSave');tray.show()
        bridge.notificationReady.connect(lambda title,message,error:tray.showMessage(title,message,QSystemTrayIcon.Warning if error else QSystemTrayIcon.Information,5000))
        tray.activated.connect(lambda reason:show_window() if reason==QSystemTrayIcon.Trigger else None)
    window = root_window
    if args.show!='library':QMetaObject.invokeMethod(root_window.findChild(QObject,'setupWizard'),'hide')
    if args.show=='setup':
        QMetaObject.invokeMethod(window,'openSetup');window=window.findChild(QObject,'setupWizard')
    elif args.show=='batch':
        QMetaObject.invokeMethod(window,'openBatch');window=window.findChild(QObject,'batchWindow')
    elif args.show=='import':
        QMetaObject.invokeMethod(window,'openImport')
        window=window.findChild(QObject,'importWindow')
    elif args.show=='settings':
        QMetaObject.invokeMethod(window,'openSettings')
    elif args.show=='cloud':
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
    tray.hide()
    bridge.timer.stop()
    bridge.flushLayout()
    bridge.pool.shutdown(wait=True)
    import shiboken6
    shiboken6.delete(engine)
    return result

if __name__ == '__main__': sys.exit(main())
