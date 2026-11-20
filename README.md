# JobCopilot

招聘求职双边平台，含求职者（C 端）与招聘方（B 端）两套界面，各自配备一个可调用工具的 AI 助手。

项目性质是**学习项目**：重点在自研 Agent Runtime、简历结构化抽取、向量 + 规则 + LLM 的三段式匹配，不面向真实上线，数据均为虚构。

## 功能概览

**求职者**
- 岗位列表：按匹配分推荐 / 全量搜索，支持收藏与不感兴趣反馈
- 岗位详情：匹配总分与逐项规则得分、AI 匹配理由、差距与补齐建议，可直接投递
- 简历中心：PDF / DOCX 上传或文本粘贴，解析为结构化档案；按目标岗位生成优化建议并保留版本历史
- 面试训练：基于岗位与简历出题，逐题作答后生成分维度报告
- 岗位订阅：保存筛选条件，新岗位进入站内通知
- AI 求职助手：自然语言找岗位、改简历、模拟面试等

**招聘方**
- 岗位管理：表格化维护岗位与在招状态，查看投递量
- 候选人看板：按匹配分排序，拖拽推进流程状态，查看规则分明细与 AI 评估
- 候选人面试报告、双 Agent 自主对谈（招聘方 Agent 与候选人 Agent 互相问答）
- AI 招聘助手：发布岗位、排序候选人、深度评估等

**公共**
- 注册 / 登录（JWT，角色 `seeker` / `employer`）
- SSE 流式对话，工具调用过程可展开查看
- 跨会话长期记忆（`save_memory` / `search_memory`）

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React 18、TypeScript、Vite、Tailwind CSS、TanStack Query、React Router |
| 后端 | FastAPI、SQLAlchemy 2、Pydantic v2、PyJWT、bcrypt |
| 数据 | SQLite（`backend/jobcopilot.db`） |
| 模型 | DeepSeek `deepseek-chat`（function calling）；阿里云百炼 `text-embedding-v4`（1024 维） |
| 解析 | pdfplumber、python-docx |

模型均通过 OpenAI 兼容适配层接入，切换供应商只需改 `backend/.env`。

## 架构

```
浏览器
  │  React SPA（Vite dev server :5180，/api 反向代理）
  ▼
FastAPI（:8000）
  ├─ routers       auth / resumes / jobs / applications / match / interviews / subscriptions / notifications / agent
  ├─ services      简历解析、岗位、投递、订阅扫描、面试、候选人
  ├─ matching      向量召回 → 规则精排 → LLM 解读
  ├─ agent         自研 tool-calling Runtime、工具注册、记忆、双 Agent 对谈
  ├─ llm           chat / embedding OpenAI 兼容适配层
  └─ SQLite        用户、简历、岗位、投递、面试、订阅、通知、记忆
```

匹配分构成：必需技能 40 + 加分技能 10 + 工作年限 20 + 地点 15 + 薪资 15。

## 目录结构

```
JobCopilot/
├─ backend/
│  ├─ app/
│  │  ├─ agent/        Agent Runtime、工具、记忆、双 Agent 对谈
│  │  ├─ llm/          chat / embedding 适配层
│  │  ├─ matching/     匹配管线与规则打分
│  │  ├─ routers/      HTTP 接口
│  │  ├─ services/     业务服务
│  │  ├─ models/       ORM 模型
│  │  ├─ schemas/      请求 / 响应模型
│  │  ├─ seed/         种子数据生成与灌库
│  │  └─ main.py
│  ├─ tests/           pytest 用例
│  ├─ requirements.txt
│  └─ .env.example
├─ frontend/
│  ├─ src/
│  │  ├─ components/   Layout、通用 UI、图标、弹窗
│  │  ├─ pages/        C 端与 B 端页面
│  │  ├─ lib/          API 客户端、鉴权
│  │  └─ index.css     设计 token 与两端主题
│  ├─ tailwind.config.js
│  └─ vite.config.ts
├─ seed_data/          83 个岗位、45 份简历（Markdown）
├─ docs/开发文档.md
├─ scripts/dev.ps1     PowerShell 一键启动
└─ start.bat           Windows 一键启动
```

## 快速开始

环境要求：Python 3.10+、Node.js 18+。

### 1. 配置环境变量

```powershell
cd backend
Copy-Item .env.example .env
```

在 `backend/.env` 中填写：

- `CHAT_API_KEY`：对话与工具调用（DeepSeek）
- `EMBEDDING_API_KEY`：向量召回与简历匹配（百炼）
- 生产部署时同时修改 `SECRET_KEY`

没有密钥仍可浏览页面，但简历解析、智能匹配、AI 对话、面试报告等依赖模型的功能会失败。

### 2. 初始化后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt

# 写入种子数据（会 drop 并重建数据库）
.venv\Scripts\python -m app.seed.seed

.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>

`app.seed.generate_seed_data` 仅用于重新生成 `seed_data/` 下的 Markdown，仓库已包含生成结果，一般无需执行。

### 3. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

打开 <http://127.0.0.1:5180>。

### 4. 一键启动（可选）

- Windows：双击根目录 `start.bat`
- PowerShell：`powershell -ExecutionPolicy Bypass -File scripts/dev.ps1`

脚本会检查依赖与数据库，并分别拉起前后端窗口。

## 演示账号

| 角色 | 用户名 | 密码 |
|---|---|---|
| 求职者 | `zhangsan` | `demo1234` |
| 招聘方 | `hr-li` | `demo1234` |

种子数据中的其他招聘方 / 候选人账号（`hr-01`、`cand01` 等）密码同为 `demo1234`。`zhangsan` 特意保持零投递，方便完整演示「找岗位 → 查看匹配解读 → 投递」链路。

## 测试与构建

```powershell
# 后端
cd backend
.venv\Scripts\python -m pytest

# 前端类型检查与生产构建
cd frontend
npm run build
```

## 相关文档

- [docs/开发文档.md](docs/开发文档.md)：项目定位、决策记录、数据模型、接口与演示脚本

## 说明

- 学习项目，数据为虚构内容，不对接真实招聘业务。
- `.env` 含模型密钥，已被 `.gitignore` 排除，请勿提交。
- `app.seed.seed` 会重建数据库，执行前请确认无需保留本地数据。
