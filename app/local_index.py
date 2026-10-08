"""Small TTL directory index. Never enumerate file contents or follow directory links."""
from collections import deque
from itertools import islice
from pathlib import Path
import os,time,threading

_cache={};_locks={};_lock=threading.Lock()
SKIP={'cache','caches','temp','tmp','node_modules','.git','logs','crashdumps','webcache','gpucache','code cache','browsermetrics'}

def directories(root,depth=3,budget=6000,seconds=2,cancel=None):
    root=Path(root).resolve();key=(str(root).casefold(),depth,budget)
    with _lock: guard=_locks.setdefault(key,threading.Lock())
    with guard:
        cached=_cache.get(key)
        if cached and time.monotonic()-cached[0]<30:return cached[1]
        deadline=time.monotonic()+seconds;queue=deque([(root,0)]);found=[]
        while queue and len(found)<budget and time.monotonic()<deadline:
            if cancel and cancel.is_set():break
            parent,level=queue.popleft()
            try:
                with os.scandir(parent) as entries:
                    for entry in islice(entries,1500):
                        if cancel and cancel.is_set():break
                        if time.monotonic()>=deadline or len(found)>=budget:break
                        if entry.name.casefold() in SKIP or '.before-restore.' in entry.name or not entry.is_dir(follow_symlinks=False):continue
                        path=Path(entry.path)
                        # Reject junctions escaping the root too.
                        if not path.resolve().is_relative_to(root):continue
                        found.append(path)
                        if level+1<depth:queue.append((path,level+1))
            except OSError:continue
        if not cancel or not cancel.is_set():_cache[key]=(time.monotonic(),tuple(found))
        return tuple(found)

def clear():
    with _lock:_cache.clear()
