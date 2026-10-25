"""Remove Qt modules not imported by the shipped QML, only in the build output."""
from pathlib import Path
import json,shutil
ROOT=Path(__file__).resolve().parents[1]
program=(ROOT/'dist/GameCloudSave').resolve();runtime=(program/'_internal/PySide6').resolve()
assert program.parent==ROOT/'dist' and runtime.is_relative_to(program) and runtime.is_dir()
targets=[runtime/'qml/QtWebEngine',runtime/'qml/QtQuick/Pdf',runtime/'qml/QtQuick3D',runtime/'qml/Qt3D',runtime/'plugins/imageformats/qpdf.dll']
targets.extend(p for p in runtime.iterdir() if p.name.startswith(('Qt6WebEngine','Qt6Pdf','Qt6Quick3D','Qt6Quick3D','Qt6Quick3DUtils','Qt6Quick3DAssetImport','Qt3D','Qt6Designer','Qt6Help')))
removed=[]
for path in targets:
    if not path.exists():continue
    assert path.resolve().is_relative_to(runtime) and not path.is_symlink()
    size=sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) if path.is_dir() else path.stat().st_size
    removed.append({'path':str(path.relative_to(program)),'bytes':size})
    if path.is_dir():shutil.rmtree(path)
    else:path.unlink()
(ROOT/'build/runtime-pruned.json').write_text(json.dumps(removed,indent=2),encoding='utf-8')
print('Pruned unused runtime:',round(sum(r['bytes'] for r in removed)/1048576,1),'MiB')
