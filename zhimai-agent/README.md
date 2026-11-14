# 知脉｜课程知识链路导航

这是根据超星“知脉”管理后台中读取到的配置，整理出的可在本机运行、可纳入 GitHub 仓库的版本。它包含课程知识检索、知识导航对话，以及五轮出题、作答、判题和学习报告。

## 已整理的内容

- `prompts/`：超星后台读取的系统提示词和两个任务流中的模型提示词。`system-source.txt` 保留后台显示的原始文本；`runtime-system.txt` 针对本地扩充的资料范围作了调整。
- `source-config.json` 和 `docs/任务流与迁移说明.md`：源平台模型、检索参数与任务流结构。
- `knowledge/default/`：从超星默认知识库导出的 12 份 Markdown 文档。
- `knowledge/local-notes/`、`knowledge/local-imports/`：从本地“知识系统”目录整理的 93 份课程笔记和导入资料。
- `app/`、`server.py`、`static/`：本地检索、模型接口和网页。

项目中的文档副本已将少量包含本机用户名的绝对路径改为通用描述；原始文件未修改。

本次本机索引扫描了 126 份资料，其中 110 份至少提取到一些可检索文字，生成 1,530 个文本片段；7,079 个页面或文件没有提取到文字。许多教材是扫描页，需要先使用 OCR 转成可搜索 PDF，才能检索其正文。扫描页未提取文字不代表书籍内容不存在。

## 本机使用

当前交付文件夹已经建立了独立运行环境和索引，并在本机 `.env` 中记录了你提供的教材目录。**对话和练习还需要填写模型服务地址和 API 密钥**；不会从超星后台复制账号或密钥。

1. 用文本编辑器打开项目目录中的 `.env`。分别填写知识导航用的 `NAV_BASE_URL`、`NAV_API_KEY`，和练习用的 `QUIZ_BASE_URL`、`QUIZ_API_KEY`。两个服务都需要提供兼容 Chat Completions 的接口。
2. `NAV_MODEL` 和 `QUIZ_MODEL` 已按源平台记录填写；如果你的服务商要求其他模型名或接入点 ID，请改成该服务实际提供的值。
3. 双击 `启动知脉.cmd`，在浏览器打开 `http://127.0.0.1:8765`。保持启动窗口打开；按 Ctrl+C 可停止服务。

`.env` 和本地索引已加入 `.gitignore`。不要把 API 密钥填入源码或上传到仓库。

## 在另一台电脑或从 GitHub 安装

需要 Python 3.10 或更新版本。在项目目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

编辑 `.env` 填入模型配置。macOS/Linux 可使用 `python3 -m venv .venv`、`source .venv/bin/activate` 和 `pip install -r requirements.txt`。

建立索引并启动：

```powershell
.\.venv\Scripts\python index_knowledge.py
.\.venv\Scripts\python server.py
```

默认只读取项目 `knowledge/` 中的文档。要直接读取电脑上的教材 PDF，在 `.env` 中设置 `KNOWLEDGE_SOURCE_DIR` 为教材所在目录，然后重新运行索引命令；程序会递归查找 PDF，并按文件内容跳过完全相同的副本。如果该目录使用本次“知识系统”的文件夹结构，还会直接读取其中的课程笔记和超星导入资料。修改原始资料后，需要重新建立索引。也可以单次指定目录：

```powershell
.\.venv\Scripts\python index_knowledge.py --source-dir "D:\你的知识系统目录"
```

如果没有原始目录，也可以使用本次另行交付的专业课程资料压缩包：

```powershell
.\.venv\Scripts\python index_knowledge.py --books-zip "D:\备份\专业课程资料.zip"
```

这两种方式选一种即可。索引过程可能需要几分钟并占用磁盘空间；请在重建索引前停止正在运行的服务。

## 上传 GitHub

将项目文件夹作为仓库提交，或使用另行交付的 GitHub 项目压缩包。压缩包不含 `.env`、本机索引、虚拟环境和大型教材 PDF。课程笔记会随项目上传；发布前请检查文档内容和教材的使用、分享权限。专业课程 PDF 备份单独保存，需要时通过本地目录或压缩包建立索引。

## 与超星版本的差异

- 源平台使用混合检索及重排，本项目使用本地 BM25 关键词检索；相似度阈值不能直接换算，检索结果不保证一致。
- 源平台的模型深度思考、重复惩罚等参数保存在 `source-config.json` 中；通用接口当前只发送模型名、温度和 Top P。不同服务商的模型名称与参数支持可能不同。
- 练习流程按实际节点实现为五轮生成、判题和报告；原平台任务流的文字简介提到查找教材习题，但读取到的节点实际使用模型生成题目。模型判题仍需核对。
- 源平台启用了七天长期记忆、文献传递回答和问题澄清；本地版只在当前网页会话中保留对话历史，没有长期记忆和文献传递功能。数智人形象、语音、附件上传、联网搜索和超星平台内的账号体系也没有迁移。网页默认仅监听本机地址；如需公开部署，需要另行配置访问控制及服务环境。
- 目前验证使用了模拟模型；真实服务尚未配置，尚未进行真实模型调用。

Windows 下运行测试：`.\.venv\Scripts\python -m unittest discover -s tests -v`。
