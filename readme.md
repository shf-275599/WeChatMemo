# WeChatChatExporter

微信聊天记录导出工具，支持 GUI 可视化操作和命令行批量导出。

基于 [CosilC/WeChatMsgArchive](https://github.com/CosilC/WeChatMsgArchive) 整理优化。

## 功能

- 解密微信本地数据库（支持微信 3.x / 4.0）
- 可视化选择联系人，一键导出聊天记录
- 支持多种导出格式：HTML、TXT、DOCX、Excel、Markdown
- 还原微信聊天界面（文本、图片、表情包）

## 项目结构

```
WeChatChatExporter/
├── src/
│   ├── gui.py            # GUI 界面
│   ├── wxManager/        # 核心模块（数据库读取、解密）
│   └── exporter/         # 导出模块
├── example/              # 命令行示例脚本
├── doc/                  # 文档
├── data/                 # 解密后的数据库（git 忽略）
└── output/               # 导出结果（git 忽略）
```

## 环境要求

- Windows 10 / 11
- Python 3.8+
- 微信已登录

## 快速开始

### 方式一：使用 exe（推荐）

1. 双击 `WeChatExporter.exe` 启动
2. 点击 **「自动解密」** — 自动检测微信进程，提取密钥并解密数据库
3. 点击 **「加载联系人」** — 显示所有联系人列表
4. 在搜索框输入关键词筛选联系人
5. 选择导出格式（HTML / TXT / DOCX / Excel / Markdown）
6. 点击 **「开始导出」**

如果已经解密过数据库，可以手动指定路径跳过步骤 2：
- 数据库路径：`data/wxid_xxx/db_storage`

### 方式二：使用 Python 源码

```bash
pip install -r requirements.txt
python src/gui.py
```

操作流程同上。

### 方式三：命令行操作

**第一步：解密数据库**

```bash
python example/1-decrypt.py
```

- 微信 4.0：默认即可
- 微信 3.x：修改脚本最后一行为 `dump_v3()`

运行后会在 `wxid_xxx/db_storage` 下生成解密后的数据库。

**第二步：查看联系人**

编辑 `example/2-contact.py`，修改以下变量：

```python
db_dir = './data/wxid_xxx/db_storage'  # 解密后的数据库路径
db_version = 4  # 微信 4.0 填 4，3.x 填 3
```

```bash
python example/2-contact.py
```

记下要导出的好友 wxid。

**第三步：导出聊天记录**

编辑 `example/3-exporter.py`，修改以下变量：

```python
db_dir = './data/wxid_xxx/db_storage'  # 同上
db_version = 4                          # 同上
wxid = 'wxid_xxxxxx'                    # 要导出的好友 wxid
output_dir = './output/'                # 输出文件夹
```

```bash
python example/3-exporter.py
```

导出的 HTML 文件在 `output/` 下，用浏览器打开即可查看。

## 常见问题

### 微信版本兼容性

| 微信版本 | 密钥提取 | 说明 |
|---------|---------|------|
| 4.0.3.36 及以下 | ✅ 支持 | 推荐版本 |
| 4.0.3.39 ~ 4.1.x | ❌ 不支持 | 密钥存储机制变更 |

如果你的微信版本过高无法提取密钥，需要降级到 4.0.3.36：

- 下载地址：[WeChatWin_4.0.3.36.exe](https://github.com/iibob/wechat-win-archive/releases/tag/v4.0.3.36)
- 旧版微信可以和新版共存，不需要卸载

### 其他问题

- **闪退**：右键以管理员身份运行
- **找不到密钥**：确保微信已登录，尝试重启微信
- **杀毒软件报警**：程序无毒，手动放行即可
- **遇到问题**：删除 `data/` 目录，重启微信，重新解密

## 致谢

- [LC044/WeChatMsg](https://github.com/LC044/WeChatMsg) — 原项目
- [iibob/wechat-win-archive](https://github.com/iibob/wechat-win-archive) — 微信历史版本存档
- [xaoyaoo/PyWxDump](https://github.com/xaoyaoo/PyWxDump) — PC 微信工具

## 许可证

[MIT](./LICENSE)
