# AI Drive Manager Agent V1

这是第一版可运行 MVP：

- Google OAuth 2.0 连接 Google Drive
- 自动创建 `AI智能资料库` 分类文件夹树
- 上传 PDF / DOCX / TXT / Markdown / 图片 / 常见音频文件
- 文本抽取；配置 OpenAI Key 后启用 AI 分类、摘要、文件命名
- 图片可由视觉模型分析内容后分类
- 音频可先转写再分类
- 自动上传到对应 Google Drive 文件夹
- SQLite 保存资料目录和摘要
- 支持快速搜索并返回 Google Drive 打开链接
- 没有 OpenAI Key 时仍能用基础关键词规则归档

## 1. 环境

建议 Python 3.11 或 3.12。

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

macOS / Linux:

```bash
source .venv/bin/activate
```

安装依赖：

```bash
pip install -r requirements.txt
```

复制环境变量：

```bash
cp .env.example .env
```

Windows 可以直接复制 `.env.example` 并改名为 `.env`。

## 2. Google Cloud 设置

1. 打开 Google Cloud Console。
2. 新建或选择项目。
3. 启用 **Google Drive API**。
4. 配置 **OAuth consent screen**。
5. 创建 OAuth Client ID，Application type 选择 **Web application**。
6. Authorized redirect URI 增加：

```text
http://localhost:8000/api/auth/google/callback
```

7. 下载 OAuth JSON，并重命名为：

```text
client_secret.json
```

放到项目根目录，与 `requirements.txt` 同一级。

本项目使用：

```text
https://www.googleapis.com/auth/drive.file
```

这是较小范围的 Drive 权限，主要访问应用创建或由应用获得访问权的文件。

## 3. OpenAI（可选但建议）

在 `.env` 中加入：

```text
OPENAI_API_KEY=你的API Key
OPENAI_MODEL=gpt-5.6-luna
```

没有 Key 时，系统仍能使用基础关键词规则分类，但图片内容理解、智能摘要和语音转写能力会受限。

## 4. 启动

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器打开：

```text
http://localhost:8000
```

然后：

1. 点击「连接 Google Drive」
2. 完成 Google 授权
3. 系统自动建立分类目录
4. 上传资料
5. 在搜索框中查找

## 5. 默认文件夹

```text
AI智能资料库/
├── 01_公司业务/
│   ├── SG-LYF
│   ├── Shopee
│   ├── EasyBoss
│   ├── 供应商
│   └── 合同
├── 02_财务税务/
│   ├── 银行
│   ├── 发票
│   ├── IRAS
│   └── 付款凭证
├── 03_政府与证件/
│   ├── MOM
│   ├── ACRA
│   ├── Corppass
│   └── 个人证件
├── 04_家庭个人/
│   ├── 教育
│   ├── 旅行
│   ├── 保险
│   └── 其他
├── 05_图片与扫描件
├── 06_语音与会议记录
├── 07_学习资料
└── 99_待确认
```

## 6. V1 已知限制

- 这是单用户 MVP，token 保存在本机 `data/token.json`。
- 搜索是目录/全文基础搜索，不是完整向量 RAG。
- 扫描 PDF 若本身没有文本层，V1 暂未做专门 OCR；图片可以用视觉模型识别。
- 大文件、批量导入、重复文件检测、版本管理尚未加入。
- 生产部署时必须使用 HTTPS、加密 token、数据库用户隔离和更严格的 OAuth / ACL 策略。

## 7. 下一版建议

V1.1：
- 拖拽和手机拍照上传
- 批量上传
- OCR
- 低置信度“待确认”人工确认后移动
- 重复文件检测
- 自动日期/公司/人物元数据

V2：
- Embedding + 向量数据库
- Hybrid Search + Reranker
- RAG 问答
- 文件级引用和页码溯源
- Gmail 附件自动归档
- 多用户和权限控制
