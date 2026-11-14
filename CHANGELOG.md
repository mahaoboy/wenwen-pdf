# 更新日志（Changelog）

本项目遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)，
格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

## [Unreleased]

### 计划中

- OCR 扫描件支持（PaddleOCR 接入）
- 套餐与支付（微信 / 支付宝沙箱）
- 多文档联合问答
- To-D API 开放

---

## [0.1.0] - 2026-11-14

首个 MVP 版本：从上传 PDF 到带引用问答的完整闭环。

### 新增（Added）

#### 后端

- **用户认证**：邮箱注册 / 登录，JWT 鉴权，密码 bcrypt 哈希。
- **文档管理**：PDF 上传、文档列表、删除；按用户隔离文档权限。
- **解析流水线**：PyMuPDF / PDFPlumber 提取文本与版面，按段落 / 条款切片，保留页码与字符位置，解析在后台任务中执行并回写状态（pending / parsing / ready / error）。
- **混合检索引擎**：
  - BGE 中文 Embedding（默认 `bge-small-zh-v1.5`，512 维）语义召回；
  - 自实现 BM25（jieba 分词 + 平滑 IDF）关键词召回；
  - RRF 融合排序，向量索引失败时自动降级为纯 BM25。
- **本地向量存储**：numpy 矩阵持久化，零外部服务依赖。
- **问答生成**：DeepSeek（OpenAI 兼容协议）主力生成；未配置 API Key 时自动降级为抽取式原文摘录，不编造内容。
- **引用校验**：回答中的 `[来源:{chunk_id}]` 必须命中真实检索结果，编造引用会被过滤；回答附带页码与原文片段。
- **多轮对话**：基于 `session_id` 维护会话上下文，自动截取最近 3 轮。
- **成本与额度闸**：相同文档 + 上下文 + 问题的回答缓存命中不扣额度；免费版文档数（3）与提问次数（20）硬限制。
- **隐私删除**：删除文档时连带清理原文件、切片、向量索引、BM25 缓存与问答缓存。
- **套餐查询接口**：`GET /api/billing/quota` 返回当前套餐与用量。

#### 前端

- **注册 / 登录页**：登录与注册切换，JWT 本地存储，错误提示与 loading 状态。
- **文档列表页**：拖拽 / 点击上传 PDF，解析状态自动轮询，删除确认，额度用量展示。
- **对话页**：多轮提问、原文引用角标与片段展开、解析中 / 失败状态、Enter 发送 / Shift+Enter 换行、移动端适配。
- **公开推广首页（Landing Page）**：Hero、功能特性、技术架构、快速开始、MIT License 与作者信息，响应式布局。
- **统一 API 封装**：集中处理鉴权头、错误信息提取与 401 跳转。

#### 工程与文档

- `README.md`：项目介绍、功能特性、技术架构、快速开始与 API 概览。
- `CONTRIBUTING.md`：Issue / PR 流程、开发环境搭建、代码规范与自检清单。
- `CHANGELOG.md`：版本记录。
- `PROMO.md`：推广文案。
- 后端 pytest 测试覆盖认证、文档、解析、检索、问答、多轮会话、缓存与额度等模块。

### 修复（Fixed）

- 前端问答接口与后端实际路由对齐：由 `/api/documents/{id}/chat` 调整为 `POST /api/chat/ask`。
- 对话历史接口对齐：由 `/api/documents/{id}/messages` 调整为 `GET /api/chat/history`。
- 多轮对话改为使用后端 `session_id` 延续上下文，并在浏览器本地按文档持久化会话，刷新页面后仍可继续追问。
- 文档列表删除后同步刷新额度用量，避免展示过期数据。

### 已知限制（Known Limitations）

- 扫描版 PDF（纯图片）暂走 OCR 预留接口，识别效果有限。
- SQLite 单文件数据库，面向单机 / 小规模使用；高并发场景需迁移 PostgreSQL。
- 支付仅保留沙箱接口，尚未接入真实微信 / 支付宝下单。
- 单次检索默认 Top-5 片段，超长文档的跨章节推理能力有限。

---

[Unreleased]: https://github.com/mahaoboy/wenwen-pdf/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/mahaoboy/wenwen-pdf/releases/tag/v0.1.0
