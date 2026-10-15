#!/usr/bin/env python3
"""
Game Cloud Save - local snapshot + cloud sync helper.

Features:
- Add games and auto-detect save directory.
- Watch game process start/stop and snapshot automatically.
- Manual snapshot while game is running (or anytime), with custom note.
- Upload snapshots to cloud via rclone (supports Baidu Netdisk through rclone remote).
- Snapshot history and restore.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None

APP_NAME = "GameCloudSave"
APP_ROOT = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))) / APP_NAME
DB_PATH = APP_ROOT / "state.db"
DEFAULT_SNAPSHOT_ROOT = APP_ROOT / "snapshots"
CONFIG_PATH = APP_ROOT / "config.json"

SAVE_EXTENSIONS = {
    ".sav",
    ".save",
    ".dat",
    ".json",
    ".xml",
    ".profile",
    ".slot",
    ".bin",
}

AUTO_SNAPSHOT_KEEP = 5
MAX_RECENT_CLOUD = 12


@dataclass
class Game:
    id: int
    name: str
    exe_path: str
    exe_name: str
    save_dir: str
    cloud_remote: str
    cloud_path: str


def now_iso() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def now_file_ts() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "game"


def ensure_dirs() -> None:
    APP_ROOT.mkdir(parents=True, exist_ok=True)
    get_snapshot_root().mkdir(parents=True, exist_ok=True)


def default_config() -> Dict[str, Any]:
    return {
        "default_cloud_remote": "",
        "default_cloud_path": "",
        "snapshot_root": str(DEFAULT_SNAPSHOT_ROOT),
        "recent_cloud_remotes": [],
        "recent_cloud_paths": [],
    }


def connect_db() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=5.0)
    conn.row_factory = sqlite3.Row
    # Improve concurrent read/write responsiveness for GUI + watcher threads.
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def init_db() -> None:
    with closing(connect_db()) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                exe_path TEXT NOT NULL,
                exe_name TEXT NOT NULL,
                save_dir TEXT NOT NULL,
                cloud_remote TEXT NOT NULL DEFAULT '',
                cloud_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                event TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                archive_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                uploaded INTEGER NOT NULL DEFAULT 0,
                cloud_ref TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(game_id) REFERENCES games(id)
            );
            """
        )
        if 'session_key' not in {row[1] for row in conn.execute('PRAGMA table_info(snapshots)')}:
            conn.execute("ALTER TABLE snapshots ADD COLUMN session_key TEXT NOT NULL DEFAULT ''")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS snapshot_session ON snapshots(game_id,session_key) WHERE session_key<>''")
        conn.commit()


def _normalize_recent_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        v = item.strip()
        if v and v not in out:
            out.append(v)
        if len(out) >= MAX_RECENT_CLOUD:
            break
    return out


def load_config() -> Dict[str, Any]:
    APP_ROOT.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        merged = default_config()
        merged.update(cfg)
        merged["recent_cloud_remotes"] = _normalize_recent_list(merged.get("recent_cloud_remotes"))
        merged["recent_cloud_paths"] = _normalize_recent_list(merged.get("recent_cloud_paths"))
        return merged
    return default_config()


def save_config(config: Dict[str, Any]) -> None:
    APP_ROOT.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def update_recent_cloud_history(config: Dict[str, Any], remote: str, path: str) -> None:
    remotes = _normalize_recent_list(config.get("recent_cloud_remotes"))
    paths = _normalize_recent_list(config.get("recent_cloud_paths"))

    remote = remote.strip()
    path = path.strip()

    if remote:
        remotes = [remote] + [x for x in remotes if x != remote]
        remotes = remotes[:MAX_RECENT_CLOUD]
    if path:
        paths = [path] + [x for x in paths if x != path]
        paths = paths[:MAX_RECENT_CLOUD]

    config["recent_cloud_remotes"] = remotes
    config["recent_cloud_paths"] = paths


def record_cloud_input(remote: str, path: str) -> None:
    cfg = load_config()
    update_recent_cloud_history(cfg, remote, path)
    save_config(cfg)


def get_snapshot_root() -> Path:
    cfg = load_config()
    snapshot_root = (cfg.get("snapshot_root") or "").strip()
    if snapshot_root:
        try:
            return Path(snapshot_root).expanduser().resolve()
        except Exception:
            return Path(snapshot_root).expanduser()
    return DEFAULT_SNAPSHOT_ROOT


