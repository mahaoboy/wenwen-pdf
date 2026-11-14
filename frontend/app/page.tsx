import Link from "next/link";
import { Brand } from "@/components/Brand";

export const metadata = {
  title: "文问 WenWen · 中国版 PDF.ai",
  description:
    "上传 PDF，直接提问，AI 给出带原文引用的答案。开源、本地优先、中文优化的文档智能问答平台。",
};

const GITHUB_URL = "https://github.com/mahaoboy/wenwen-pdf";

const FEATURES = [
  {
    title: "PDF 智能解析",
    description:
      "PyMuPDF + PDFPlumber 提取文本与版面，按段落 / 条款自动切片，保留页码与位置信息。",
    icon: (
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zm0 0v6h6M8 13h8M8 17h5" />
    ),
  },
  {
    title: "混合检索引擎",
    description:
      "BGE 向量语义检索 + BM25 关键词检索，RRF 融合排序，兼顾语义理解与精准匹配。",
    icon: <path d="M21 21l-4.35-4.35M11 19a8 8 0 1 1 0-16 8 8 0 0 1 0 16zM8 11h6M11 8v6" />,
  },
  {
    title: "引用溯源",
    description:
      "每个答案都附带页码与原文片段，点击即可展开核对，从机制上杜绝幻觉。",
    icon: <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />,
  },
  {
    title: "多轮对话",
    description:
      "支持连续追问，后端按会话维护上下文，自动截取最近若干轮，追问不丢线索。",
    icon: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
  },
  {
    title: "一键隐私删除",
    description:
      "删除文档时连带清理切片、向量索引与 BM25 缓存，数据不留痕。",
    icon: (
      <path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M10 11v6M14 11v6" />
    ),
  },
  {
    title: "本地优先架构",
    description:
      "向量存储使用 numpy 本地矩阵，零外部服务依赖，开箱即用，可平滑迁移 Qdrant / PostgreSQL。",
    icon: <path d="M12 2 2 7l10 5 10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />,
  },
];

const STACK = [
  { name: "Next.js 15", role: "前端框架 · App Router" },
  { name: "Tailwind CSS 4", role: "样式系统" },
  { name: "FastAPI", role: "后端框架 · 异步高性能" },
  { name: "SQLAlchemy 2.x", role: "ORM · SQLite / PostgreSQL" },
  { name: "BGE", role: "中文向量化 · bge-small-zh" },
  { name: "BM25", role: "关键词检索 · jieba 分词" },
  { name: "DeepSeek", role: "LLM 生成 · 中文优" },
  { name: "PyMuPDF", role: "PDF 文本与版面提取" },
  { name: "numpy", role: "本地向量矩阵存储" },
  { name: "JWT", role: "轻量认证" },
];

const PIPELINE = [
  { step: "01", title: "上传 PDF", detail: "拖拽上传，自动创建解析任务" },
  { step: "02", title: "解析切片", detail: "提取文本，按段落 / 条款切片" },
  { step: "03", title: "混合检索", detail: "向量 + BM25 双路召回，RRF 融合" },
  { step: "04", title: "生成回答", detail: "Prompt 约束仅基于检索片段作答" },
  { step: "05", title: "引用校验", detail: "引用必须来自真实检索结果" },
];

const BACKEND_CMD = `cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # 填入 DEEPSEEK_API_KEY
uvicorn app.main:app --reload --port 8000`;

const FRONTEND_CMD = `cd frontend
npm install
cp .env.example .env.local
npm run dev
# 打开 http://localhost:3000`;

