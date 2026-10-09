from pathlib import Path
import argparse
import sys
import json
import threading
import tkinter as tk
from tkinter import ttk,messagebox
from install_core import uninstall

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--silent',action='store_true');parser.add_argument('--target');parser.add_argument('--report');args=parser.parse_args()
    target=Path(args.target).resolve() if args.target else Path(sys.executable).resolve().parent
    if args.silent:
        try:uninstall(target);result={'passed':True}
        except Exception as error:result={'passed':False,'error':str(error)}
        if args.report:Path(args.report).write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        return 0 if result['passed'] else 1
    root=tk.Tk();root.title('卸载 GameCloudSave');root.geometry('560x280');root.resizable(False,False)
    frame=ttk.Frame(root,padding=24);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='卸载 GameCloudSave',font=('Microsoft YaHei UI',18,'bold')).pack(anchor='w',pady=(0,14))
    ttk.Label(frame,text='移除程序、桌面和开始菜单快捷方式。\n设置、封面、密码和本地存档备份保留。',font=('Microsoft YaHei UI',10)).pack(anchor='w',pady=10)
    progress=ttk.Progressbar(frame,maximum=100);progress.pack(fill='x',pady=12)
    def run():
        if not messagebox.askyesno('确认卸载','卸载程序并保留个人数据？'):return
        button.configure(state='disabled')
        def worker():
            try:
                uninstall(target,lambda value:root.after(0,lambda v=value:progress.configure(value=v)))
                root.after(0,lambda:(messagebox.showinfo('卸载完成','程序已移除，个人数据保留。'),root.destroy()))
            except Exception as error:root.after(0,lambda message=str(error):messagebox.showerror('卸载失败',message));root.after(0,lambda:button.configure(state='normal'))
        threading.Thread(target=worker,daemon=True).start()
    button=ttk.Button(frame,text='卸载',command=run);button.pack(side='right',pady=6)
    root.protocol('WM_DELETE_WINDOW',lambda:messagebox.showinfo('正在卸载','请等待卸载完成。') if button.instate(['disabled']) else root.destroy())
    root.mainloop();return 0
if __name__=='__main__':sys.exit(main())
