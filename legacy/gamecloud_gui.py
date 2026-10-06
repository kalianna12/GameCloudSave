#!/usr/bin/env python3
from __future__ import annotations

import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from pathlib import Path
import os
import subprocess

import gamecloud as core


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: tk.Toplevel | None = None
        self.widget.bind("<Enter>", self.show)
        self.widget.bind("<Leave>", self.hide)

    def show(self, _event=None) -> None:
        if self.tip_window is not None:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#fffbe6",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=4,
        )
        label.pack()

    def hide(self, _event=None) -> None:
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class GameCloudGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("GameCloudSave GUI")
        self.geometry("1080x700")
        self.minsize(960, 620)

        core.init_db()
        self.watch_thread: threading.Thread | None = None
        self.watch_stop = threading.Event()

        self._build_ui()
        self.refresh_games()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=1)

        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        for i in range(12):
            top.columnconfigure(i, weight=0)
        top.columnconfigure(11, weight=1)

        btn_refresh = ttk.Button(top, text="刷新", command=self.refresh_games)
        btn_add = ttk.Button(top, text="添加游戏", command=self.add_game_dialog)
        btn_set_save = ttk.Button(top, text="改存档目录", command=self.set_save_dir_dialog)
        btn_set_cloud = ttk.Button(top, text="配云端", command=self.set_cloud_dialog)
        btn_open_snapshot_root = ttk.Button(top, text="打开快照目录", command=self.open_snapshot_root)
        btn_snapshot_root = ttk.Button(top, text="更改快照目录", command=self.set_snapshot_root_dialog)
        btn_manual = ttk.Button(top, text="手动存档", command=self.manual_snapshot_dialog)
        btn_restore = ttk.Button(top, text="恢复选中快照", command=self.restore_selected_snapshot)
        btn_launch = ttk.Button(top, text="启动游戏", command=self.launch_selected_game)
        btn_watch = ttk.Button(top, text="启动监听", command=self.start_watch)
        btn_stop = ttk.Button(top, text="停止监听", command=self.stop_watch)

        btn_refresh.grid(row=0, column=0, padx=4)
        btn_add.grid(row=0, column=1, padx=4)
        btn_set_save.grid(row=0, column=2, padx=4)
        btn_set_cloud.grid(row=0, column=3, padx=4)
        btn_open_snapshot_root.grid(row=0, column=4, padx=4)
        btn_snapshot_root.grid(row=0, column=5, padx=4)
        btn_manual.grid(row=0, column=6, padx=4)
        btn_restore.grid(row=0, column=7, padx=4)
        btn_launch.grid(row=0, column=8, padx=4)
        btn_watch.grid(row=0, column=9, padx=4)
        btn_stop.grid(row=0, column=10, padx=4)

        ToolTip(btn_refresh, "重新加载游戏列表和快照历史。")
        ToolTip(btn_add, "添加游戏：选择 EXE 后手动选择存档目录。")
        ToolTip(btn_set_save, "修改当前选中游戏的存档目录。")
        ToolTip(btn_set_cloud, "设置当前选中游戏的云端 remote/path。")
        ToolTip(btn_open_snapshot_root, "在资源管理器中打开快照目录。")
        ToolTip(btn_snapshot_root, "设置快照 zip 文件保存到哪个本地目录。")
        ToolTip(btn_manual, "立即创建一次手动快照，可写备注。")
        ToolTip(btn_restore, "恢复你在历史里选中的快照记录。")
        ToolTip(btn_launch, "启动当前选中游戏。")
        ToolTip(btn_watch, "开始监听游戏进程，启动/退出自动存档。")
        ToolTip(btn_stop, "停止后台进程监听。")

        self.watch_status = tk.StringVar(value="监听状态: 未启动")
        ttk.Label(top, textvariable=self.watch_status).grid(row=0, column=11, sticky="e")

        mid = ttk.LabelFrame(self, text="游戏列表", padding=8)
        mid.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(0, weight=1)

        self.game_tree = ttk.Treeview(
            mid,
            columns=("name", "exe", "save", "cloud"),
            show="headings",
            height=10,
        )
        self.game_tree.heading("name", text="游戏")
        self.game_tree.heading("exe", text="EXE")
        self.game_tree.heading("save", text="存档目录")
        self.game_tree.heading("cloud", text="云端")
        self.game_tree.column("name", width=160, anchor="w")
        self.game_tree.column("exe", width=300, anchor="w")
        self.game_tree.column("save", width=350, anchor="w")
        self.game_tree.column("cloud", width=220, anchor="w")
        self.game_tree.grid(row=0, column=0, sticky="nsew")
        self.game_tree.bind("<<TreeviewSelect>>", lambda _: self.refresh_history())

        game_scroll = ttk.Scrollbar(mid, orient="vertical", command=self.game_tree.yview)
        self.game_tree.configure(yscrollcommand=game_scroll.set)
        game_scroll.grid(row=0, column=1, sticky="ns")

        bottom = ttk.LabelFrame(self, text="快照历史", padding=8)
        bottom.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        bottom.columnconfigure(0, weight=1)
        bottom.rowconfigure(0, weight=1)

        self.snap_tree = ttk.Treeview(
            bottom,
            columns=("id", "time", "event", "uploaded", "note", "file"),
            show="headings",
            height=12,
        )
        self.snap_tree.heading("id", text="ID")
        self.snap_tree.heading("time", text="时间")
        self.snap_tree.heading("event", text="事件")
        self.snap_tree.heading("uploaded", text="已上传")
        self.snap_tree.heading("note", text="备注")
        self.snap_tree.heading("file", text="快照文件")
        self.snap_tree.column("id", width=60, anchor="center")
        self.snap_tree.column("time", width=160, anchor="w")
        self.snap_tree.column("event", width=120, anchor="w")
        self.snap_tree.column("uploaded", width=80, anchor="center")
        self.snap_tree.column("note", width=260, anchor="w")
        self.snap_tree.column("file", width=360, anchor="w")
        self.snap_tree.grid(row=0, column=0, sticky="nsew")

        snap_scroll = ttk.Scrollbar(bottom, orient="vertical", command=self.snap_tree.yview)
        self.snap_tree.configure(yscrollcommand=snap_scroll.set)
        snap_scroll.grid(row=0, column=1, sticky="ns")

        log_frame = ttk.LabelFrame(self, text="日志", padding=8)
        log_frame.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=8)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.grid(row=0, column=1, sticky="ns")

    def log(self, msg: str) -> None:
        self.log_text.insert("end", f"{core.now_iso()}  {msg}\n")
        self.log_text.see("end")

    def log_async(self, msg: str) -> None:
        self.after(0, lambda: self.log(msg))

    def _run_bg(self, work, on_done=None) -> None:
        def runner() -> None:
            try:
                work()
            finally:
                if on_done is not None:
                    self.after(0, on_done)
        threading.Thread(target=runner, daemon=True).start()

    def _selected_game_name(self) -> str | None:
        item = self.game_tree.selection()
        if not item:
            return None
        return self.game_tree.item(item[0], "values")[0]

    def refresh_games(self) -> None:
        for i in self.game_tree.get_children():
            self.game_tree.delete(i)

        with core.connect_db() as conn:
            games = core.list_games(conn)

        for g in games:
            cloud = f"{g.cloud_remote}:{g.cloud_path}" if g.cloud_remote and g.cloud_path else "(未配置)"
            self.game_tree.insert("", "end", values=(g.name, g.exe_path, g.save_dir, cloud))

        self.refresh_history()
        self.log(f"已刷新游戏列表（快照目录: {core.get_snapshot_root()}）")

    def refresh_history(self) -> None:
        for i in self.snap_tree.get_children():
            self.snap_tree.delete(i)

        name = self._selected_game_name()
        if not name:
            return

        with core.connect_db() as conn:
            game = core.get_game(conn, name)
            if not game:
                return
            rows = conn.execute(
                """
                SELECT id, created_at, event, uploaded, note, archive_path
                FROM snapshots
                WHERE game_id=?
                ORDER BY id DESC
                LIMIT 100
                """,
                (game.id,),
            ).fetchall()

        for r in rows:
            self.snap_tree.insert(
                "",
                "end",
                values=(
                    r["id"],
                    r["created_at"],
                    r["event"],
                    "yes" if r["uploaded"] else "no",
                    r["note"],
                    r["archive_path"],
                ),
            )

    def add_game_dialog(self) -> None:
        name = simpledialog.askstring("添加游戏", "游戏名称：", parent=self)
        if not name:
            return

        exe = filedialog.askopenfilename(
            title="选择游戏 EXE",
            filetypes=[("EXE", "*.exe"), ("All files", "*.*")],
            parent=self,
        )
        if not exe:
            return

        # Default to manual selection to avoid long auto-detection pauses.
        save_dir = filedialog.askdirectory(title="选择存档目录（手动）", parent=self)
        if not save_dir:
            try_auto = messagebox.askyesno("未选择目录", "未选择存档目录，是否尝试自动识别？（最多等待 5 秒）", parent=self)
            if try_auto:
                guessed, completed = self._detect_save_dir_with_timeout(name, exe, timeout_sec=5.0)
                if completed and guessed:
                    use_guess = messagebox.askyesno("存档目录", f"自动识别到存档目录：\n{guessed}\n\n是否使用？", parent=self)
                    save_dir = guessed if use_guess else ""
                elif not completed:
                    messagebox.showinfo("提示", "自动识别超时，请重新手动选择存档目录。", parent=self)

        if not save_dir:
            messagebox.showwarning("取消", "未设置存档目录，添加已取消。")
            return

        with core.connect_db() as conn:
            cfg = core.load_config()
            conn.execute(
                """
                INSERT OR REPLACE INTO games (name, exe_path, exe_name, save_dir, cloud_remote, cloud_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT created_at FROM games WHERE name=?), ?), ?)
                """,
                (
                    name,
                    core.canonical_path(exe),
                    Path(exe).name,
                    core.canonical_path(save_dir),
                    cfg.get("default_cloud_remote", ""),
                    cfg.get("default_cloud_path", ""),
                    name,
                    core.now_iso(),
                    core.now_iso(),
                ),
            )
            conn.commit()

        self.refresh_games()
        self.log(f"已添加游戏: {name}")

    def _detect_save_dir_with_timeout(self, name: str, exe: str, timeout_sec: float = 5.0) -> tuple[str | None, bool]:
        result: dict[str, str | None | bool] = {"value": None, "done": False}

        def worker() -> None:
            result["value"] = core.find_save_dir(name, exe, timeout_sec=timeout_sec)
            result["done"] = True

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        start = time.time()
        while time.time() - start < timeout_sec:
            if bool(result["done"]):
                return (result["value"] if isinstance(result["value"], str) else None, True)
            self.update_idletasks()
            self.update()
            time.sleep(0.05)
        return (None, False)

    def set_save_dir_dialog(self) -> None:
        name = self._selected_game_name()
        if not name:
            messagebox.showinfo("提示", "请先在游戏列表选择一项。")
            return
        save_dir = filedialog.askdirectory(title=f"为 {name} 选择存档目录", parent=self)
        if not save_dir:
            return

        with core.connect_db() as conn:
            game = core.get_game(conn, name)
            if not game:
                return
            conn.execute("UPDATE games SET save_dir=?, updated_at=? WHERE id=?", (core.canonical_path(save_dir), core.now_iso(), game.id))
            conn.commit()

        self.refresh_games()
        self.log(f"已更新存档目录: {name}")

    def set_cloud_dialog(self) -> None:
        name = self._selected_game_name()
        if not name:
            messagebox.showinfo("提示", "请先在游戏列表选择一项。")
            return

        with core.connect_db() as conn:
            game = core.get_game(conn, name)
            if not game:
                return

        cfg = core.load_config()
        recent_remotes = cfg.get("recent_cloud_remotes", [])
        recent_paths = cfg.get("recent_cloud_paths", [])
        remote, path = self._cloud_picker_dialog(
            game_name=name,
            current_remote=game.cloud_remote,
            current_path=game.cloud_path,
            recent_remotes=recent_remotes if isinstance(recent_remotes, list) else [],
            recent_paths=recent_paths if isinstance(recent_paths, list) else [],
        )
        if remote is None or path is None:
            return

        remote = remote.strip()
        path = path.strip()
        if not remote or not path:
            messagebox.showwarning("提示", "remote 和 path 不能为空。")
            return

        with core.connect_db() as conn:
            game = core.get_game(conn, name)
            if not game:
                return
            conn.execute(
                "UPDATE games SET cloud_remote=?, cloud_path=?, updated_at=? WHERE id=?",
                (remote, path, core.now_iso(), game.id),
            )
            conn.commit()

        core.record_cloud_input(remote, path)
        self.refresh_games()
        self.log(f"已更新云端配置: {name} -> {remote}:{path}")

    def _cloud_picker_dialog(
        self,
        game_name: str,
        current_remote: str,
        current_path: str,
        recent_remotes: list[str],
        recent_paths: list[str],
    ) -> tuple[str | None, str | None]:
        dlg = tk.Toplevel(self)
        dlg.title(f"云端配置 - {game_name}")
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)

        frame = ttk.Frame(dlg, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="remote：").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        ttk.Label(frame, text="path：").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))

        remote_values = []
        for v in [current_remote, *recent_remotes]:
            if isinstance(v, str) and v and v not in remote_values:
                remote_values.append(v)
        path_values = []
        for v in [current_path, *recent_paths]:
            if isinstance(v, str) and v and v not in path_values:
                path_values.append(v)

        remote_var = tk.StringVar(value=current_remote or (remote_values[0] if remote_values else ""))
        path_var = tk.StringVar(value=current_path or (path_values[0] if path_values else ""))

        cb_remote = ttk.Combobox(frame, textvariable=remote_var, values=remote_values, width=42)
        cb_path = ttk.Combobox(frame, textvariable=path_var, values=path_values, width=42)
        cb_remote.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        cb_path.grid(row=1, column=1, sticky="ew", pady=(0, 8))

        hint = ttk.Label(frame, text="可直接输入，也可从下拉选择最近内容。")
        hint.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 10))

        result: dict[str, str | None] = {"remote": None, "path": None}

        def on_ok() -> None:
            result["remote"] = remote_var.get().strip()
            result["path"] = path_var.get().strip()
            dlg.destroy()

        def on_cancel() -> None:
            dlg.destroy()

        btns = ttk.Frame(frame)
        btns.grid(row=3, column=0, columnspan=2, sticky="e")
        ttk.Button(btns, text="取消", command=on_cancel).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="保存", command=on_ok).grid(row=0, column=1)

        dlg.bind("<Return>", lambda _: on_ok())
        dlg.bind("<Escape>", lambda _: on_cancel())
        cb_remote.focus_set()

        self.wait_window(dlg)
        return (result["remote"], result["path"])

    def set_snapshot_root_dialog(self) -> None:
        cfg = core.load_config()
        current = cfg.get("snapshot_root", "")
        selected = filedialog.askdirectory(title="选择快照保存目录", initialdir=current or "D:\\", parent=self)
        if not selected:
            return
        selected = core.canonical_path(selected)
        cfg["snapshot_root"] = selected
        core.save_config(cfg)
        core.ensure_dirs()
        self.log(f"已设置快照目录: {selected}")

    def open_snapshot_root(self) -> None:
        path = core.get_snapshot_root()
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))
        self.log(f"已打开快照目录: {path}")

    def manual_snapshot_dialog(self) -> None:
        name = self._selected_game_name()
        if not name:
            messagebox.showinfo("提示", "请先在游戏列表选择一项。")
            return

        note = simpledialog.askstring("手动存档", "输入备注（可空）：", parent=self) or ""
        self.log(f"开始手动快照: {name}")

        def work() -> None:
            with core.connect_db() as conn:
                game = core.get_game(conn, name)
                if not game:
                    self.log_async("手动快照失败：未找到游戏配置。")
                    return
                archive = core.snapshot_game(conn, game, event="manual", note=note or "手动快照")
                if archive:
                    self.log_async(f"手动快照完成: {archive}")
                    core.upload_snapshot(conn, game, archive)
                else:
                    self.log_async("手动快照失败：存档目录不可用。")

        self._run_bg(work, on_done=self.refresh_history)

    def launch_selected_game(self) -> None:
        name = self._selected_game_name()
        if not name:
            messagebox.showinfo("提示", "请先在游戏列表选择一项。")
            return

        with core.connect_db() as conn:
            game = core.get_game(conn, name)
            if not game:
                messagebox.showerror("错误", "未找到该游戏配置。")
                return

        exe_path = Path(game.exe_path)
        if not exe_path.exists():
            messagebox.showerror("错误", f"游戏 EXE 不存在：\n{exe_path}")
            return

        try:
            subprocess.Popen([str(exe_path)], cwd=str(exe_path.parent))
            self.log(f"已启动游戏: {game.name} ({exe_path})")
        except Exception as e:
            messagebox.showerror("启动失败", f"无法启动游戏：\n{e}")

    def restore_selected_snapshot(self) -> None:
        item = self.snap_tree.selection()
        if not item:
            messagebox.showinfo("提示", "请先在快照历史中选择一条记录。")
            return

        snap_id = int(self.snap_tree.item(item[0], "values")[0])
        ok = messagebox.askyesno("确认恢复", f"确认恢复快照 #{snap_id} 吗？\n会先备份当前存档。")
        if not ok:
            return
        self.log(f"开始恢复快照: #{snap_id}")

        def work() -> None:
            args = type("Args", (), {"snapshot_id": snap_id})
            core.cmd_restore(args)
            self.log_async(f"已执行恢复: #{snap_id}")

        self._run_bg(work, on_done=self.refresh_history)

    def _watch_loop(self) -> None:
        self.after(0, lambda: self.watch_status.set("监听状态: 运行中"))
        self.log_async("监听已启动")

        with core.connect_db() as conn:
            games = core.list_games(conn)
        states = core.running_game_map(games)

        while not self.watch_stop.is_set():
            time.sleep(3)
            with core.connect_db() as conn:
                games = core.list_games(conn)
                current = core.running_game_map(games)

                for g in games:
                    old = states.get(g.id, False)
                    new = current.get(g.id, False)
                    if not old and new:
                        self.log_async(f"检测到启动: {g.name}")
                        archive = core.snapshot_game(conn, g, event="game_start", note="自动: 启动前备份")
                        if archive:
                            core.upload_snapshot(conn, g, archive)
                            self.after(0, self.refresh_history)
                    elif old and not new:
                        self.log_async(f"检测到退出: {g.name}")
                        archive = core.snapshot_game(conn, g, event="game_stop", note="自动: 退出后备份")
                        if archive:
                            core.upload_snapshot(conn, g, archive)
                            self.after(0, self.refresh_history)
                states = current

        self.after(0, lambda: self.watch_status.set("监听状态: 未启动"))
        self.log_async("监听已停止")

    def start_watch(self) -> None:
        if core.psutil is None:
            messagebox.showerror("缺少依赖", "请先安装 psutil：\npython -m pip install -r requirements.txt")
            return
        if self.watch_thread and self.watch_thread.is_alive():
            messagebox.showinfo("提示", "监听已经在运行。")
            return

        self.watch_stop.clear()
        self.watch_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watch_thread.start()

    def stop_watch(self) -> None:
        self.watch_stop.set()

    def on_close(self) -> None:
        self.stop_watch()
        self.destroy()


def main() -> None:
    app = GameCloudGUI()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()


if __name__ == "__main__":
    main()