def canonical_path(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def tokenize_name(name: str) -> List[str]:
    parts = re.split(r"[^a-zA-Z0-9\u4e00-\u9fff]+", name.lower())
    return [p for p in parts if len(p) >= 2]


def score_candidate(path: Path) -> int:
    score = 0
    total_files = 0
    likely_save_files = 0
    max_files = 300
    max_depth = 2

    base_depth = len(path.parts)
    try:
        for root, _, files in os.walk(path):
            current_depth = len(Path(root).parts) - base_depth
            if current_depth > max_depth:
                continue
            for name in files:
                total_files += 1
                if Path(name).suffix.lower() in SAVE_EXTENSIONS:
                    likely_save_files += 1
                if total_files >= max_files:
                    break
            if total_files >= max_files:
                break
    except Exception:
        return score

    score += min(total_files, 200)
    score += likely_save_files * 10
    if any(p.lower() in {"save", "saves", "savegames", "savedata", "profiles"} for p in path.parts):
        score += 50
    return score


def find_save_dir(game_name: str, exe_path: str, timeout_sec: float = 6.0) -> Optional[str]:
    tokens = set(tokenize_name(game_name))
    exe_stem = Path(exe_path).stem.lower()
    tokens.update(tokenize_name(exe_stem))

    user = Path.home()
    roots = [
        user / "Documents",
        user / "Documents" / "My Games",
        user / "Saved Games",
        Path(os.environ.get("APPDATA", str(user / "AppData" / "Roaming"))),
        Path(os.environ.get("LOCALAPPDATA", str(user / "AppData" / "Local"))),
    ]

    candidates: List[Tuple[int, Path]] = []
    start = time.monotonic()
    max_dirs_per_root = 1500
    for root in roots:
        if time.monotonic() - start > timeout_sec:
            break
        if not root.exists():
            continue
        try:
            dirs = [root]
            scanned = 0
            for p in root.rglob("*"):
                if not p.is_dir():
                    continue
                dirs.append(p)
                scanned += 1
                if scanned >= max_dirs_per_root:
                    break
        except Exception:
            continue

        for d in dirs:
            if time.monotonic() - start > timeout_sec:
                break
            rel_depth = len(d.relative_to(root).parts) if d != root else 0
            if rel_depth > 4:
                continue
            name_lower = d.name.lower()
            if tokens and not any(t in name_lower for t in tokens):
                continue
            score = score_candidate(d)
            if score > 0:
                candidates.append((score, d))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    return str(candidates[0][1])


def get_game(conn: sqlite3.Connection, name: str) -> Optional[Game]:
    row = conn.execute("SELECT * FROM games WHERE name = ?", (name,)).fetchone()
    if not row:
        return None
    return Game(
        id=row["id"],
        name=row["name"],
        exe_path=row["exe_path"],
        exe_name=row["exe_name"],
        save_dir=row["save_dir"],
        cloud_remote=row["cloud_remote"],
        cloud_path=row["cloud_path"],
    )


def list_games(conn: sqlite3.Connection) -> List[Game]:
    rows = conn.execute("SELECT * FROM games ORDER BY name").fetchall()
    return [
        Game(
            id=r["id"],
            name=r["name"],
            exe_path=r["exe_path"],
            exe_name=r["exe_name"],
            save_dir=r["save_dir"],
            cloud_remote=r["cloud_remote"],
            cloud_path=r["cloud_path"],
        )
        for r in rows
    ]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def prune_auto_snapshots(conn: sqlite3.Connection, game_id: int, keep: int = AUTO_SNAPSHOT_KEEP) -> None:
    rows = conn.execute(
        """
        SELECT id, archive_path
        FROM snapshots
        WHERE game_id = ? AND event IN ('game_start', 'game_stop')
        ORDER BY id DESC
        """,
        (game_id,),
    ).fetchall()

    for row in rows[keep:]:
        archive = Path(row["archive_path"])
        game_name=conn.execute('SELECT name FROM games WHERE id=?',(game_id,)).fetchone()[0]
        allowed=(get_snapshot_root()/slugify(game_name)).resolve()
        if not archive.resolve().is_relative_to(allowed):continue
        try:
            if archive.exists():
                archive.unlink()
        except OSError:
            continue
        conn.execute("DELETE FROM snapshots WHERE id = ?", (row["id"],))

    conn.commit()


def snapshot_game(conn: sqlite3.Connection, game: Game, event: str, note: str, auto_keep: int = AUTO_SNAPSHOT_KEEP, session_key: str = '') -> Optional[Path]:
    if session_key:
        existing=conn.execute('SELECT archive_path FROM snapshots WHERE game_id=? AND session_key=?',(game.id,session_key)).fetchone()
        if existing and Path(existing['archive_path']).is_file():return Path(existing['archive_path'])
        if existing:raise ValueError('这次自动备份文件已不在本机，请核对保留上限或备份目录')
    save_dir = Path(game.save_dir)
    if not save_dir.exists() or not save_dir.is_dir():
        print(f"[WARN] 存档目录不可用: {save_dir}")
        return None

    game_slug = slugify(game.name)
    target_dir = get_snapshot_root() / game_slug
    target_dir.mkdir(parents=True, exist_ok=True)

    ts = now_file_ts()
    zip_name = f"{ts}__{slugify(event)}.zip"
    zip_path = target_dir / zip_name

    meta = {
        "game": game.name,
        "event": event,
        "note": note,
        "created_at": now_iso(),
        "save_dir": str(save_dir),
    }
    temporary=zip_path.with_suffix('.part')
    try:
        with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED,compresslevel=1 if event in ('game_start','game_stop') else 6) as zipped:
            zipped.writestr('_snapshot_meta.json',json.dumps(meta,ensure_ascii=False))
            zipped.writestr('save/',b'')
            for file in save_dir.rglob('*'):
                if file.is_file():
                    before=file.stat();zipped.write(file,'save/'+file.relative_to(save_dir).as_posix());after=file.stat()
                    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('存档仍在写入，请稍后重试备份')
                elif file.is_dir():zipped.writestr('save/'+file.relative_to(save_dir).as_posix()+'/',b'')
        temporary.replace(zip_path)
    except Exception:
        temporary.unlink(missing_ok=True);raise

    file_hash = sha256_file(zip_path)
    conn.execute(
        """
        INSERT INTO snapshots (game_id, created_at, event, note, archive_path, sha256, uploaded, cloud_ref, session_key)
        VALUES (?, ?, ?, ?, ?, ?, 0, '', ?)
        """,
        (game.id, now_iso(), event, note, str(zip_path), file_hash, session_key),
    )
    conn.commit()

    # Keep only the latest N auto snapshots; manual snapshots are unlimited.
    if event in {"game_start", "game_stop"}:
        prune_auto_snapshots(conn, game.id, keep=auto_keep)

    return zip_path


