import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "文问 WenWen · PDF 文档问答",
  description: "上传 PDF，像聊天一样向文档提问，答案附带原文引用。",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className="min-h-dvh bg-slate-50 font-sans text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
