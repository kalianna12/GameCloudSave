from pathlib import Path
import argparse
import hashlib
import json
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from install_core import install

def resources():return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
def desktop():
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders') as key:return Path(winreg.QueryValueEx(key,'Desktop')[0])
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--silent',action='store_true');parser.add_argument('--target');parser.add_argument('--desktop');parser.add_argument('--start-menu');parser.add_argument('--no-register',action='store_true');args=parser.parse_args()
    payload=resources()/'payload.zip';meta=json.loads((resources()/'payload.json').read_text())
    with payload.open('rb') as stream:
        if hashlib.file_digest(stream,'sha256').hexdigest()!=meta['sha256']:raise ValueError('安装包完整性校验失败')
    target=args.target or str(Path(os.environ['LOCALAPPDATA'])/'Programs/GameCloudSave')
    menu=args.start_menu or str(Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/GameCloudSave')
    if args.silent:install(payload,target,args.desktop,args.start_menu,version=meta['version'],registry=not args.no_register);return 0
    root=tk.Tk();root.title('GameCloudSave 安装');root.geometry('680x540');root.resizable(False,False)
    style=ttk.Style();style.theme_use('vista');style.configure('.',font=('Microsoft YaHei UI',10))
    frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='安装 GameCloudSave',font=('Microsoft YaHei UI',19,'bold')).pack(anchor='w',pady=(0,12))
    ttk.Label(frame,text='安装到当前用户，无需管理员权限。设置和存档备份单独保存。').pack(anchor='w',pady=(0,14))
    notice=tk.Text(frame,height=9,wrap='word',font=('Microsoft YaHei UI',9));notice.insert('1.0',(resources()/'OPEN_SOURCE_NOTICE.txt').read_text(encoding='utf-8'));notice.configure(state='disabled');notice.pack(fill='x',pady=(0,12))
    folder=tk.StringVar(value=target);row=ttk.Frame(frame);row.pack(fill='x')
    ttk.Entry(row,textvariable=folder).pack(side='left',fill='x',expand=True)
    def browse():
        chosen=filedialog.askdirectory(initialdir=folder.get());folder.set(chosen or folder.get())
    ttk.Button(row,text='选择目录',command=browse).pack(side='right',padx=(8,0))
    make_desktop=tk.BooleanVar(value=True);accepted=tk.BooleanVar(value=False)
    ttk.Checkbutton(frame,text='建立桌面快捷方式',variable=make_desktop).pack(anchor='w',pady=(12,0))
    ttk.Checkbutton(frame,text='已阅读开源许可和使用说明',variable=accepted).pack(anchor='w',pady=(8,10))
    progress=ttk.Progressbar(frame,maximum=100);progress.pack(fill='x');status=ttk.Label(frame,text='请先退出旧版及托盘程序。');status.pack(anchor='w',pady=8)
    def run():
        if not accepted.get():messagebox.showinfo('开源说明','请先阅读开源许可和使用说明。');return
        button.configure(state='disabled');chosen_folder=folder.get();chosen_desktop=str(desktop()) if make_desktop.get() else None
        def worker():
            try:
                install(payload,chosen_folder,chosen_desktop,menu,version=meta['version'],progress=lambda value:root.after(0,lambda v=value:progress.configure(value=v)))
                root.after(0,lambda:status.configure(text='安装完成。可从桌面或开始菜单启动，首次启动会打开设置向导。'))
            except Exception as error:root.after(0,lambda message=str(error):messagebox.showerror('安装失败',message))
            finally:root.after(0,lambda:button.configure(state='normal'))
        threading.Thread(target=worker,daemon=True).start()
    button=ttk.Button(frame,text='安装',command=run);button.pack(side='right',pady=8)
    root.protocol('WM_DELETE_WINDOW',lambda:messagebox.showinfo('正在安装','请等待安装完成。') if button.instate(['disabled']) else root.destroy())
    root.mainloop();return 0
if __name__=='__main__':sys.exit(main())
