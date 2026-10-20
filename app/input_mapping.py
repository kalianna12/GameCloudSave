"""Mapping editor and one bounded background runtime; injection is off until explicitly enabled."""
import copy
import json
import os
import threading
import time
import uuid
from collections import deque

from PySide6.QtCore import QObject,Property,Signal,Slot,QEvent,Qt,QCoreApplication,QTimer
from mapping_model import default_profile,validate,chord,token_name,direction_keys,Forward,Reverse,PAD_BUTTONS,PAD_OUTPUTS,DIRECTIONS,KEY_NAMES
from mapping_templates import make_template,template_catalog


class MappingController(QObject):
    changed=Signal()
    stateChanged=Signal()
    sampled=Signal(object)
    runtimeMessage=Signal(str,bool)
    selectionChanged=Signal()
    previewChanged=Signal()
    keyboardPreviewChanged=Signal()
    modelChanged=Signal()
    dropHintChanged=Signal()

    def __init__(self,store,parent=None,transport_factory=None,virtual_factory=None):
        super().__init__(parent)
        self.store=store;self.file=store.profile/'input-mapping.json'
        self._profiles={};self._selected='default';self._draft=default_profile();self._target='A';self._route='';self._dirty=False
        self._enabled=False;self._editor=False;self._message='映射未启用';self._sample={};self._recording=False;self._capture=[];self._capture_held=set();self._capture_kind='binding'
        self._host=None;self._runtime_host=None;self._raw=None;self._thread=None;self._closed=False;self._stop=threading.Event();self._wake=threading.Event();self._lock=threading.Lock();self._revision=0
        self._capture_draining=set();self._capture_cancel_mouse=False;self._wheel_guard_until=0
        self._transport_factory=transport_factory;self._virtual_factory=virtual_factory
        self._virtual_index=-1
        self._virtual_ready=None
        self._auto_select=True
        self._events=[];self._seen_input=set();self._preview_forward=Forward();self._preview_reverse=Reverse()
        from mapping_preview import InputHistory
        self._history_model=InputHistory(self);self._pending_sample=None;self._pending_edges=deque(maxlen=512);self._keyboard_preview=[];self._preview_last=time.perf_counter();self._drop_hint='';self._drop_target='';self._editor_wheel={}
        self._preview_timer=QTimer(self);self._preview_timer.setTimerType(Qt.PreciseTimer);self._preview_timer.setInterval(8);self._preview_timer.timeout.connect(self.publishPreview)
        self.changed.connect(self.selectionChanged.emit);self.changed.connect(self.modelChanged.emit)
        from mapping_setup import MappingSetup
        self._setup=MappingSetup(store,self);self._setup.changed.connect(self.setupChanged)
        self.load();self.sampled.connect(self.receiveSample);self.runtimeMessage.connect(self.receiveRuntimeMessage)
        self._runtime_profile=copy.deepcopy(self._draft)
        self._saved_ids=set(self._profiles)
        app=QCoreApplication.instance()
        if app:app.installEventFilter(self)

    def load(self):
        try:
            data=json.loads(self.file.read_text(encoding='utf-8'))
            if not isinstance(data,dict) or data.get('version')!=1 or not isinstance(data.get('profiles'),dict) or len(data['profiles'])>40:raise ValueError()
            self._profiles={key:validate(profile) for key,profile in data['profiles'].items() if isinstance(key,str)}
            self._selected=data.get('selected') if data.get('selected') in self._profiles else next(iter(self._profiles))
            self._draft=copy.deepcopy(self._profiles[self._selected])
        except (OSError,ValueError,TypeError,KeyError,StopIteration):self._profiles={'default':default_profile()};self._selected='default';self._draft=default_profile()
        self._route=next((row['id'] for row in self._draft['reverse']['routes']), '')

    @Property('QVariantMap',notify=changed)
    def profile(self):return self._draft
    @Property(QObject,constant=True)
    def setup(self):return self._setup
    @Property(QObject,constant=True)
    def history(self):return self._history_model
    @Property('QVariantMap',notify=previewChanged)
    def live(self):return self._sample
    @Property('QStringList',notify=keyboardPreviewChanged)
    def keyboardPreview(self):return self._keyboard_preview
    @Property(str,notify=modelChanged)
    def padModel(self):return self._draft.get('padModel','xbox')
    @Property(str,notify=dropHintChanged)
    def dropHint(self):return self._drop_hint
    @Property(str,notify=dropHintChanged)
    def dropTarget(self):return self._drop_target
    @Property('QVariantList',notify=changed)
    def profiles(self):return [{'id':key,'name':profile['name']} for key,profile in self._profiles.items()]
    @Property('QVariantList',constant=True)
    def templates(self):return template_catalog()
    @Property('QStringList',notify=changed)
    def addedTemplates(self):return sorted({p['templateId'] for key,p in self._profiles.items() if key in self._saved_ids and isinstance(p.get('templateId'),str)})
    def importTemplates(self,idents):
        known={row['id'] for row in self.templates}
        if any(ident not in known for ident in idents):raise ValueError('游戏模板不存在')
        additions={};existing={}
        for key,p in self._profiles.items():
            if key in self._saved_ids and isinstance(p.get('templateId'),str):existing.setdefault(p['templateId'],key)
        for ident in idents:
            if ident not in existing:
                key='template-'+ident
                if key in self._profiles:key=uuid.uuid4().hex
                profile=make_template(ident);profile['padModel']=self.padModel;profile['slot']=self._draft['slot']
                additions[key]=profile;existing[ident]=key
        if len(self._profiles)+len(additions)>40:raise ValueError('配置已满，最多 40 份；请先删除不用的配置')
        if additions:
            # Import only saved profiles plus the new templates. Keep unrelated unsaved drafts untouched.
            saved={key:p for key,p in self._profiles.items() if key in self._saved_ids}|additions
            selected=self._selected if self._selected in saved else next(iter(saved))
            temporary=self.file.with_suffix('.tmp');temporary.write_text(json.dumps({'version':1,'selected':selected,'profiles':saved},ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(self.file)
            self._profiles.update(additions);self._saved_ids.update(additions);self.changed.emit()
        return existing,len(additions)
    @Slot(str,result=bool)
    def addTemplate(self,ident):
        try:
            existing,count=self.importTemplates([ident])
            if existing[ident]!=self._selected:self.selectProfile(existing[ident])
            self._message='已创建配置，可直接编辑' if count else '已打开现有配置，保留你的修改';self.stateChanged.emit();return True
        except (ValueError,OSError,TypeError,KeyError) as error:self.receiveMessage(str(error),False);return False
    @Slot(result=bool)
    def addAllTemplates(self):
        try:
            _,count=self.importTemplates([row['id'] for row in self.templates]);self._message='已添加 '+str(count)+' 组配置，已有模板保持不变' if count else '8 组模板已添加，保留你的修改';self.stateChanged.emit();return True
        except (ValueError,OSError,TypeError,KeyError) as error:self.receiveMessage(str(error),False);return False
    @Property('QVariantList',notify=changed)
    def profileOptions(self):
        return [{'id':'','label':'无 · 关闭映射','mode':'none'}]+[{'id':key,'label':('🎮 → ⌨  ' if profile['mode']=='pad_to_keys' else '⌨ → 🎮  ')+profile['name'],'mode':profile['mode']} for key,profile in self._profiles.items() if key in self._saved_ids]
    @Property(str,notify=stateChanged)
    def activeProfile(self):return self._selected if self._enabled else ''
    @Slot(str)
    def activateProfile(self,ident):
        if not ident:self.setEnabled(False);return
        if ident in self._saved_ids and ident in self._profiles:self.selectProfile(ident);self.setEnabled(True)
    @Property(str,notify=changed)
    def profileId(self):return self._selected
    @Property(str,notify=selectionChanged)
    def target(self):return self._target if self._draft['mode']=='pad_to_keys' else self._route
    @Property('QVariantList',notify=selectionChanged)
    def currentChord(self):
        if self._draft['mode']=='keys_to_pad':return self.route().get('targets',[])
        owner,key=self.binding();return owner.get(key,[])
    @Property('QVariantList',notify=selectionChanged)
    def sourceChord(self):return self.route().get('source',[]) if self._draft['mode']=='keys_to_pad' else []
    @Property(str,notify=selectionChanged)
    def bindingLabel(self):
        if self._draft['mode']=='keys_to_pad':return ' + '.join(token_name(t) for t in self.sourceChord) or '选择键盘或鼠标按键'
        return self.label('P:'+self._target).replace('.light.',' · 轻推 ').replace('.hard.',' · 重推 ').replace('.lightExtra',' · 轻推附加键').replace('.hardExtra',' · 重推附加键')
    @Property('QVariantMap',notify=stateChanged)
    def state(self):
        from mapping_native import virtual_available
        if self._virtual_ready is None:self._virtual_ready=virtual_available()
        return {'enabled':self._enabled,'editor':self._editor,'message':self._message,'recording':self._recording,
                'captured':[token_name(t) for t in self._capture],'sample':self._sample,'events':self._events,'virtualReady':self._virtual_ready,'dirty':self._dirty}
    @Property('QVariantList',constant=True)
    def allKeys(self):
        order=list(dict.fromkeys([*range(65,91),*range(48,58),*range(112,136),*sorted(KEY_NAMES),*range(7,255)]))
        return [{'token':'K:'+str(vk),'label':token_name('K:'+str(vk))} for vk in order]
    @Property('QVariantList',notify=changed)
    def reverseRoutes(self):return [{'id':r['id'],'label':' + '.join(self.label(t) for t in r['source'])+' → '+' + '.join(self.label(t) for t in r['targets'])} for r in self._draft['reverse']['routes']]

    @Slot(str,result=str)
    def label(self,token):
        if token.startswith('P:'):
            name=token[2:];model=self._draft.get('padModel','xbox')
            axes={'LX-':'左摇杆 ←','LX+':'左摇杆 →','LY+':'左摇杆 ↑','LY-':'左摇杆 ↓','RX-':'右摇杆 ←','RX+':'右摇杆 →','RY+':'右摇杆 ↑','RY-':'右摇杆 ↓'}
            if name in axes:return axes[name]
            if name.startswith(('LS.','RS.')):
                parts=name.split('.');stick='左摇杆' if parts[0]=='LS' else '右摇杆';zone={'light':'轻推','hard':'重推','lightExtra':'轻推附加键','hardExtra':'重推附加键'}.get(parts[1],parts[1])
                return stick+' · '+zone+(' '+dict(zip(DIRECTIONS,['↑','↗','→','↘','↓','↙','←','↖'])).get(parts[2],parts[2]) if len(parts)>2 else '')
            if name in ('LS','RS'):return '左摇杆按下' if name=='LS' else '右摇杆按下'
            if name.startswith('D') and name in PAD_BUTTONS:return {'DUp':'十字键 ↑','DDown':'十字键 ↓','DLeft':'十字键 ←','DRight':'十字键 →'}.get(name,name)
            if model=='ps':return {'A':'×','B':'○','X':'□','Y':'△','LB':'L1','RB':'R1','LT':'L2','RT':'R2'}.get(name,name)
            if model=='joycon':return {'A':'B','B':'A','X':'Y','Y':'X','LB':'L','RB':'R','LT':'ZL','RT':'ZR'}.get(name,name)
        return token_name(token)
    @Slot()
    def setupChanged(self):self._virtual_ready=None;self.stateChanged.emit()
    def route(self):return next((row for row in self._draft['reverse']['routes'] if row['id']==self._route),{})
    def binding(self):
        if self._target in PAD_BUTTONS:return self._draft['forward']['buttons'],self._target
        parts=self._target.split('.');cfg=self._draft['forward']['sticks'][parts[0]]
        return (cfg[parts[1]],parts[2]) if len(parts)==3 else (cfg,parts[1])
    def edit(self):self._dirty=True;self.changed.emit();self.stateChanged.emit()

    @Slot(str)
    def selectTarget(self,target):
        if target not in PAD_BUTTONS and not any(target in [s+'.'+zone+'.'+d for zone in ('light','hard') for d in DIRECTIONS]+[s+'.lightExtra',s+'.hardExtra'] for s in ('LS','RS')):return
        if self._target!=target:self._target=target;self.selectionChanged.emit()
    @Slot('QVariantList')
    def setChord(self,values):
        try:
            values=chord(list(values),self._draft['mode']=='keys_to_pad')
            if self._draft['mode']=='keys_to_pad':
                route=self.route()
                if not route:return
                route['targets']=values
            else:
                owner,key=self.binding();owner[key]=values
            self.edit()
        except ValueError as error:self.receiveMessage(str(error),False)
    @Slot(str)
    def chooseKey(self,token):
        try:
            chord([token])
            if self._draft['mode']=='pad_to_keys':
                values=list(self.currentChord);values.remove(token) if token in values else values.append(token);self.setChord(values)
            else:self.selectSource([token])
        except ValueError:pass
    @Slot(str)
    def choosePad(self,token):
        name=token.removeprefix('P:')
        if self._draft['mode']=='pad_to_keys':self.selectTarget(name)
        elif name in PAD_OUTPUTS:
            values=list(self.currentChord);values.remove('P:'+name) if 'P:'+name in values else values.append('P:'+name);self.setChord(values)
    @Slot('QVariantList')
    def selectSource(self,values):
        values=chord(list(values));route=next((r for r in self._draft['reverse']['routes'] if r['source']==values),None)
        if route is None:
            if len(self._draft['reverse']['routes'])>=160:self.receiveMessage('最多 160 条绑定',False);return
            route={'id':uuid.uuid4().hex,'source':values,'targets':[]};self._draft['reverse']['routes'].append(route);self._dirty=True
        self._route=route['id'];self.changed.emit();self.stateChanged.emit()
    @Slot(str)
    def selectRoute(self,ident):
        if any(row['id']==ident for row in self._draft['reverse']['routes']) and self._route!=ident:self._route=ident;self.selectionChanged.emit()
    @Slot()
    def deleteRoute(self):
        self._draft['reverse']['routes']=[r for r in self._draft['reverse']['routes'] if r['id']!=self._route]
        self._route=next((r['id'] for r in self._draft['reverse']['routes']),'');self.edit()
    @Slot(str,str,bool)
    def dropBinding(self,source,target,append):
        try:
            if self._draft['mode']=='pad_to_keys' and target.startswith('P:'):
                chord([source]);self.selectTarget(target[2:]);self.setChord(list(self.currentChord)+[source] if append else [source])
            elif self._draft['mode']=='keys_to_pad' and source.startswith('P:'):
                chord([source],True);self.selectSource([target]);self.setChord(list(self.currentChord)+[source] if append else [source])
        except (ValueError,KeyError):pass
    @Slot(str)
    def setMode(self,mode):
        if mode in ('pad_to_keys','keys_to_pad') and mode!=self._draft['mode']:
            self.cancelCapture()
            self.setEnabled(False);self._draft['mode']=mode;self.edit()
    @Slot(str)
    def setModel(self,model):
        if model in ('xbox','ps','joycon') and model!=self.padModel:
            self._draft['padModel']=model;self._dirty=True;self.modelChanged.emit();self.selectionChanged.emit();self.stateChanged.emit()
    @Slot()
    def clearEvents(self):self._events=[];self._history_model.clear();self.stateChanged.emit()
    @Slot(str,str,result=bool)
    def canDrop(self,source,target):
        try:
            if self._draft['mode']=='pad_to_keys' and target.startswith('P:'):
                chord([source]);return target[2:] in PAD_BUTTONS or any(target[2:] in [s+'.'+z+'.'+d for z in ('light','hard') for d in DIRECTIONS]+[s+'.lightExtra',s+'.hardExtra'] for s in ('LS','RS'))
            if self._draft['mode']=='keys_to_pad' and source.startswith('P:'):chord([source],True);chord([target]);return True
        except ValueError:pass
        return False
    @Slot(str,str)
    def hoverDrop(self,source,target):
        if not self.canDrop(source,target):return
        first,second=(target,source) if self._draft['mode']=='keys_to_pad' else (source,target)
        self._drop_target=target;self._drop_hint='松开绑定：'+self.label(first)+' → '+self.label(second);self.dropHintChanged.emit()
    @Slot(str)
    def clearDropHint(self,target=''):
        if self._drop_target and (not target or target==self._drop_target):self._drop_target='';self._drop_hint='';self.dropHintChanged.emit()
    @Slot(str,str,'QVariant')
    def setOption(self,section,key,value):
        owner=self._draft['forward']['sticks'].get(section) if section in ('LS','RS') else self._draft['reverse'] if section=='reverse' else None
        if owner is None or key not in owner or isinstance(owner[key],dict):return
        old=copy.deepcopy(owner[key]);owner[key]=value
        try:validate(self._draft);self.edit()
        except (ValueError,TypeError,KeyError):owner[key]=old;self.receiveMessage('设置超出可用范围',False)
    @Slot(str,str,str)
    def applyStickPreset(self,stick,zone,preset):
        if stick not in ('LS','RS') or zone not in ('light','hard','both') or preset not in ('wasd','arrows'):return
        cfg=self._draft['forward']['sticks'][stick]
        for target in (('light','hard') if zone=='both' else (zone,)):cfg[target]=direction_keys(preset)
        if not self._target.startswith(stick+'.') or zone!='both':self.selectTarget(stick+'.'+('light' if zone=='both' else zone)+'.N')
        self.edit()
    @Slot(str,result=str)
    def wheelTarget(self,source):
        route=next((r for r in self._draft['reverse']['routes'] if r['source']==[source]),None)
        targets=route['targets'] if route else []
        return targets[0] if len(targets)==1 and targets[0][2:] in ('LX+','LX-','LY+','LY-','RX+','RX-','RY+','RY-') else 'custom' if targets else ''
    @Slot(str,str)
    def setWheelTarget(self,source,target):
        if source not in ('M:wheelup','M:wheeldown') or target not in ('','P:LX+','P:LX-','P:LY+','P:LY-','P:RX+','P:RX-','P:RY+','P:RY-'):return
        # Only the plain wheel route is edited; modified wheel chords remain independent.
        route=next((r for r in self._draft['reverse']['routes'] if r['source']==[source]),None)
        if route is None and target:
            if len(self._draft['reverse']['routes'])>=160:self.receiveMessage('最多 160 条绑定',False);return
            route={'id':uuid.uuid4().hex,'source':[source],'targets':[]};self._draft['reverse']['routes'].append(route)
        if route is not None:
            self._draft['reverse']['routes']=[r for r in self._draft['reverse']['routes'] if r is route or r['source']!=[source]]
            route['targets']=[target] if target else [];self._route=route['id'];self.edit()
    @Slot(int)
    def setSlot(self,slot):
        if -1<=slot<=3:
            if self._enabled:self.setEnabled(False)
            self._draft['slot']=slot
            with self._lock:self._runtime_profile['slot']=slot;self._revision+=1
            self._wake.set();self.edit()
    @Slot(str)
    def rename(self,name):
        if 1<=len(name.strip())<=40:self._draft['name']=name.strip();self.edit()
    @Slot(str)
    def selectProfile(self,ident):
        if ident in self._profiles:
            self.setEnabled(False);self._selected=ident;self._draft=copy.deepcopy(self._profiles[ident]);self._dirty=False;self._route=next((r['id'] for r in self._draft['reverse']['routes']),'');self.changed.emit();self.stateChanged.emit()
            with self._lock:self._runtime_profile=copy.deepcopy(self._draft);self._revision+=1
            self._wake.set()
    @Slot()
    def duplicate(self):
        if len(self._profiles)>=40:self.receiveMessage('最多 40 份配置',False);return
        self.setEnabled(False);self._selected=uuid.uuid4().hex;self._draft=copy.deepcopy(self._draft);self._draft['name']='新配置';self._profiles[self._selected]=copy.deepcopy(self._draft);self.edit()
    @Slot()
    def createProfile(self):
        if len(self._profiles)>=40:self.receiveMessage('最多 40 份配置',False);return
        self.setEnabled(False);self._selected=uuid.uuid4().hex;self._draft=default_profile('新配置');self._profiles[self._selected]=copy.deepcopy(self._draft);self._target='A';self._route='default-w';self.edit()
    @Slot()
    def deleteProfile(self):
        if len(self._profiles)<=1:return
        old=self._selected;self.selectProfile(next(key for key in self._profiles if key!=old));self._profiles.pop(old);self.edit()
    @Slot()
    def reset(self):
        self.setEnabled(False)
        if self._draft.get('templateId') in {row['id'] for row in self.templates}:
            profile=make_template(self._draft['templateId'])
            for key in ('name','padModel','slot'):profile[key]=self._draft[key]
        else:profile=default_profile(self._draft['name'])
        self._draft=profile;self._target='A';self._route='default-w';self.edit()
    @Slot(result=bool)
    def save(self):
        try:
            profile=validate(self._draft);self._profiles[self._selected]=profile
            if self._enabled:self.configureRaw(profile)
            temporary=self.file.with_suffix('.tmp');temporary.write_text(json.dumps({'version':1,'selected':self._selected,'profiles':self._profiles},ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(self.file)
            with self._lock:self._runtime_profile=copy.deepcopy(profile);self._revision+=1
            self._saved_ids.add(self._selected);self._dirty=False;self._wake.set();self._message='配置已保存';self.changed.emit();self.stateChanged.emit()
            return True
        except (ValueError,OSError,TypeError,KeyError) as error:self.receiveMessage(str(error),False);return False

    @Slot(QObject)
    def bindWindow(self,window):self._host=window
    @Slot(QObject)
    def bindRuntimeWindow(self,window):self._runtime_host=window
    @Slot(bool)
    def setPreviewActive(self,active):self._preview_timer.setInterval(8 if active else 33)
    @Slot(bool)
    def setEditorVisible(self,visible):
        if self._editor==bool(visible):return
        self._editor=bool(visible)
        if not visible:self.cancelCapture()
        if not visible:
            self._preview_timer.stop();self._events=[];self._history_model.clear();self._seen_input=set();self._preview_forward.reset();self._preview_reverse.reset();self.clearDropHint()
            with self._lock:self._pending_sample=None;self._pending_edges.clear();self._editor_wheel.clear()
            self._sample={};self._keyboard_preview=[];self.previewChanged.emit();self.keyboardPreviewChanged.emit()
        if visible:self._preview_last=time.perf_counter();self._preview_timer.start();self.ensure_worker();self._setup.detect()
        self._wake.set();self.stateChanged.emit()
    @Slot(bool)
    def setAutoSelect(self,enabled):self._auto_select=enabled
    def ensure_worker(self):
        if (self._thread is None or not self._thread.is_alive()) and not self._closed:
            self._thread=threading.Thread(target=self.run,name='input-mapping',daemon=True);self._thread.start()
    def configureRaw(self,profile):
        from mapping_native import RawMouse
        cfg=profile['reverse']
        needed=profile['mode']=='keys_to_pad' and (cfg['mouse']!='disabled' or any(route['targets'] and any(t in ('M:wheelup','M:wheeldown') for t in route['source']) for route in cfg['routes']))
        if not needed:
            if self._raw:self._raw.stop()
            return
        host=self._runtime_host or self._host
        if host is None:raise ValueError('没有可用的映射窗口')
        if self._raw is None:
            self._raw=RawMouse();QCoreApplication.instance().installNativeEventFilter(self._raw)
        self._raw.start(int(host.winId()))
    @Slot(bool)
    def setEnabled(self,enabled):
        if self._closed:return
        if enabled:
            try:
                validate(self._draft)
                if self._draft['mode']=='keys_to_pad':
                    from mapping_native import virtual_available
                    if not virtual_available():raise ValueError('键鼠→手柄需要 vgamepad 与 ViGEmBus；请查看映射帮助')
                    self.configureRaw(self._draft)
                # The runtime always reads a validated immutable saved copy.
                if not self.save():
                    if self._raw:self._raw.stop()
                    return
            except (ValueError,OSError,TypeError,KeyError) as error:self.receiveMessage(str(error),False);return
        else:
            if self._raw:self._raw.stop()
        with self._lock:self._enabled=bool(enabled);self._revision+=1
        if enabled:self.ensure_worker()
        self._wake.set();self._message='已启用，切换到游戏窗口生效' if enabled else '映射已停止';self.stateChanged.emit()

    @Slot()
    @Slot(str)
    def record(self,kind='binding'):
        self._recording=True;self._capture=[];self._capture_held=set();self._capture_kind=kind;self.stateChanged.emit()
    @Slot()
    def cancelCapture(self):
        self._capture_draining.update(self._capture_held)
        self._recording=False;self._capture_held.clear();self.stateChanged.emit()
    def finishCapture(self):
        if not self._capture or self._capture_held:return
        self._recording=False
        if self._capture_kind=='lightModifier':self.setOption('reverse','lightModifier',self._capture)
        elif self._draft['mode']=='pad_to_keys':self.setChord(self._capture)
        else:
            route=self.route()
            if route:route['source']=list(self._capture);self.edit()
            else:self.selectSource(self._capture)
        self.stateChanged.emit()
    def captureInput(self,token,pressed):
        if pressed:
            self._capture_held.add(token)
            if token not in self._capture and len(self._capture)<12:self._capture.append(token)
            self.stateChanged.emit()
        else:
            self._capture_held.discard(token);self.finishCapture()
    def eventFilter(self,watched,event):
        kind=event.type()
        # Filter at the owned window before Quick delivers input to controls. Do not
        # call window() on arbitrary QML objects (PySide ownership is significant).
        if self._host is not None and watched is not self._host:return False
        if kind==QEvent.WindowDeactivate:
            if self._recording:self.cancelCapture()
            self._capture_draining.clear();self._capture_cancel_mouse=False;self._wheel_guard_until=0
            return False
        if kind==QEvent.Wheel and (self._recording or time.perf_counter()<self._wheel_guard_until):
            self._wheel_guard_until=time.perf_counter()+.18
            delta=event.angleDelta().y() or event.pixelDelta().y()
            if self._recording and delta:
                token='M:wheelup' if delta>0 else 'M:wheeldown'
                if token not in self._capture and len(self._capture)<12:self._capture.append(token)
                self.finishCapture();self.stateChanged.emit()
            event.accept();return True
        if kind in (QEvent.MouseButtonPress,QEvent.MouseButtonDblClick,QEvent.MouseButtonRelease):
            token={Qt.LeftButton:'M:left',Qt.RightButton:'M:right',Qt.MiddleButton:'M:middle',Qt.BackButton:'M:x1',Qt.ForwardButton:'M:x2'}.get(event.button())
            released=kind==QEvent.MouseButtonRelease
            if token in self._capture_draining:
                if released:self._capture_draining.discard(token)
                event.accept();return True
            if self._capture_cancel_mouse and released:
                self._capture_cancel_mouse=False;return False
            if self._recording:
                cancel=self._host.property('captureCancelItem') if self._host is not None else None
                if not released and event.button()==Qt.LeftButton and cancel is not None and cancel.isVisible() and cancel.contains(cancel.mapFromScene(event.position())):
                    self._capture_cancel_mouse=True;return False
                if token:self.captureInput(token,not released)
                event.accept();return True
        if self._editor and self._draft['mode']=='keys_to_pad' and event.type()==QEvent.Wheel:
            if watched is self._host and event.angleDelta().y():
                token='M:wheelup' if event.angleDelta().y()>0 else 'M:wheeldown'
                with self._lock:
                    self._editor_wheel.pop('M:wheeldown' if token=='M:wheelup' else 'M:wheelup',None)
                    self._editor_wheel[token]=time.perf_counter()+self._draft['reverse']['wheelPulse']/1000
            # Preview observes the event; normal scrolling and control editing still work.
        if kind==QEvent.InputMethod and self._recording:event.accept();return True
        if kind not in (QEvent.KeyPress,QEvent.KeyRelease,QEvent.ShortcutOverride):return False
        if not self._recording and not self._capture_draining:return False
        vk=event.nativeVirtualKey()
        if not vk:
            fallback={Qt.Key_Escape:27,Qt.Key_Tab:9,Qt.Key_Backspace:8,Qt.Key_Return:13,Qt.Key_Enter:13,Qt.Key_Shift:160,Qt.Key_Control:162,Qt.Key_Alt:164,Qt.Key_Meta:91,
                      Qt.Key_Left:37,Qt.Key_Up:38,Qt.Key_Right:39,Qt.Key_Down:40,Qt.Key_Delete:46,Qt.Key_Insert:45,Qt.Key_Home:36,Qt.Key_End:35,Qt.Key_PageUp:33,Qt.Key_PageDown:34}
            vk=fallback.get(event.key(),event.key() if 32<=event.key()<=126 else 112+event.key()-Qt.Key_F1 if Qt.Key_F1<=event.key()<=Qt.Key_F24 else 0)
        scan=event.nativeScanCode()
        if vk==16:vk=161 if scan&255==0x36 else 160
        elif vk in (17,18):vk=(163 if vk==17 else 165) if scan&0x100 or scan&0xe000 else (162 if vk==17 else 164)
        if not 1<=vk<=254:return self._recording
        token='K:'+str(vk)
        if token in self._capture_draining:
            if kind==QEvent.KeyRelease and not event.isAutoRepeat():self._capture_draining.discard(token)
        elif not self._recording:return False
        elif kind!=QEvent.ShortcutOverride and not event.isAutoRepeat():self.captureInput(token,kind==QEvent.KeyPress)
        event.accept()
        return True

    @Slot(object)
    def receiveSample(self,sample):
        if not self._editor:return
        now=time.perf_counter();dt=min(.05,max(.001,now-self._preview_last));self._preview_last=now
        preview=dict(sample);self._last_capture_age=now-preview.pop('_captured',now)
        keys=set(sample.get('keys',[]));inputs=keys|{'P:'+b for b in sample.get('buttons',[])}
        if self._draft['mode']=='pad_to_keys':
            desired,move=self._preview_forward.frame(self._draft,sample,dt);preview['outputs']=sorted(desired|{'M:'+d for d in self._preview_forward.wheel_steps});preview['mouse']=move
        else:
            held=set(keys)
            for generic,sides in (('K:16',{'K:160','K:161'}),('K:17',{'K:162','K:163'}),('K:18',{'K:164','K:165'})):
                if keys&sides:held.add(generic)
            report=self._preview_reverse.frame(self._draft,held,sample.get('mouseDelta',[0,0]),dt)
            preview['outputs']=['P:'+name for name,mask in __import__('mapping_model').BUTTONS.items() if report['buttons']&mask]+['P:'+key for key in ('LT','RT') if report[key]]
            preview['outputs']+=['P:'+key+('+' if report[key]>0 else '-') for key in ('LX','LY','RX','RY') if abs(report[key])>512]
            preview['virtualAxes']=[report[key]/32767 for key in ('LX','LY','RX','RY')]
        edges=preview.pop('_edges',None)
        if edges is None:edges=[{'token':token,'down':down,'at':time.time()} for token,down in [(t,False) for t in sorted(self._seen_input-inputs)]+[(t,True) for t in sorted(inputs-self._seen_input)]]
        self._history_model.push(edges,self.label);self._events=self._history_model.rows;self._seen_input=inputs
        preview['flashes']=[e['token'][2:] for e in edges if e['down'] and e['token'].startswith('P:')]
        new=[e['token'][2:] for e in edges if e['down'] and e['token'].startswith('P:')]
        if self._auto_select and not self._recording and self._draft['mode']=='pad_to_keys' and new:self.selectTarget(new[-1])
        keyboard=sorted(keys|({t for t in preview['outputs'] if not t.startswith('P:')} if self._draft['mode']=='pad_to_keys' else set())|{e['token'] for e in edges if e['down'] and not e['token'].startswith('P:')})
        if keyboard!=self._keyboard_preview:self._keyboard_preview=keyboard;self.keyboardPreviewChanged.emit()
        if preview!=self._sample:self._sample=preview;self.previewChanged.emit()

    @Slot()
    def publishPreview(self):
        if not self._editor:return
        with self._lock:
            sample=self._pending_sample;self._pending_sample=None
            edges=list(self._pending_edges);self._pending_edges.clear()
        if sample is not None:sample['_edges']=edges;self.receiveSample(sample)

    def queuePreview(self,sample,edges):
        with self._lock:
            if not self._editor:return
            if self._pending_sample is not None:
                old=self._pending_sample.get('mouseDelta',[0,0]);delta=sample.get('mouseDelta',[0,0]);sample['mouseDelta']=[old[i]+delta[i] for i in range(2)]
            self._pending_sample=sample;self._pending_edges.extend(edges)
    @Slot(str,bool)
    def receiveMessage(self,message,stop):
        if stop:self.setEnabled(False)
        self._message=message;self.stateChanged.emit()

    @Slot(str,bool)
    def receiveRuntimeMessage(self,message,stop):
        # A queued running status must not replace an explicit stop in the UI.
        if stop or self._enabled:self.receiveMessage(message,stop)

    def run(self):
        from mapping_native import WindowsInput,KeyOutput,VirtualPad
        from mapping_clock import PollClock
        try:transport=(self._transport_factory or WindowsInput)()
        except Exception as error:self.runtimeMessage.emit('无法读取输入：'+str(error)[:120],True);return
        output=KeyOutput(transport);forward=Forward();reverse=Reverse();virtual=None
        revision=-1;profile=None;last=time.perf_counter();foreground=None;armed=False;previous_message=''
        sample_at=0;known_slot=-1;state=None;slot=-1;preview_cursor=None;wheel_until={}
        clock=PollClock();monitor_inputs=set();monitor_keys=[];key_at=0;last_own=None;self._capture_count=0
        all_preview_keys=tuple('K:'+str(vk) for vk in range(8,255) if vk not in (16,17,18))+tuple('M:'+name for name in ('left','right','middle','x1','x2'))
        configured_keys=set()
        try:
            while not self._stop.is_set():
                now=time.perf_counter();dt=min(.05,now-last);last=now
                with self._lock:
                    enabled=self._enabled;current_revision=self._revision
                    if current_revision!=revision:profile=copy.deepcopy(self._runtime_profile)
                if current_revision!=revision:
                    output.release();forward.reset();reverse.reset();armed=False;foreground=None
                    if virtual:virtual.close();virtual=None;self._virtual_index=-1
                    revision=current_revision;sample_at=0;known_slot=-1;previous_message='';wheel_until.clear()
                    configured_keys={t for route in profile['reverse']['routes'] for t in route['source']}|set(profile['reverse']['lightModifier'])
                if not enabled and not self._editor:
                    self._wake.wait(.5);self._wake.clear();continue
                if profile['mode']=='pad_to_keys' or self._editor:
                    if now>=sample_at:
                        state,slot=transport.sample(known_slot if profile['slot']<0 else profile['slot'],self._virtual_index)
                        known_slot=slot if state else -1;sample_at=now+(0 if state else .5)
                else:state=None;slot=-1
                current=transport.foreground();own=current[1]==os.getpid();raw=self._raw;mouse,pulses=raw.take() if raw else ([0,0],set())
                if len(pulses)==1:wheel_until.pop('M:wheeldown' if 'M:wheelup' in pulses else 'M:wheelup',None)
                for token in pulses:wheel_until[token]=now+profile['reverse'].get('wheelPulse',100)/1000
                wheel_until={token:until for token,until in wheel_until.items() if until>now};pulses=set(wheel_until)
                if self._editor:
                    # Full keyboard preview only while our editor has foreground focus.
                    if now>=key_at or own!=last_own:
                        preview_keys=all_preview_keys if own else configured_keys if profile['mode']=='keys_to_pad' else ()
                        monitor_keys=[token for token in preview_keys if transport.held(token)];key_at=now+.008;last_own=own
                    with self._lock:
                        self._editor_wheel={token:until for token,until in self._editor_wheel.items() if until>now}
                        editor_pulses=set(self._editor_wheel)
                    keys=sorted(set(monitor_keys)|pulses|editor_pulses);delta=list(mouse)
                    if own and hasattr(transport,'pointer'):
                        cursor=transport.pointer()
                        if preview_cursor:delta=[cursor[i]-preview_cursor[i] for i in range(2)]
                        preview_cursor=cursor
                    else:preview_cursor=None
                    current_inputs=set(keys)|{'P:'+button for button in (state or {}).get('buttons',[])}
                    edges=[{'token':token,'down':down,'at':time.time()} for token,down in [(t,False) for t in sorted(monitor_inputs-current_inputs)]+[(t,True) for t in sorted(current_inputs-monitor_inputs)]]
                    monitor_inputs=current_inputs;self._capture_count+=1
                    self.queuePreview({**(state or {'buttons':[],'LS':[0.,0.],'RS':[0.,0.]}),'keys':keys,'mouseDelta':delta,'connected':state is not None,'slot':slot,'_captured':now},edges)
                else:monitor_inputs.clear();preview_cursor=None;key_at=0
                if enabled and all(transport.held(token) for token in ('K:17','K:18','K:123')):
                    with self._lock:self._enabled=False
                    enabled=False;output.release()
                    if virtual:virtual.close();virtual=None;self._virtual_index=-1
                    self.runtimeMessage.emit('已用 Ctrl + Alt + F12 停止映射',True)
                if not enabled or own or not current[0]:
                    output.release();forward.reset();reverse.reset();armed=False;foreground=None
                    if virtual:virtual.release()
                    message=('编辑时暂停输出，切换到游戏窗口生效' if self._editor else '游戏库内暂停输出，切换到游戏窗口生效') if enabled else ''
                else:
                    if foreground!=current:
                        foreground=current;output.release();forward.reset();reverse.reset();armed=False
                        if virtual:virtual.release()
                    if profile['mode']=='pad_to_keys':
                        neutral=state is not None and not state['buttons'] and all(cfg['mode']=='disabled' or sum(value*value for value in state[stick])<(cfg['deadzone']-.025)**2 for stick,cfg in profile['forward']['sticks'].items())
                        if not state:output.release();forward.reset();armed=False
                        if neutral:armed=True
                        if enabled and armed and state:
                            desired,move=forward.frame(profile,state,dt);output.update(desired,move,now,forward.wheel_steps)
                        message='映射运行中' if armed and state else '等待手柄连接 / 松开按键并回中摇杆'
                    else:
                        held={t for t in configured_keys if transport.held(t)}|pulses
                        if not held and not any(mouse):armed=True
                        if enabled and armed:
                            if virtual is None:
                                virtual=(self._virtual_factory or VirtualPad)();self._virtual_index=virtual.index
                            virtual.update(reverse.frame(profile,held,mouse,dt))
                        message='键鼠→手柄运行中' if armed else '松开绑定键后开始映射'
                if message and message!=previous_message:self.runtimeMessage.emit(message,False);previous_message=message
                clock.wait(.004 if self._editor else .008,self._wake)
        except Exception as error:
            self.runtimeMessage.emit('映射已停止：'+str(error)[:160],True)
        finally:
            output.release()
            if virtual:virtual.close()
            self._virtual_index=-1
            clock.close()

    def shutdown(self):
        self._closed=True;self._enabled=False;self._stop.set();self._wake.set();self._preview_timer.stop();self.cancelCapture()
        if self._raw:self._raw.stop();QCoreApplication.instance().removeNativeEventFilter(self._raw)
        if self._thread:self._thread.join(timeout=3)
        app=QCoreApplication.instance()
        if app:app.removeEventFilter(self)
        self._setup.shutdown()
