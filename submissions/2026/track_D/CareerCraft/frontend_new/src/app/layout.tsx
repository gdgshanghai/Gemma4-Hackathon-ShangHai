import type { Metadata } from "next";
import AppErrorBoundary from "@/components/common/AppErrorBoundary";
import "./globals.css";

export const metadata: Metadata = {
  title: "CareerCraft - AI 驱动的职业模拟沙盒",
  description:
    "面向计算机系大学生的职业模拟器：完成真实职业任务，接受 AI 同事评审，沉淀作品集与技能树。",
  keywords: "CareerCraft, AI, 职业模拟, 游戏化学习, 像素风",
  openGraph: {
    title: "CareerCraft - AI 驱动的职业模拟沙盒",
    description: "完成真实职业任务，接受 AI 同事评审，沉淀作品集与技能树。",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <head>
        {/* 像素风 Favicon */}
        <link
          rel="icon"
          href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🎮</text></svg>"
        />
      </head>
      <body
        style={{
          fontFamily: "'Press Start 2P', 'VT323', 'Courier New', monospace",
        }}
      >
        <AppErrorBoundary>{children}</AppErrorBoundary>
      </body>
    </html>
  );
}
