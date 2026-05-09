#!/usr/bin/env python
import os
import sys
import json
import threading
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

CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
MAX_RECENT = 5


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'recent_paths': [], 'output_dir': os.path.join(BASE_DIR, 'output')}


def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def add_recent_path(config, path):
    paths = config.get('recent_paths', [])
    if path in paths:
        paths.remove(path)
    paths.insert(0, path)
    config['recent_paths'] = paths[:MAX_RECENT]
    save_config(config)


class WeChatExporterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("微信聊天记录导出工具")
        self.root.geometry("700x620")
        self.root.resizable(False, False)

        self.config = load_config()
        self.database = None
        self.contacts = []
        self.filtered_contacts = []
        self.db_dir = tk.StringVar()
        self.db_version = tk.IntVar(value=4)
        self.output_dir = tk.StringVar(value=self.config.get('output_dir', os.path.join(BASE_DIR, 'output')))
        self.export_format = tk.StringVar(value="HTML")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self.filter_contacts)

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        db_frame = ttk.LabelFrame(self.root, text="数据库", padding=10)
        db_frame.pack(fill="x", **pad)

        ttk.Label(db_frame, text="路径:").grid(row=0, column=0, sticky="w")
        self.path_combo = ttk.Combobox(db_frame, textvariable=self.db_dir, values=self.config.get('recent_paths', []), width=50)
        self.path_combo.grid(row=0, column=1, sticky="ew", padx=5)
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

        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill="x", padx=10, pady=5)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100, length=400)
        self.progress_bar.pack(fill="x", side="left", expand=True)

        self.progress_label = ttk.Label(progress_frame, text="0%", width=6)
        self.progress_label.pack(side="right", padx=(5, 0))

        ttk.Button(self.root, text="开始导出", command=self.start_export).pack(pady=10)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w").pack(fill="x", side="bottom", padx=10, pady=(0, 10))

    def update_progress(self, progress):
        percent = progress * 100
        self.progress_var.set(percent)
        self.progress_label.config(text=f"{percent:.1f}%")
        self.root.update_idletasks()

    def browse_db(self):
        path = filedialog.askdirectory(title="选择解密后的数据库文件夹")
        if path:
            self.db_dir.set(path)
            add_recent_path(self.config, path)
            self.path_combo['values'] = self.config.get('recent_paths', [])

    def browse_output(self):
        path = filedialog.askdirectory(title="选择输出文件夹")
        if path:
            self.output_dir.set(path)
            self.config['output_dir'] = path
            save_config(self.config)

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
                    self.root.after(0, lambda: messagebox.showerror("解密失败",
                        "未找到微信进程！\n\n"
                        "请检查：\n"
                        "1. 微信是否已登录（不是最小化，是真正登录状态）\n"
                        "2. 微信是否正在运行\n"
                        "3. 尝试重启微信后重试"))
                    self.root.after(0, lambda: self.status_var.set("解密失败"))
                    self.root.after(0, lambda: setattr(self, '_decrypting', False))
                    return

                info = infos[0]
                if info.errcode == 404:
                    self.root.after(0, lambda: messagebox.showerror("解密失败",
                        "未找到密钥！\n\n"
                        "请检查：\n"
                        "1. 微信版本是否 ≤ 4.0.3.36（更高版本不支持）\n"
                        "2. 重启微信后重试\n"
                        "3. 如需降级微信，详见 README"))
                    self.root.after(0, lambda: self.status_var.set("解密失败"))
                    self.root.after(0, lambda: setattr(self, '_decrypting', False))
                    return

                wxid = info.wxid
                wx_dir = info.wx_dir
                key = info.key
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
                me.name = info.nick_name or ''
                info_data = me.to_json()
                with open(os.path.join(db_path, 'info.json'), 'w', encoding='utf-8') as f:
                    json.dump(info_data, f, ensure_ascii=False, indent=4)

                abs_db_path = os.path.abspath(db_path)

                def update_ui():
                    self.db_dir.set(abs_db_path)
                    add_recent_path(self.config, abs_db_path)
                    self.path_combo['values'] = self.config.get('recent_paths', [])
                    messagebox.showinfo("解密成功", f"数据库解密成功！\n\n用户ID: {wxid}\n路径: {abs_db_path}\n\n请点击「加载联系人」按钮")
                    self.status_var.set(f"解密成功: {wxid}")
                    self._decrypting = False

                self.root.after(0, update_ui)

            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("解密失败", str(e)))
                self.root.after(0, lambda: self.status_var.set("解密失败"))
                self.root.after(0, lambda: setattr(self, '_decrypting', False))

        threading.Thread(target=do_decrypt, daemon=True).start()

    def load_contacts(self):
        db_dir = self.db_dir.get()
        if not db_dir or not os.path.exists(db_dir):
            messagebox.showwarning("提示",
                "请先选择数据库路径！\n\n"
                "操作步骤：\n"
                "1. 点击「浏览」选择已解密的数据库文件夹\n"
                "2. 或者点击「自动解密」自动检测微信并解密")
            return

        add_recent_path(self.config, db_dir)
        self.path_combo['values'] = self.config.get('recent_paths', [])
        self.status_var.set("正在加载联系人...")
        self.root.update()

        def do_load():
            try:
                conn = DatabaseConnection(db_dir, self.db_version.get())
                database = conn.get_interface()
                if not database:
                    self.root.after(0, lambda: messagebox.showerror("加载失败",
                        "数据库初始化失败！\n\n"
                        "请检查：\n"
                        "1. 路径是否正确（应选择 db_storage 或 Msg 文件夹）\n"
                        "2. 微信版本是否匹配（4.0 选微信 4.0，3.x 选微信 3.x）\n"
                        "3. 数据库是否已解密（未解密请先点击「自动解密」）"))
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
            messagebox.showwarning("提示",
                "请先选择一个联系人！\n\n"
                "操作步骤：\n"
                "1. 先点击「加载联系人」\n"
                "2. 在左侧列表中点击选择要导出的联系人")
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

        self.progress_var.set(0)
        self.progress_label.config(text="0%")
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
                    group_members=None,
                    progress_callback=lambda p: self.root.after(0, lambda: self.update_progress(p))
                )
                exporter.start()
                self.root.after(0, lambda: self.progress_var.set(100))
                self.root.after(0, lambda: self.progress_label.config(text="100%"))
                self.root.after(0, lambda: messagebox.showinfo("导出完成",
                    f"聊天记录导出成功！\n\n"
                    f"联系人: {contact_info['label']}\n"
                    f"格式: {fmt}\n"
                    f"保存到: {os.path.abspath(output_dir)}"))
                self.root.after(0, lambda: self.status_var.set("导出完成"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("导出失败",
                    f"导出失败！\n\n"
                    f"错误信息: {str(e)}\n\n"
                    f"请检查：\n"
                    f"1. 输出路径是否有写入权限\n"
                    f"2. 磁盘空间是否充足\n"
                    f"3. 联系人是否有聊天记录"))
                self.root.after(0, lambda: self.status_var.set("导出失败"))

        threading.Thread(target=do_export, daemon=True).start()


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    root = tk.Tk()
    app = WeChatExporterGUI(root)
    root.mainloop()