function Icon({ children }: { children: React.ReactNode }) {
  return (
    <svg
      className="size-5"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

function GithubMark({ className = "size-4" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
      <path d="M12 .5C5.73.5.9 5.33.9 11.6c0 4.9 3.17 9.05 7.57 10.52.55.1.75-.24.75-.53v-2.06c-3.08.67-3.73-1.3-3.73-1.3-.5-1.28-1.23-1.62-1.23-1.62-1-.69.08-.68.08-.68 1.11.08 1.7 1.14 1.7 1.14.98 1.69 2.58 1.2 3.21.92.1-.71.39-1.2.7-1.47-2.46-.28-5.05-1.23-5.05-5.48 0-1.21.43-2.2 1.14-2.98-.11-.28-.5-1.41.11-2.94 0 0 .93-.3 3.05 1.14a10.6 10.6 0 0 1 5.55 0c2.12-1.44 3.05-1.14 3.05-1.14.61 1.53.22 2.66.11 2.94.71.78 1.14 1.77 1.14 2.98 0 4.26-2.6 5.2-5.07 5.47.4.35.76 1.03.76 2.08v3.08c0 .3.2.64.76.53a11.1 11.1 0 0 0 7.56-10.52C23.1 5.33 18.27.5 12 .5z" />
    </svg>
  );
}

export default function LandingPage() {
  return (
    <div className="min-h-dvh bg-white">
      {/* 顶部导航 */}
      <header className="sticky top-0 z-50 border-b border-slate-200/70 bg-white/80 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Brand href="/" />
          <nav className="hidden items-center gap-7 text-sm text-slate-600 md:flex">
            <a href="#features" className="transition hover:text-emerald-600">
              功能特性
            </a>
            <a href="#stack" className="transition hover:text-emerald-600">
              技术架构
            </a>
            <a href="#quickstart" className="transition hover:text-emerald-600">
              快速开始
            </a>
          </nav>
          <div className="flex items-center gap-2">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden items-center gap-2 rounded-xl border border-slate-200 px-3.5 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 sm:inline-flex"
            >
              <GithubMark />
              GitHub
            </a>
            <Link
              href="/login"
              className="rounded-xl bg-emerald-500 px-3.5 py-2 text-sm font-semibold text-white shadow-sm shadow-emerald-500/25 transition hover:bg-emerald-600"
            >
              打开应用
            </Link>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute -top-40 left-1/2 size-[40rem] -translate-x-1/2 rounded-full bg-emerald-100/60 blur-3xl" />
        <div className="pointer-events-none absolute -right-40 top-40 size-96 rounded-full bg-teal-100/50 blur-3xl" />
        <div className="relative mx-auto max-w-6xl px-4 pb-20 pt-16 text-center sm:px-6 sm:pt-24">
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3.5 py-1.5 text-xs font-medium text-emerald-700">
            <span className="size-1.5 rounded-full bg-emerald-500" />
            开源 · MIT License · 本地优先
          </span>
          <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-bold tracking-tight text-slate-900 sm:text-6xl">
            中国版{" "}
            <span className="bg-linear-to-r from-emerald-500 to-teal-600 bg-clip-text text-transparent">
              PDF.ai
            </span>
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-slate-600 sm:text-lg">
            上传 PDF，直接提问。AI 给出带<strong className="font-semibold text-slate-900">原文页码与片段</strong>
            的答案，点击即可核对——让文档问答不再靠猜。
          </p>
          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href={GITHUB_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-slate-900 px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-900/15 transition hover:bg-slate-800 sm:w-auto"
            >
              <GithubMark />
              GitHub Star
            </a>
            <a
              href="#quickstart"
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-6 py-3 text-sm font-semibold text-slate-700 transition hover:border-emerald-300 hover:bg-emerald-50 hover:text-emerald-700 sm:w-auto"
            >
              快速开始
              <svg
                className="size-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M12 5v14m-6-6 6 6 6-6" />
              </svg>
            </a>
          </div>
          <p className="mt-4 text-xs text-slate-400">
            免费版可上传 3 份文档 · 累计提问 20 次 · 无需信用卡
          </p>

          <dl className="mx-auto mt-14 grid max-w-3xl grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              ["100%", "本地索引"],
              ["6 项", "核心能力"],
              ["24 个", "测试用例"],
              ["MIT", "开源协议"],
            ].map(([value, label]) => (
              <div
                key={label}
                className="rounded-2xl border border-slate-200 bg-white/70 px-4 py-4 backdrop-blur"
              >
                <dt className="text-2xl font-bold tracking-tight text-slate-900">
                  {value}
                </dt>
                <dd className="mt-0.5 text-xs text-slate-500">{label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* 功能特性 */}
      <section id="features" className="scroll-mt-24 border-t border-slate-100 py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold text-emerald-600">功能特性</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
              为中文文档问答而生的每一层设计
            </h2>
            <p className="mt-3 text-base leading-relaxed text-slate-600">
              从解析、切片、检索到生成与引用校验，全链路针对中文合同、报告、论文优化。
            </p>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((feature) => (
              <article
                key={feature.title}
                className="group rounded-2xl border border-slate-200 bg-white p-6 transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-lg hover:shadow-emerald-500/5"
              >
                <span className="inline-grid size-11 place-items-center rounded-xl bg-emerald-50 text-emerald-600 transition group-hover:bg-emerald-500 group-hover:text-white">
                  <Icon>{feature.icon}</Icon>
                </span>
                <h3 className="mt-4 text-base font-semibold text-slate-900">
                  {feature.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">
                  {feature.description}
                </p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* 技术架构 */}
      <section
        id="stack"
        className="scroll-mt-24 border-t border-slate-100 bg-slate-50/70 py-20"
      >
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold text-emerald-600">技术架构</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
              全栈开源，零外部服务依赖
            </h2>
            <p className="mt-3 text-base leading-relaxed text-slate-600">
              FastAPI 后端 + Next.js 前端，向量索引与检索全部在本地完成，开箱即用。
            </p>
          </div>

          <div className="mt-10 grid gap-6 lg:grid-cols-[1fr_1.1fr]">
            <ol className="space-y-3">
              {PIPELINE.map((item, index) => (
                <li
                  key={item.step}
                  className="flex items-start gap-4 rounded-2xl border border-slate-200 bg-white p-4"
                >
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-slate-900 text-xs font-bold text-white">
                    {item.step}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900">
                      {item.title}
                    </p>
                    <p className="mt-0.5 text-xs leading-relaxed text-slate-500">
                      {item.detail}
                    </p>
                  </div>
                  {index < PIPELINE.length - 1 && (
                    <span className="ml-auto hidden text-slate-300 sm:block">↓</span>
                  )}
                </li>
              ))}
            </ol>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-2">
              {STACK.map((item) => (
                <div
                  key={item.name}
                  className="rounded-2xl border border-slate-200 bg-white px-4 py-4"
                >
                  <p className="text-sm font-semibold text-slate-900">
                    {item.name}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-slate-500">
                    {item.role}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* 快速开始 */}
      <section id="quickstart" className="scroll-mt-24 border-t border-slate-100 py-20">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold text-emerald-600">快速开始</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
              两条命令，本地跑起来
            </h2>
            <p className="mt-3 text-base leading-relaxed text-slate-600">
              克隆仓库后分别启动后端与前端。国内下载 Embedding 模型前可先设置
              <code className="mx-1 rounded bg-slate-100 px-1.5 py-0.5 text-[13px] text-slate-700">
                HF_ENDPOINT=https://hf-mirror.com
              </code>
              。
            </p>
          </div>

          <div className="mt-10 grid gap-4 lg:grid-cols-2">
            {[
              { label: "后端 · FastAPI", cmd: BACKEND_CMD, port: ":8000" },
              { label: "前端 · Next.js", cmd: FRONTEND_CMD, port: ":3000" },
            ].map((block) => (
              <div
                key={block.label}
                className="overflow-hidden rounded-2xl border border-slate-800 bg-slate-900 shadow-xl shadow-slate-900/10"
              >
                <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                  <span className="text-xs font-medium text-slate-300">
                    {block.label}
                  </span>
                  <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
                    <span className="size-2 rounded-full bg-rose-400/80" />
                    <span className="size-2 rounded-full bg-amber-400/80" />
                    <span className="size-2 rounded-full bg-emerald-400/80" />
                  </span>
                </div>
                <pre className="overflow-x-auto px-4 py-4 text-[13px] leading-relaxed text-emerald-200/90">
                  <code>{block.cmd}</code>
                </pre>
              </div>
            ))}
          </div>

          <div className="mt-8 flex flex-col items-center justify-between gap-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-6 py-5 sm:flex-row">
            <div>
              <p className="text-sm font-semibold text-emerald-900">
                已经跑起来了？
              </p>
              <p className="mt-0.5 text-sm text-emerald-700/80">
                注册账号，上传第一份 PDF，开始向文档提问。
              </p>
            </div>
            <Link
              href="/login"
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-700"
            >
              打开文问
              <svg
                className="size-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M5 12h14m-6-6 6 6-6 6" />
              </svg>
            </Link>
          </div>
        </div>
      </section>

      {/* 页脚 */}
      <footer className="border-t border-slate-200 bg-slate-50">
        <div className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
          <div className="flex flex-col items-start justify-between gap-6 sm:flex-row sm:items-center">
            <div>
              <Brand href="/" />
              <p className="mt-2 max-w-md text-sm text-slate-500">
                面向中国专业工作者的文档智能问答平台。上传 PDF，直接提问，答案附带出处。
              </p>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <a
                href={GITHUB_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-2 text-slate-600 transition hover:text-emerald-600"
              >
                <GithubMark />
                mahaoboy/wenwen-pdf
              </a>
              <Link
                href="/login"
                className="text-slate-600 transition hover:text-emerald-600"
              >
                登录
              </Link>
            </div>
          </div>
          <div className="mt-8 flex flex-col items-start justify-between gap-2 border-t border-slate-200 pt-6 text-xs text-slate-400 sm:flex-row sm:items-center">
            <p>© 2026 文问 WenWen · MIT License</p>
            <p>
              作者{" "}
              <a
                href="https://github.com/mahaoboy"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-slate-500 transition hover:text-emerald-600"
              >
                mahaoboy
              </a>{" "}
              · 用中文文档问答，从文问开始
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
