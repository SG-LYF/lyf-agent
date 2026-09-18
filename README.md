# AI Drive Manager Agent

AI Drive Manager Agent 开发版本归档仓库。

## 已归档版本

- **V1.0**：基础可运行版（完整源码保存在 `versions/V1.0/source/`）
- **V1.1**：自然语言/模糊搜索、分类规则与 AI 状态改进
- **V1.2**：Windows 一键启动器 / EXE 构建支持
- **V1.3**：浏览器直接录音、自动转写与归档
- **V1.4.1**：录音暂停/继续、停止确认、按内容主题分类
- **V1.4.2**：搜索结果显示完整存放路径、文件类型与上传时间

## 版本目录

```text
versions/
├─ V1.0/source/
├─ V1.1/ai-drive-manager-agent-v1.1-patch.zip
├─ V1.2/AI-Drive-Manager-V1.2-Launcher.zip
├─ V1.3/AI-Drive-Manager-V1.3-Recording-Patch.zip
├─ V1.4.1/AI-Drive-Manager-V1.4.1-Combined-Patch.zip
└─ V1.4.2/AI-Drive-Manager-V1.4.2-Search-Path-Patch.zip
```

## 安全说明

本仓库**不提交**以下敏感信息：

- `.env`
- OpenAI / 其他模型 API Key
- Google OAuth `client_secret.json`
- OAuth token
- 本地个人资料数据库

`.env.example` 仅为无密钥的配置模板，可安全用于版本管理。