def upload_snapshot(conn: sqlite3.Connection, game: Game, archive_path: Path) -> bool:
    if not game.cloud_remote or not game.cloud_path:
        return False

    remote_target = f"{game.cloud_remote}:{game.cloud_path.rstrip('/')}/{slugify(game.name)}/{archive_path.name}"

    try:
        subprocess.run(
            ["rclone", "copyto", str(archive_path), remote_target, "--transfers", "1", "--checkers", "2"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        conn.execute(
            "UPDATE snapshots SET uploaded = 1, cloud_ref = ? WHERE archive_path = ?",
            (remote_target, str(archive_path)),
        )
        conn.commit()
        print(f"[CLOUD] 上传成功: {remote_target}")
        return True
    except FileNotFoundError:
        print("[WARN] 未检测到 rclone，请先安装并配置云盘远端。")
    except subprocess.CalledProcessError as e:
        print("[WARN] 上传失败，保留本地快照。")
        print(e.stdout)
    return False


def running_game_map(games: List[Game]) -> Dict[int, bool]:
    result = {g.id: False for g in games}
    if psutil is None:
        return result

    exe_to_game: Dict[str, List[Game]] = {}
    name_to_game: Dict[str, List[Game]] = {}
    for g in games:
        exe_to_game.setdefault(g.exe_path.lower(), []).append(g)
        name_to_game.setdefault(g.exe_name.lower(), []).append(g)

    for proc in psutil.process_iter(["name", "exe"]):
        try:
            pexe = (proc.info.get("exe") or "").lower()
            pname = (proc.info.get("name") or "").lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        if pexe in exe_to_game:
            for g in exe_to_game[pexe]:
                result[g.id] = True
        if pname in name_to_game:
            for g in name_to_game[pname]:
                result[g.id] = True
    return result


def cmd_init(_: argparse.Namespace) -> None:
    init_db()
    ensure_dirs()
    cfg = load_config()
    save_config(cfg)
    print(f"初始化完成: {APP_ROOT}")


def cmd_config_cloud(args: argparse.Namespace) -> None:
    init_db()
    cfg = load_config()
    cfg["default_cloud_remote"] = args.remote
    cfg["default_cloud_path"] = args.path
    update_recent_cloud_history(cfg, args.remote, args.path)
    save_config(cfg)
    print("默认云端配置已保存。")


def cmd_config_snapshot(args: argparse.Namespace) -> None:
    init_db()
    cfg = load_config()
    snapshot_root = canonical_path(args.path)
    Path(snapshot_root).mkdir(parents=True, exist_ok=True)
    cfg["snapshot_root"] = snapshot_root
    save_config(cfg)
    print(f"快照目录已设置: {snapshot_root}")


def cmd_add(args: argparse.Namespace) -> None:
    init_db()
    exe = canonical_path(args.exe)
    if not Path(exe).exists():
        print(f"[ERROR] 游戏可执行文件不存在: {exe}")
        return

    save_dir = canonical_path(args.save_dir) if args.save_dir else find_save_dir(args.name, exe)
    if not save_dir:
        print("[WARN] 自动识别存档目录失败，请使用 --save-dir 手动添加。")
        return

    cfg = load_config()
    cloud_remote = args.cloud_remote if args.cloud_remote is not None else cfg.get("default_cloud_remote", "")
    cloud_path = args.cloud_path if args.cloud_path is not None else cfg.get("default_cloud_path", "")

    with connect_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO games (name, exe_path, exe_name, save_dir, cloud_remote, cloud_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM games WHERE name=?), ?), ?)
            """,
            (
                args.name,
                exe,
                Path(exe).name,
                save_dir,
                cloud_remote,
                cloud_path,
                args.name,
                now_iso(),
                now_iso(),
            ),
        )
        conn.commit()

    print(f"已添加游戏: {args.name}")
    print(f"- EXE: {exe}")
    print(f"- Save: {save_dir}")
    if cloud_remote and cloud_path:
        print(f"- Cloud: {cloud_remote}:{cloud_path}")


def cmd_set_save(args: argparse.Namespace) -> None:
    init_db()
    save_dir = canonical_path(args.save_dir)
    if not Path(save_dir).exists():
        print(f"[ERROR] 存档目录不存在: {save_dir}")
        return

    with connect_db() as conn:
        game = get_game(conn, args.name)
        if not game:
            print("[ERROR] 游戏未找到，请先 add。")
            return
        conn.execute(
            "UPDATE games SET save_dir=?, updated_at=? WHERE id=?",
            (save_dir, now_iso(), game.id),
        )
        conn.commit()

    print(f"已更新存档目录: {args.name} -> {save_dir}")


def cmd_set_cloud(args: argparse.Namespace) -> None:
    init_db()
    with connect_db() as conn:
        game = get_game(conn, args.name)
        if not game:
            print("[ERROR] 游戏未找到，请先 add。")
            return
        conn.execute(
            "UPDATE games SET cloud_remote=?, cloud_path=?, updated_at=? WHERE id=?",
            (args.remote, args.path, now_iso(), game.id),
        )
        conn.commit()
    print(f"已更新云端配置: {args.name} -> {args.remote}:{args.path}")


def cmd_list(_: argparse.Namespace) -> None:
    init_db()
    with connect_db() as conn:
        games = list_games(conn)
    if not games:
        print("暂无游戏。")
        return

    for g in games:
        cloud = f"{g.cloud_remote}:{g.cloud_path}" if g.cloud_remote and g.cloud_path else "(未配置)"
        print(f"- {g.name}")
        print(f"  exe: {g.exe_path}")
        print(f"  save: {g.save_dir}")
        print(f"  cloud: {cloud}")


def cmd_watch(args: argparse.Namespace) -> None:
    init_db()
    if psutil is None:
        print("[ERROR] 需要安装 psutil: pip install psutil")
        return

    with connect_db() as conn:
        games = list_games(conn)

    if not games:
        print("[ERROR] 没有游戏，先执行 add。")
        return

    print("开始监听游戏进程。按 Ctrl+C 退出。")
    states = running_game_map(games)

    try:
        while True:
            time.sleep(max(1, args.interval))
            with connect_db() as conn:
                games = list_games(conn)
                current = running_game_map(games)
                for g in games:
                    old = states.get(g.id, False)
                    new = current.get(g.id, False)
                    if not old and new:
                        print(f"[EVENT] {g.name} 启动")
                        archive = snapshot_game(conn, g, event="game_start", note="自动: 启动前备份")
                        if archive:
                            upload_snapshot(conn, g, archive)
                    elif old and not new:
                        print(f"[EVENT] {g.name} 退出")
                        archive = snapshot_game(conn, g, event="game_stop", note="自动: 退出后备份")
                        if archive:
                            upload_snapshot(conn, g, archive)
                states = current
    except KeyboardInterrupt:
        print("已停止监听。")


def cmd_save(args: argparse.Namespace) -> None:
    init_db()
    with connect_db() as conn:
        game = get_game(conn, args.name)
        if not game:
            print("[ERROR] 游戏未找到，请先 add。")
            return
        note = args.note or "手动快照"
        archive = snapshot_game(conn, game, event="manual", note=note)
        if archive:
            print(f"[OK] 快照完成: {archive}")
            upload_snapshot(conn, game, archive)


def cmd_history(args: argparse.Namespace) -> None:
    init_db()
    with connect_db() as conn:
        game = get_game(conn, args.name)
        if not game:
            print("[ERROR] 游戏未找到，请先 add。")
            return

        rows = conn.execute(
            """
            SELECT id, created_at, event, note, uploaded, archive_path
            FROM snapshots
            WHERE game_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (game.id, args.limit),
        ).fetchall()

    if not rows:
        print("暂无快照。")
        return

    for r in rows:
        up = "yes" if r["uploaded"] else "no"
        print(f"#{r['id']} {r['created_at']} [{r['event']}] uploaded={up}")
        if r["note"]:
            print(f"  note: {r['note']}")
        print(f"  file: {r['archive_path']}")


