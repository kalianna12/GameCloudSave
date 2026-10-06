"""Exercise the unchanged core using only workspace-owned disposable data."""
import importlib.util
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
import sys
import gc
from contextlib import closing

workspace = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gamecloud", workspace / "legacy/gamecloud.py")
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

with tempfile.TemporaryDirectory(dir=workspace / "test-data") as temporary:
    root = Path(temporary)
    core.APP_ROOT = root / "app"
    core.DB_PATH = core.APP_ROOT / "state.db"
    core.CONFIG_PATH = core.APP_ROOT / "config.json"
    core.DEFAULT_SNAPSHOT_ROOT = core.APP_ROOT / "snapshots"
    save = root / "中文游戏存档"
    save.mkdir()
    original = {"进度": 42}
    (save / "save.json").write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")
    core.ensure_dirs()
    core.init_db()
    gc.collect()
    game = core.Game(1, "中文游戏测试", str(root / "game.exe"), "game.exe", str(save), "alist", "test")
    with closing(core.connect_db()) as conn:
        archive = core.snapshot_game(conn, game, "manual", "隔离验证")
        assert archive and archive.is_file()
        with zipfile.ZipFile(archive) as zipped:
            assert any(name.endswith("save.json") for name in zipped.namelist())
        with patch.object(core.subprocess, "run", side_effect=FileNotFoundError("isolated")):
            assert core.upload_snapshot(conn, game, archive) is False
        assert archive.is_file(), "Failed upload must retain local snapshot"
        assert conn.execute("SELECT uploaded FROM snapshots").fetchone()[0] == 0
    print("PASS: Chinese name, local ZIP, failed upload retains archive; no real cloud request")
