"""Keep sibling save slots together without promoting into shared system folders."""
from pathlib import Path
import re

SHARED={'appdata','local','locallow','roaming','documents','my games','saved games','users','steam','userdata'}

def slot_name(name):
    return bool(re.fullmatch(r'(?:backup[_ -]?)?(?:save(?:game|data)?|slot|profile|challenge(?:save)?)[_ -]*\d*',name,re.I))

def complete_directory(path):
    selected=Path(path)
    if not selected.is_dir() or not slot_name(selected.name): return selected
    parent=selected.parent
    if parent.name.casefold() in SHARED or parent==parent.parent: return selected
    try:
        children=list(parent.iterdir())[:200]
        slots=[child for child in children if child.is_dir() and not child.is_symlink() and slot_name(child.name) and not child.name.casefold().startswith('backup')]
        # Slots can be empty; preserve them alongside occupied slots and game backup folders.
        if len(slots)>=2 and any(any(entry.is_file() for entry in child.iterdir()) for child in slots):
            return parent
    except OSError: pass
    return selected
