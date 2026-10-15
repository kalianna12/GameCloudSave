"""Lightweight process sampling, exit debouncing and a durable once-per-session queue."""
from contextlib import contextmanager
from pathlib import Path
import ctypes,ntpath,os,threading,time,uuid

def normalized(value):return ntpath.normcase(ntpath.normpath(str(value)))

@contextmanager
def background_work():
    """Lower this worker's CPU/I/O priority; never change a game's process priority."""
    active=False
    if os.name=='nt':
        kernel=ctypes.windll.kernel32
        kernel.GetCurrentThread.restype=ctypes.c_void_p
        kernel.SetThreadPriority.argtypes=[ctypes.c_void_p,ctypes.c_int]
        handle=kernel.GetCurrentThread()
        active=bool(kernel.SetThreadPriority(handle,0x10000))
    try:yield
    finally:
        if active:kernel.SetThreadPriority(handle,0x20000)

class ProcessSampler:
    def __init__(self):self.config={};self.cache={}
    def targets(self,games,local):
        result={}
        for game in games:
            ident=game['id'];item=local.get(ident,{})
            if not item.get('save_dir'):continue
            signature=tuple(item.get(key,'') for key in ('monitor_exe','exe','install_dir','save_dir'))
            if self.config.get(ident,{}).get('signature')!=signature:
                explicit=item.get('monitor_exe','');exe=explicit or item.get('exe','');root=item.get('install_dir','')
                names=set();paths=set()
                if ntpath.splitext(exe)[1].casefold()=='.exe':names.add(ntpath.basename(exe).casefold());paths.add(normalized(exe))
                # Discover real shipping executables once per configuration, never on every tick.
                if not explicit and root and Path(root).is_dir():
                    from itertools import islice
                    folders=[Path(root),*[Path(root)/part for part in ('Game','bin','bin/x64','x64','Binaries/Win64','Binaries/Win32')]]
                    folders.extend(islice(Path(root).glob('*/Binaries/Win64'),12))
                    for folder in folders:
                        if not folder.is_dir():continue
                        for file in islice(folder.glob('*.exe'),128):
                            if any(word in file.stem.casefold() for word in ('unins','setup','crash','redist','installer','launcher','easyanticheat','start_protected')):continue
                            names.add(file.name.casefold());paths.add(normalized(file))
                self.config[ident]={'signature':signature,'names':names,'paths':paths,'explicit':bool(explicit)}
            if self.config[ident]['names']:result[ident]=self.config[ident]
        return result
    def sample(self,targets):
        import psutil
        names=set().union(*(target['names'] for target in targets.values())) if targets else set()
        states={ident:False for ident in targets};seen=set()
        # Query paths only for candidate names, not for every Windows process.
        for process in psutil.process_iter(['pid','name']):
            name=(process.info.get('name') or '').casefold()
            if name not in names:continue
            pid=process.info.get('pid');seen.add(pid)
            try:
                created=process.create_time() if hasattr(process,'create_time') else 0
                key=(pid,created,name)
                path=self.cache.get(key)
                if path is None:
                    path=process.info.get('exe') or (process.exe() if hasattr(process,'exe') else '')
                    path=normalized(path) if path else ''
                    if path:self.cache[key]=path
            except psutil.NoSuchProcess:continue
            except (psutil.AccessDenied,OSError):path=''
            eligible=[ident for ident,target in targets.items() if name in target['names']]
            for ident in eligible:
                if path in targets[ident]['paths']:states[ident]=True
                elif not path and len(eligible)==1 and targets[ident]['explicit']:states[ident]=True
                elif not path and states[ident] is not True:states[ident]=None
        self.cache={key:value for key,value in self.cache.items() if key[0] in seen}
        return states

class Sessions:
    def __init__(self,delay=3):self.active={};self.missing={};self.delay=delay
    def update(self,states,now=None):
        now=time.monotonic() if now is None else now;started=[];ended=[]
        for ident in list(self.active):
            if ident not in states:self.active.pop(ident,None);self.missing.pop(ident,None)
        for ident,running in states.items():
            if running is None:continue
            if running:
                self.missing.pop(ident,None)
                if ident not in self.active:
                    self.active[ident]={'ident':ident,'token':uuid.uuid4().hex};started.append(ident)
            elif ident in self.active:
                if ident not in self.missing:self.missing[ident]=now
                elif now-self.missing[ident]>=self.delay:
                    ended.append(self.active.pop(ident));self.missing.pop(ident,None)
        return started,ended

class ExitQueue:
    def __init__(self,path):
        from services import read_json
        self.path=path;self.lock=threading.RLock();self.rows=read_json(path,[])
    def save(self):
        from services import write_json
        write_json(self.path,self.rows)
    def add(self,session,count_play=True):
        with self.lock:
            if any(row['token']==session['token'] for row in self.rows):return
            self.rows.append({**session,'phase':'pending','archive':'','count_play':count_play});self.save()
    def update(self,token,**values):
        with self.lock:
            for row in self.rows:
                if row['token']==token:row.update(values);break
            self.save()
    def next(self):
        with self.lock:return next((dict(row) for row in self.rows if row['phase'] in ('pending','saved')),None)
    def finish(self,token):
        with self.lock:self.rows=[row for row in self.rows if row['token']!=token];self.save()
    def discard_pruned(self,ident,archives):
        with self.lock:
            self.rows=[row for row in self.rows if row['ident']!=ident or not row.get('archive') or row['archive'] in archives]
            self.save()
    def retry(self):
        with self.lock:
            for row in self.rows:
                if row['phase'] in ('backup_failed','upload_failed'):row['phase']='saved' if row.get('archive') else 'pending'
            self.save()
    def counts(self):
        with self.lock:return {'queued':sum(row['phase'] in ('pending','saved') for row in self.rows),'failed':sum(row['phase'].endswith('failed') for row in self.rows)}