def cmd_restore(args: argparse.Namespace) -> None:
    init_db()
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT s.archive_path, g.save_dir, g.name
            FROM snapshots s
            JOIN games g ON g.id=s.game_id
            WHERE s.id=?
            """,
            (args.snapshot_id,),
        ).fetchone()

    if not row:
        print("[ERROR] 快照不存在。")
        return

    archive = Path(row["archive_path"])
    save_dir = Path(row["save_dir"])

    if not archive.exists():
        print(f"[ERROR] 快照文件不存在: {archive}")
        return

    backup_dir = save_dir.parent / f"{save_dir.name}.before-restore.{now_file_ts()}"
    if save_dir.exists():
        shutil.copytree(save_dir, backup_dir, dirs_exist_ok=True)
        print(f"已备份当前存档到: {backup_dir}")

    extract_tmp = save_dir.parent / f"{save_dir.name}.restore-tmp.{now_file_ts()}"
    extract_tmp.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(str(archive), str(extract_tmp))

    restored = extract_tmp / "save"
    if not restored.exists():
        shutil.rmtree(extract_tmp, ignore_errors=True)
        print("[ERROR] 快照格式异常，缺少 save 目录。")
        return

    if save_dir.exists():
        shutil.rmtree(save_dir, ignore_errors=True)
    shutil.copytree(restored, save_dir, dirs_exist_ok=True)
    shutil.rmtree(extract_tmp, ignore_errors=True)

    print(f"[OK] 已恢复快照 #{args.snapshot_id} 到 {save_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gamecloud", description="Local game save snapshots + cloud sync")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="初始化数据库和目录")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("config-cloud", help="设置默认云端配置")
    p.add_argument("--remote", required=True, help="rclone remote 名称，例如 baidu")
    p.add_argument("--path", required=True, help="云端目录，例如 game-saves")
    p.set_defaults(func=cmd_config_cloud)

    p = sub.add_parser("config-snapshot", help="设置快照保存目录")
    p.add_argument("--path", required=True, help="本地快照目录，例如 D:\\GameCloudSaveSnapshots")
    p.set_defaults(func=cmd_config_snapshot)

    p = sub.add_parser("add", help="添加游戏")
    p.add_argument("name", help="游戏名称")
    p.add_argument("--exe", required=True, help="游戏 exe 路径")
    p.add_argument("--save-dir", help="存档目录，留空自动识别")
    p.add_argument("--cloud-remote", help="rclone remote，留空用默认")
    p.add_argument("--cloud-path", help="云端目录，留空用默认")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("set-save", help="手动更新存档目录")
    p.add_argument("name")
    p.add_argument("save_dir")
    p.set_defaults(func=cmd_set_save)

    p = sub.add_parser("set-cloud", help="设置某个游戏的云端配置")
    p.add_argument("name")
    p.add_argument("--remote", required=True)
    p.add_argument("--path", required=True)
    p.set_defaults(func=cmd_set_cloud)

    p = sub.add_parser("list", help="列出游戏")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("watch", help="监听游戏进程自动备份")
    p.add_argument("--interval", type=int, default=3, help="轮询间隔秒")
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("save", help="手动打点快照")
    p.add_argument("name")
    p.add_argument("--note", default="", help="自定义备注")
    p.set_defaults(func=cmd_save)

    p = sub.add_parser("history", help="查看快照历史")
    p.add_argument("name")
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_history)

    p = sub.add_parser("restore", help="恢复某个快照")
    p.add_argument("snapshot_id", type=int)
    p.set_defaults(func=cmd_restore)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
