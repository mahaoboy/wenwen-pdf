# 📄 文问（WenWen）—— 中国版 PDF.ai

> 上传 PDF，直接提问，AI 给**带出处引用**的答案。

面向中国专业工作者的文档智能问答平台。解析 PDF 文档（合同、报告、论文、说明书等），构建本地混合检索引擎，让用户像聊天一样向文档提问，每个答案都附带原文出处，可一键跳转验证。

## ✨ 功能特性

- **PDF 智能解析**：PyMuPDF + PDFPlumber 提取文本与版面，按段落/条款自动切片，保留页码位置信息
- **混合检索引擎**：BGE 向量语义检索 + BM25 关键词检索（jieba 分词 + 平滑 IDF），RRF 融合排序，兼顾语义与精准匹配
- **引用溯源**：每个回答附带原文引用（页码 + 片段），点击跳转原文位置，杜绝幻觉
- **多轮对话**：支持连续追问，后端维护对话历史，上下文窗口自动截断
- **一键隐私删除**：删除文档时连带清理切片、向量索引、BM25 缓存，不留痕迹
- **本地优先架构**：向量存储用 numpy 本地矩阵，零外部服务依赖，可平滑迁移到 Qdrant/PostgreSQL

## 🏗️ 技术架构

| 层 | 选型 | 说明 |
|----|------|------|
| 后端框架 | FastAPI + SQLAlchemy 2.x | 异步高性能，上传/流式友好 |
| 数据库 | SQLite（MVP） | 零运维起步，可平滑迁移 PostgreSQL |
| PDF 解析 | PyMuPDF + PDFPlumber | 电子版文本提取，中文段落保留 |
| OCR（扫描件） | PaddleOCR（预留接口） | 中文强、免费、可本地部署 |
| 切片 | 按段落/条款切片 + 上下文重叠 | 合同条款切片利于引用定位 |
| 向量化 | BGE 本地（默认 bge-small-zh-v1.5） | 中文语义强、免费、离线可用 |
| 向量存储 | numpy 本地矩阵 | MVP 零依赖零运维，后续可迁 Qdrant |
| 关键词检索 | 自实现 BM25（jieba 分词 + 平滑 IDF） | 小语料 IDF 恒正不退化 |
| LLM 生成 | DeepSeek（主力）/ Qwen（备选） | 国产模型成本低、中文好 |
| 认证 | JWT | 轻量，MVP 足够 |
| 前端 | Next.js 15（App Router）+ Tailwind CSS 4 | SSR 友好，引用溯源跳转体验好 |

## 📁 目录结构

```
PDF文档问答/
├── README.md
├── .env.example
├── backend/
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口
│   │   ├── core/                   # 配置、安全
│   │   ├── db/                     # 数据库模型
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── api/                    # 路由层
│   │   │   ├── deps.py
│   │   │   └── routes/             # auth / documents / chat / billing
│   │   └── services/               # 业务服务层
│   │       ├── parsing/            # 解析、切片、OCR
│   │       ├── retrieval/          # 向量化、向量库、BM25、混合检索
│   │       ├── generation/         # LLM、Prompt、引用映射
│   │       └── cache.py
│   └── tests/                      # pytest 测试（18 个用例全绿）
└── frontend/                       # Next.js 前端
    ├── app/                        # App Router 页面
    │   ├── login/                  # 登录/注册
    │   ├── docs/                   # 文档列表
    │   └── docs/[id]/              # 对话页
    ├── lib/                        # API 封装、认证、类型
    └── components/                 # UI 组件
```

## 🚀 快速开始

### 1. 后端

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install torch --index-url https://download.pytorch.org/whl/cpu  # CPU 版 torch
pip install -r requirements.txt
cp ../.env.example .env  # 填入 DeepSeek API Key 等
# 国内下载 embedding 模型先执行：export HF_ENDPOINT=https://hf-mirror.com
uvicorn app.main:app --reload --port 8000
```

### 2. 前端

```bash
cd frontend
npm install
cp .env.example .env.local  # 配置 API 地址
npm run dev  # http://localhost:3000
```

### 3. 运行测试

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v  # 18 个用例
```

## 📡 API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 注册 |
| POST | `/api/auth/login` | 登录，返回 JWT |
| GET | `/api/documents` | 文档列表 |
| POST | `/api/documents/upload` | 上传 PDF |
| DELETE | `/api/documents/{id}` | 删除文档（连带清理索引） |
| POST | `/api/documents/{id}/chat` | 文档问答 |
| GET | `/api/documents/{id}/messages` | 对话历史 |

## 🔒 安全与隐私

- **幻觉治理**：Prompt 强制仅基于检索片段作答，无相关内容返回"文档中未找到"，引用必须来自检索结果
- **隐私保护**：文档权限隔离、一键删除连带清理向量/缓存、不用于模型训练
- **本地优先**：所有向量化、索引、存储均在本地完成，数据不离开你的机器

## 📋 路线图

- [x] MVP：上传 → 解析 → 问答 → 引用溯源
- [x] 混合检索（向量 + BM25 + RRF）
- [x] 多轮对话
- [ ] OCR 扫描件支持（PaddleOCR 接入）
- [ ] 套餐与支付（微信/支付宝）
- [ ] 多文档联合问答
- [ ] To-D API 开放

## 📄 许可证

MIT License
