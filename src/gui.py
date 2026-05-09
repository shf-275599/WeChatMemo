#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import sys
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from wxManager import DatabaseConnection, MessageType
from exporter import HtmlExporter, TxtExporter, AiTxtExporter, DocxExporter, MarkdownExporter, ExcelExporter
from exporter.config import FileType


class WeChatExporterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("微信聊天记录导出工具")
        self.root.geometry("700x580")
        self.root.resizable(False, False)

        self.database = None
        self.contacts = []
        self.filtered_contacts = []
        self.db_dir = tk.StringVar()
        self.db_version = tk.IntVar(value=4)
        self.output_dir = tk.StringVar(value=os.path.join(BASE_DIR, "output"))
        self.export_format = tk.StringVar(value="HTML")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_contacts)

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        db_frame = ttk.LabelFrame(self.root, text="数据库", padding=10)
        db_frame.pack(fill="x", **pad)

        ttk.Label(db_frame, text="路径:").grid(row=0, column=0, sticky="w")
        ttk.Entry(db_frame, textvariable=self.db_dir, width=50).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(db_frame, text="浏览", command=self.browse_db).grid(row=0, column=2)
        ttk.Button(db_frame, text="自动解密", command=self.auto_decrypt).grid(row=0, column=3, padx=5)

        ttk.Label(db_frame, text="版本:").grid(row=1, column=0, sticky="w", pady=(5,0))
        ttk.Radiobutton(db_frame, text="微信 4.0", variable=self.db_version, value=4).grid(row=1, column=1, sticky="w", pady=(5,0))
        ttk.Radiobutton(db_frame, text="微信 3.x", variable=self.db_version, value=3).grid(row=1, column=2, sticky="w", pady=(5,0))
        ttk.Button(db_frame, text="加载联系人", command=self.load_contacts).grid(row=1, column=3, pady=(5,0))
        db_frame.columnconfigure(1, weight=1)

        contact_frame = ttk.LabelFrame(self.root, text="选择联系人", padding=10)
        contact_frame.pack(fill="both", expand=True, **pad)

        ttk.Label(contact_frame, text="搜索:").pack(anchor="w")
        ttk.Entry(contact_frame, textvariable=self.search_var).pack(fill="x", pady=(0, 5))

        list_container = ttk.Frame(contact_frame)
        list_container.pack(fill="both", expand=True)

        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side="right", fill="y")

        self.contact_list = tk.Listbox(list_container, yscrollcommand=scrollbar.set, font=("Microsoft YaHei", 10))
        self.contact_list.pack(fill="both", expand=True)
        scrollbar.config(command=self.contact_list.yview)

        export_frame = ttk.LabelFrame(self.root, text="导出设置", padding=10)
        export_frame.pack(fill="x", **pad)

        ttk.Label(export_frame, text="格式:").grid(row=0, column=0, sticky="w")
        fmt_combo = ttk.Combobox(export_frame, textvariable=self.export_format, values=["HTML", "TXT", "DOCX", "Excel", "Markdown", "AI_TXT"], state="readonly", width=15)
        fmt_combo.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(export_frame, text="输出:").grid(row=0, column=2, sticky="w", padx=(20,0))
        ttk.Entry(export_frame, textvariable=self.output_dir, width=25).grid(row=0, column=3, sticky="ew", padx=5)
        ttk.Button(export_frame, text="浏览", command=self.browse_output).grid(row=0, column=4)
        export_frame.columnconfigure(3, weight=1)

        ttk.Button(self.root, text="开始导出", command=self.start_export).pack(pady=10)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", side="bottom", padx=10, pady=(0, 10))

    def browse_db(self):
        path = filedialog.askdirectory(title="选择解密后的数据库文件夹")
        if path:
            self.db_dir.set(path)

    def browse_output(self):
        path = filedialog.askdirectory(title="选择输出文件夹")
        if path:
            self.output_dir.set(path)

    def auto_decrypt(self):
        if hasattr(self, '_decrypting') and self._decrypting:
            return
        self._decrypting = True
        self.status_var.set("正在解密数据库...")
        self.root.update()

        def do_decrypt():
            try:
                from wxManager.decrypt import get_info_v4, get_info_v3
                from wxManager.decrypt.decrypt_dat import get_decode_code_v4
                from wxManager.decrypt import decrypt_v4, decrypt_v3
                from wxManager import Me

                version = self.db_version.get()
                if version == 4:
                    infos = get_info_v4()
                else:
                    version_list_path = os.path.join(os.path.dirname(__file__), 'wxManager', 'decrypt', 'version_list.json')
                    with open(version_list_path, "r", encoding="utf-8") as f:
                        version_list = json.loads(f.read())
                    infos = get_info_v3(version_list)

                if not infos:
                    self.root.after(0, lambda: messagebox.showerror("错误", "未找到微信进程，请确保微信已登录"))
                    self.root.after(0, lambda: self.status_var.set("解密失败"))
                    return

                info = infos[0]
                if info.get('errcode') == 404:
                    self.root.after(0, lambda: messagebox.showerror("错误", "未找到密钥，请重启微信后重试"))
                    self.root.after(0, lambda: self.status_var.set("解密失败"))
                    return

                wxid = info['wxid']
                wx_dir = info['wx_dir']
                key = info['key']
                output_dir = os.path.join(BASE_DIR, 'data', wxid)

                if not os.path.exists(wx_dir):
                    self.root.after(0, lambda: messagebox.showerror("错误", f"微信目录不存在: {wx_dir}"))
                    self.root.after(0, lambda: self.status_var.set("解密失败"))
                    self.root.after(0, lambda: setattr(self, '_decrypting', False))
                    return

                os.makedirs(output_dir, exist_ok=True)

                if version == 4:
                    xor_key = get_decode_code_v4(wx_dir)
                    decrypt_v4.decrypt_db_files(key, src_dir=wx_dir, dest_dir=output_dir)
                    db_path = os.path.join(output_dir, 'db_storage')
                else:
                    decrypt_v3.decrypt_db_files(key, src_dir=wx_dir, dest_dir=output_dir)
                    db_path = os.path.join(output_dir, 'Msg')

                if not os.path.exists(db_path):
                    self.root.after(0, lambda: messagebox.showerror("错误", f"解密失败，数据库路径不存在: {db_path}"))
                    self.root.after(0, lambda: self.status_var.set("解密失败"))
                    self.root.after(0, lambda: setattr(self, '_decrypting', False))
                    return

                me = Me()
                me.wx_dir = wx_dir
                me.wxid = wxid
                me.name = info.get('name', '')
                info_data = me.to_json()
                with open(os.path.join(db_path, 'info.json'), 'w', encoding='utf-8') as f:
                    json.dump(info_data, f, ensure_ascii=False, indent=4)

                abs_db_path = os.path.abspath(db_path)
                self.root.after(0, lambda: self.db_dir.set(abs_db_path))
                self.root.after(0, lambda: self.status_var.set(f"解密成功: {wxid}"))
                self.root.after(0, lambda: setattr(self, '_decrypting', False))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("解密失败", str(e)))
                self.root.after(0, lambda: self.status_var.set("解密失败"))
                self.root.after(0, lambda: setattr(self, '_decrypting', False))

        threading.Thread(target=do_decrypt, daemon=True).start()

    def load_contacts(self):
        db_dir = self.db_dir.get()
        if not db_dir or not os.path.exists(db_dir):
            messagebox.showwarning("提示", "请先选择或解密数据库")
            return

        self.status_var.set("正在加载联系人...")
        self.root.update()

        def do_load():
            try:
                conn = DatabaseConnection(db_dir, self.db_version.get())
                database = conn.get_interface()
                if not database:
                    self.root.after(0, lambda: messagebox.showerror("错误", "数据库初始化失败"))
                    return

                self.database = database
                contacts = database.get_contacts()
                self.contacts = []
                for c in contacts:
                    label = f"{c.nickname or c.wxid}"
                    if c.remark:
                        label = f"{c.remark} ({c.nickname})"
                    if c.is_chatroom:
                        label = f"[群] {label}"
                    self.contacts.append({
                        "label": label,
                        "wxid": c.wxid,
                        "contact": c
                    })

                self.filtered_contacts = self.contacts[:]
                self.root.after(0, self._refresh_list)
                self.root.after(0, lambda: self.status_var.set(f"加载完成，共 {len(self.contacts)} 个联系人"))

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("加载失败", str(e)))

        threading.Thread(target=do_load, daemon=True).start()

    def filter_contacts(self, *args):
        keyword = self.search_var.get().strip().lower()
        if not keyword:
            self.filtered_contacts = self.contacts[:]
        else:
            self.filtered_contacts = [c for c in self.contacts if keyword in c["label"].lower() or keyword in c["wxid"].lower()]
        self._refresh_list()

    def _refresh_list(self):
        self.contact_list.delete(0, tk.END)
        for c in self.filtered_contacts:
            self.contact_list.insert(tk.END, c["label"])

    def start_export(self):
        sel = self.contact_list.curselection()
        if not sel:
            messagebox.showwarning("提示", "请先选择一个联系人")
            return

        contact_info = self.filtered_contacts[sel[0]]
        contact = contact_info["contact"]
        output_dir = self.output_dir.get()
        fmt = self.export_format.get()

        exporter_map = {
            "HTML": (HtmlExporter, FileType.HTML),
            "TXT": (TxtExporter, FileType.TXT),
            "DOCX": (DocxExporter, FileType.DOCX),
            "Excel": (ExcelExporter, FileType.XLSX),
            "Markdown": (MarkdownExporter, FileType.MARKDOWN),
            "AI_TXT": (AiTxtExporter, FileType.AI_TXT),
        }

        exporter_cls, file_type = exporter_map[fmt]

        self.status_var.set(f"正在导出 {contact_info['label']} 的聊天记录...")
        self.root.update()

        def do_export():
            try:
                exporter = exporter_cls(
                    self.database,
                    contact,
                    output_dir=output_dir,
                    type_=file_type,
                    message_types=None,
                    time_range=['2000-01-01 00:00:00', '2035-12-31 00:00:00'],
                    group_members=None
                )
                exporter.start()
                self.root.after(0, lambda: messagebox.showinfo("完成", f"导出成功!\n保存到: {os.path.abspath(output_dir)}"))
                self.root.after(0, lambda: self.status_var.set("导出完成"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("导出失败", str(e)))
                self.root.after(0, lambda: self.status_var.set("导出失败"))

        threading.Thread(target=do_export, daemon=True).start()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    root = tk.Tk()
    app = WeChatExporterGUI(root)
    root.mainloop()
