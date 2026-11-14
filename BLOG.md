# 从 0 到 1 构建中国版 PDF.ai：文问 WenWen 的 RAG 架构实践

> 上传 PDF，直接提问，AI 给你带出处的答案。
>
> 项目开源地址：**[github.com/mahaoboy/wenwen-pdf](https://github.com/mahaoboy/wenwen-pdf)**，觉得有用的话点个 Star ⭐，这对独立开发者是真实的鼓励。

PDF.ai 用 RAG 在四个月做到 $25K MRR 的故事验证了一件事：**文档问答 + 引用溯源**是一个真实的付费需求。但在国内直接照搬会遇到三个水土不服——中文合同/财报的解析质量、扫描件比例高、以及用户对"AI 说了什么"的信任成本。

文问（WenWen）是我们对此的回答：一个面向中国专业工作者的开源文档问答系统。本文讲清楚它的架构、几个关键的技术决策、以及踩过的坑。

---

## 一、架构总览

```
上传 PDF
    ↓
文档解析（PyMuPDF 为主 → PDFPlumber 兜底 → PaddleOCR 扫描件）
    ↓
条款切片（按「第X条 / 1.」编号断片，非固定长度，带页码+bbox 位置）
    ↓
向量化（BGE 本地推理，归一化）
    ↓
混合检索（numpy 向量召回 + BM25 关键词召回 → RRF 融合）
    ↓
生成（DeepSeek，Prompt 强制文档内作答）
    ↓
引用校验（模型输出的引用必须在检索结果中真实存在，编造即丢弃）
    ↓
返回：回答 + 可点击跳转原文的引用
```

技术栈一句话：**FastAPI + SQLAlchemy/SQLite + BGE + numpy 向量索引 + 自实现 BM25 + DeepSeek**，MVP 全部用免费/嵌入式组件，一台 2 核 4G 的机器就能跑。

---

## 二、三个关键决策（以及为什么）

### 决策 1：向量存储用本地 numpy 矩阵，而不是 Qdrant / Pinecone / Chroma

RAG 教程会教你上向量数据库。但我们算了一笔账：

- 单文档切片量级：一份 50 页合同 ≈ 100~300 个 chunk。即使 1000 个付费用户 × 100 文档，也只是百万级向量——**numpy 矩阵乘法毫秒级完成**。
- 每文档一个 `.npy` 文件 + 一个 meta JSON，删除文档 = 删两个文件，事务语义简单到不会出错。
- 换 Qdrant/Pinecone 意味着多一个常驻服务、一份迁移脚本、一类新的运维故障。

**结论**：MVP 阶段用 numpy（点积即余弦，向量入库前归一化），把「向量存储」抽象成 4 个函数（index/search/get_meta/delete），未来迁 Qdrant 只改这一个文件。**规模没到之前，复杂度就是负债。**

### 决策 2：自实现 BM25，而不是用 rank_bm25

这是一个被真实 bug 教育出来的决策。联调时发现 BM25 对中文合同检索返回空，排查后是 rank_bm25 的 `BM25Okapi` 的 IDF 公式问题：

```
IDF = ln((N - n + 0.5) / (n + 0.5))
```

当语料只有 2 个 chunk、词出现在其中 1 个时：`IDF = ln(1.5/1.5) = ln(1) = 0`——**整个检索全零分**。这不是极端场景：合同按条款切片后，一份小合同就只有 2~3 个切片，Okapi 公式在小语料下系统性退化。

修复方案是自实现 BM25 评分（30 行代码），IDF 改用平滑式：

```python
IDF = ln((N + 1) / (n + 0.5))   # 恒为正，小语料可用
score = Σ IDF(qi) * f*(k1+1) / (f + k1*(1-b+b*|D|/avgdl))
```

顺带把 `rank_bm25` 依赖移除了。教训：**引入一个"标准库"之前，先看它的数学在你的数据分布下是否成立。**

### 决策 3：Embedding 选 bge-small-zh-v1.5 起步，而不是直接上 BGE-M3

BGE-M3 语义质量更好，但它是 2GB 级模型。我们的选择逻辑：

- MVP 要验证的是**产品闭环**（付费意愿、引用溯源价值），不是检索 SOTA；
- bge-small-zh-v1.5 只有 90MB，实测服务常驻内存 ~144MB（含 torch CPU），低配机器和容器都友好；
- 实测中文合同场景：查"违约金"精准命中第一条违约条款，top1 相似度 0.809；
- 模型名是配置项，质量瓶颈出现时改一行配置切 M3，向量索引自动检测模型变更并重建。

另外踩了一个坑：HuggingFace 的模型加载默认联网校验，在网络受限环境会**无限挂死**。解法是本地缓存优先加载，未缓存时才走镜像（`HF_ENDPOINT=hf-mirror.com`）下载。

---

## 三、代码亮点

### 1. 引用溯源：每一步都为"可验证"服务

引用不是生成的装饰，是贯穿三层的契约：

- **切片层**：每个 chunk 有全局稳定 ID（`{doc_id}-c{seq}`）+ 页码 + 页内字符偏移 + bbox 坐标；
- **生成层**：Prompt 强制模型用 `[来源:chunk_id]` 格式标注；回答返回后跑一遍校验器，**引用的 chunk_id 必须存在于本次检索结果中，编造的一律丢弃**——这是幻觉闸的最后一道防线；
- **前端层**：引用角标点击后用 page + bbox 定位到原文精确位置高亮。

用户点一下就能验证 AI 没有胡说——信任成本降下来，付费才有可能。

### 2. 一键隐私删除：一条命令清干净所有痕迹

删除文档不是 `DELETE` 一行了事，隐私闸连带清理四层：

```python
# 原文件 + SQLite 切片记录 + 对话消息 + 文档元数据（一次事务提交）
# 向量索引文件 + BM25 缓存 + 问答缓存（事务提交后二次清理，避免 SQLite 写锁冲突）
```

这里有个 SQLite 特有的坑：两个会话并发 DELETE 会撞写锁（`database is locked`）。解法是**请求内先提交释放锁，再做检索层清理**，并且给连接加 30s busy timeout。删除后我们用测试逐层断言：文件 0、切片 0、消息 0、向量 0。

### 3. 多轮对话：session 管理在服务端，不在前端

前端只需要带一个 `session_id`（不传则新建并返回），服务端按会话取最近 3 轮问答对拼进 Prompt 窗口。消息全部落库，`GET /api/chat/history` 可完整回放。顺带做了一个成本优化：**相同文档+上下文+问题命中缓存时直接返回且不扣提问额度**（消息仍落库保持历史连贯），高频重复问题不重复付费。

---

## 四、30 秒跑起来

```bash
git clone https://github.com/mahaoboy/wenwen-pdf
cd wenwen-pdf/backend
python3 -m venv .venv && source .venv/bin/activate

# CPU 版 torch（避免拉 800MB CUDA 包）
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt

# 配置（DeepSeek key 选填；不填时问答降级为原文摘录+引用，仍可跑通全流程）
cp .env.example .env

uvicorn app.main:app --port 8000
```

然后：

```bash
# 注册拿 token
curl -X POST localhost:8000/api/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"me@test.dev","password":"pass1234"}'

# 上传一份 PDF → 轮询解析就绪 → 提问（带引用）
curl -X POST localhost:8000/api/documents/upload -H "Authorization: Bearer $TOKEN" -F "file=@合同.pdf"
curl -X POST localhost:8000/api/chat/ask -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"document_id":1,"question":"违约金怎么算？"}'
```

无 LLM Key 时的降级设计值得说一下：回答直接摘录最相关条款原文并标注引用——**宁可诚实地"摘录"，也不编造一句漂亮话**。这也是我们对幻觉问题的基本态度。

---

## 五、写在最后

文问的完整链路（上传 → 解析 → 检索 → 问答 → 溯源 → 删除）目前 24 个测试全绿，端到端联调通过，架构上为三件事留好了口子：向量库迁移（存储层 4 函数抽象）、模型升级（配置切换 + 索引自动重建）、私有化部署（无外部服务依赖）。

接下来的路线：扫描件 OCR 深度优化 → 订阅与额度体系 → API 开放。

如果这个项目对你有参考价值，去 **[github.com/mahaoboy/wenwen-pdf](https://github.com/mahaoboy/wenwen-pdf)** 点个 Star，也欢迎 issue 里拍砖。

---

*文问 WenWen · 上传文档，直接提问，AI 给你带出处的答案。*
