# 贡献指南（Contributing to 文问 WenWen）

感谢你愿意为文问（WenWen）做出贡献！无论是修 Bug、加功能、补文档还是提建议，都欢迎。

本文档说明如何提 Issue、提交 PR、搭建开发环境以及需要遵守的代码规范。

---

## 目录

- [行为准则](#行为准则)
- [如何提 Issue](#如何提-issue)
- [开发环境搭建](#开发环境搭建)
- [如何提交 PR](#如何提交-pr)
- [代码规范](#代码规范)
- [测试与构建](#测试与构建)
- [目录结构速览](#目录结构速览)
- [许可证](#许可证)

---

## 行为准则

- 尊重彼此，保持友善、专业的讨论氛围。
- 对事不对人，技术分歧用事实和代码说话。
- 不发布他人的隐私信息、密钥或未授权数据。

---

## 如何提 Issue

提 Issue 前请先搜索是否已有相同问题。

### Bug 报告

请尽量包含以下信息：

1. **复现步骤**：从启动服务到触发问题的最小步骤。
2. **期望行为**与实际行为。
3. **环境信息**：操作系统、Python / Node.js 版本、浏览器版本、是否使用本地 LLM Key。
4. **日志与截图**：后端终端日志、浏览器 Console 报错、相关请求的 HTTP 状态码。
5. **示例文件**：如与 PDF 解析相关，请在脱敏后提供最小可复现 PDF。

### 功能建议

请说明：

1. 你遇到的真实场景与痛点（而不是直接给方案）。
2. 期望的交互或输出。
3. 你考虑过的替代方案。
4. 该功能对现有架构的影响（可选）。

### 安全漏洞

请**不要**在公开 Issue 中披露安全漏洞细节，直接通过 GitHub 联系维护者 [@mahaoboy](https://github.com/mahaoboy) 私下沟通。

---

## 开发环境搭建

### 前置要求

| 工具 | 版本建议 |
|------|----------|
| Python | 3.11+（开发环境使用 3.12） |
| Node.js | 18+（开发环境使用 20+） |
| Git | 任意较新版本 |

### 1. 克隆仓库

```bash
git clone git@github.com:mahaoboy/wenwen-pdf.git
cd wenwen-pdf
```

### 2. 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate

# 先装 CPU 版 torch（体积小、无需 GPU）
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

cp ../.env.example .env
# 编辑 .env，至少确认 DATABASE_URL；DEEPSEEK_API_KEY 可留空
uvicorn app.main:app --reload --port 8000
```

说明：

- 未配置 `DEEPSEEK_API_KEY` 时，问答自动降级为**抽取式回答**（直接摘录原文并带引用），方便本地开发与测试。
- 首次向量化会下载 Embedding 模型。国内网络建议先设置镜像：

  ```bash
  export HF_ENDPOINT=https://hf-mirror.com
  ```

- OCR（PaddleOCR）为预留能力，安装依赖体积较大；仅调试问答主链路时可暂不启用。

### 3. 前端

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
# 打开 http://localhost:3000
```

`frontend/.env.local` 默认配置：

```bash
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

后端已允许 `http://localhost:3000` 跨域；如前端换端口，请同步调整 `backend/app/main.py` 中的 CORS 配置。

### 4. 常用开发命令

| 位置 | 命令 | 说明 |
|------|------|------|
| backend | `pytest tests/ -v` | 运行后端测试 |
| backend | `uvicorn app.main:app --reload` | 启动后端热重载 |
| frontend | `npm run dev` | 启动前端开发服务器 |
| frontend | `npm run build` | 生产构建 + 类型检查 |
| frontend | `npm run start` | 启动生产构建产物 |

---

## 如何提交 PR

1. **Fork 仓库**并从 `main` 切出功能分支：

   ```bash
   git checkout -b feat/your-feature
   # 或 fix/your-bugfix
   ```

2. **保持改动聚焦**：一个 PR 只做一件事，避免顺手重构无关代码。
3. **补充测试**：
   - 后端逻辑变更请在 `backend/tests/` 增加或更新用例；
   - 前端交互变更请说明手动验证步骤。
4. **本地验证通过**：

   ```bash
   cd backend && source .venv/bin/activate && pytest tests/ -v
   cd frontend && npm run build
   ```

5. **提交信息遵循 Conventional Commits**：

   ```
   feat: 支持多文档联合问答
   fix: 修复引用页码在跨页切片时偏移
   docs: 补充环境变量说明
   refactor: 拆分检索融合逻辑
   test: 增加额度闸边界用例
   chore: 升级依赖
   ```

6. **发起 PR**，在描述中说明：
   - 这个改动解决了什么问题；
   - 实现思路与关键取舍；
   - 如何验证（命令 / 截图）；
   - 关联的 Issue（如 `Closes #12`）。

PR 合并前需要至少一名维护者 Review，并确保 CI / 本地测试与构建通过。

---

## 代码规范

### 通用

- 不提交密钥、`.env`、数据库文件、`uploads/`、`vectors/` 等运行时产物。
- 面向真实边界做校验（用户输入、外部 API），内部调用保持简洁。
- 注释只解释“为什么”，不重复代码表面含义。

### 后端（Python）

- 遵循 PEP 8；使用类型标注与清晰的命名。
- 路由层保持轻薄，业务逻辑放在 `app/services/`。
- 数据库访问统一通过 SQLAlchemy Session，不在路由中直接拼 SQL。
- 新增响应模型放在 `app/schemas/`，并确保 `from_attributes` 配置正确。
- 外部依赖（LLM、Embedding）需具备**降级路径**，不能因单点失败阻塞主流程。

### 前端（TypeScript / React）

- 启用 `strict` 模式，不允许 `any` 逃逸。
- 默认使用 Server Component；只有需要状态、副作用或浏览器 API 时才加 `"use client"`。
- 所有 HTTP 请求集中在 `lib/api.ts`，类型定义集中在 `lib/types.ts`。
- 样式使用 Tailwind CSS 原子类，保持与现有设计语言一致（emerald / teal 主色、圆角卡片、轻阴影）。
- 必须处理 loading、空状态、错误状态，错误信息要能被用户理解。

### 提交前自检

- [ ] 没有调试用 `console.log` / `print`
- [ ] 没有硬编码密钥或本地绝对路径
- [ ] 新增/修改的逻辑有测试或明确的手动验证记录
- [ ] `npm run build` 与 `pytest` 通过

---

## 测试与构建

```bash
# 后端
cd backend
source .venv/bin/activate
pytest tests/ -v

# 前端
cd frontend
npm run build
```

当前测试覆盖：注册登录、文档上传 / 列表 / 删除、PDF 解析与切片、混合检索、问答与引用校验、多轮会话、缓存与额度闸。

---

## 目录结构速览

```
PDF文档问答/
├── backend/
│   ├── app/
│   │   ├── api/routes/        # auth / documents / chat / billing
│   │   ├── core/              # 配置与安全
│   │   ├── db/                # 数据模型与会话
│   │   ├── schemas/           # Pydantic 模型
│   │   └── services/          # 解析 / 检索 / 生成 / 缓存
│   └── tests/                 # pytest 用例
├── frontend/
│   ├── app/                   # Next.js App Router 页面
│   ├── components/            # 通用 UI 组件
│   └── lib/                   # API 封装、认证、类型
├── CONTRIBUTING.md
├── CHANGELOG.md
├── LICENSE
└── README.md
```

---

## 许可证

本项目采用 [MIT License](./LICENSE)。提交贡献即表示你同意以 MIT 协议授权你的贡献。
