# UI 重做实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 Tailwind CSS + shadcn/ui 重做前端，从"玩具界面"升级为"产品级界面"。

**Architecture:** 安装 Tailwind + shadcn/ui 基础设施 → 逐页重写组件（Landing → Onboarding → MainApp）→ 删除旧 CSS。

**Tech Stack:** Tailwind CSS v4 / shadcn/ui (React) / Radix UI / Lucide Icons / clsx + tailwind-merge

---

### Task 1: 安装 Tailwind CSS + shadcn/ui 基础设施

**Files:**
- Modify: `apps/web/package.json` (新增依赖)
- Modify: `apps/web/vite.config.ts` (Tailwind 插件)
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/postcss.config.js`
- Create: `apps/web/src/lib/utils.ts` (cn 函数)
- Modify: `apps/web/src/styles.css` (Tailwind 指令替换)

- [ ] **Step 1: 安装依赖**

```bash
cd apps/web
pnpm add -D tailwindcss @tailwindcss/vite
pnpm add clsx tailwind-merge class-variance-authority lucide-react
pnpm add @radix-ui/react-dialog @radix-ui/react-slot @radix-ui/react-tabs @radix-ui/react-progress @radix-ui/react-tooltip
```

- [ ] **Step 2: 配置 vite.config.ts**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8001',
    },
  },
})
```

- [ ] **Step 3: 替换 styles.css**

将 `apps/web/src/styles.css` 的全部内容替换为：

```css
@import "tailwindcss";

/* 自定义主题变量 */
@theme {
  --color-primary: #f97316;
  --color-primary-foreground: #ffffff;
  --color-secondary: #f1f5f9;
  --color-secondary-foreground: #0f172a;
  --color-accent: #f97316;
  --color-accent-foreground: #ffffff;
  --color-destructive: #ef4444;
  --color-muted: #f1f5f9;
  --color-muted-foreground: #64748b;
  --color-card: #ffffff;
  --color-card-foreground: #0f172a;
  --color-border: #e2e8f0;
  --color-ring: #f97316;
  --radius-sm: 0.375rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
}

/* 全局基础 */
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background-color: #f8fafc;
  color: #0f172a;
}
```

- [ ] **Step 4: 创建 utils.ts**

创建 `apps/web/src/lib/utils.ts`：

```typescript
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

- [ ] **Step 5: Commit**

```bash
git add apps/web/
git commit -m "chore: 安装 Tailwind CSS + shadcn/ui 基础设施"
```

---

### Task 2: 创建 shadcn/ui 基础组件

**Files:**
- Create: `apps/web/src/components/ui/button.tsx`
- Create: `apps/web/src/components/ui/card.tsx`
- Create: `apps/web/src/components/ui/input.tsx`
- Create: `apps/web/src/components/ui/textarea.tsx`
- Create: `apps/web/src/components/ui/badge.tsx`
- Create: `apps/web/src/components/ui/dialog.tsx`
- Create: `apps/web/src/components/ui/progress.tsx`
- Create: `apps/web/src/components/ui/tabs.tsx`

这些是 shadcn/ui 标准组件，直接从 shadcn/ui 官方复制。每个组件约 30-60 行，使用 Radix UI 原语 + Tailwind 样式 + CVA (class-variance-authority) 变体。

- [ ] **Step 1: 创建 button.tsx**

```tsx
import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-white hover:bg-destructive/90",
        outline: "border border-border bg-white hover:bg-accent hover:text-accent-foreground",
        secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
```

- [ ] **Step 2: 创建 card.tsx**

```tsx
import * as React from "react"
import { cn } from "@/lib/utils"

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("rounded-lg border border-border bg-card text-card-foreground shadow-sm", className)} {...props} />
  )
)
Card.displayName = "Card"

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
  )
)
CardHeader.displayName = "CardHeader"

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-2xl font-semibold leading-none tracking-tight", className)} {...props} />
  )
)
CardTitle.displayName = "CardTitle"

const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
  )
)
CardDescription.displayName = "CardDescription"

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
  )
)
CardContent.displayName = "CardContent"

const CardFooter = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex items-center p-6 pt-0", className)} {...props} />
  )
)
CardFooter.displayName = "CardFooter"

export { Card, CardHeader, CardFooter, CardTitle, CardDescription, CardContent }
```

- [ ] **Step 3: 创建 badge.tsx**

```tsx
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground hover:bg-primary/80",
        secondary: "border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",
        destructive: "border-transparent bg-destructive text-white hover:bg-destructive/80",
        outline: "text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
```

- [ ] **Step 4: 创建 progress.tsx**

```tsx
import * as React from "react"
import * as ProgressPrimitive from "@radix-ui/react-progress"
import { cn } from "@/lib/utils"

const Progress = React.forwardRef<
  React.ElementRef<typeof ProgressPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ProgressPrimitive.Root>
>(({ className, value, ...props }, ref) => (
  <ProgressPrimitive.Root
    ref={ref}
    className={cn("relative h-4 w-full overflow-hidden rounded-full bg-secondary", className)}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className="h-full w-full flex-1 bg-primary transition-all"
      style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
    />
  </ProgressPrimitive.Root>
))
Progress.displayName = ProgressPrimitive.Root.displayName

export { Progress }
```

- [ ] **Step 5: 创建 tabs.tsx**

```tsx
import * as React from "react"
import * as TabsPrimitive from "@radix-ui/react-tabs"
import { cn } from "@/lib/utils"

const Tabs = TabsPrimitive.Root

const TabsList = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.List>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.List
    ref={ref}
    className={cn("inline-flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground", className)}
    {...props}
  />
))
TabsList.displayName = TabsPrimitive.List.displayName

const TabsTrigger = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Trigger
    ref={ref}
    className={cn("inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-white data-[state=active]:text-foreground data-[state=active]:shadow-sm", className)}
    {...props}
  />
))
TabsTrigger.displayName = TabsPrimitive.Trigger.displayName

const TabsContent = React.forwardRef<
  React.ElementRef<typeof TabsPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>
>(({ className, ...props }, ref) => (
  <TabsPrimitive.Content
    ref={ref}
    className={cn("mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2", className)}
    {...props}
  />
))
TabsContent.displayName = TabsPrimitive.Content.displayName

export { Tabs, TabsList, TabsTrigger, TabsContent }
```

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/ui/ apps/web/src/lib/
git commit -m "chore: 创建 shadcn/ui 基础组件 (button/card/badge/progress/tabs)"
```

---

### Task 3: 重写 Landing 页 (ModeSelectionLanding)

**Files:**
- Rewrite: `apps/web/src/components/ModeSelectionLanding.tsx`

用 Tailwind + shadcn Card/Button 重写首页。设计方向：
- 居中布局，渐变背景
- 两张大卡片，hover 动效
- 底部小字安全声明

```tsx
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card'
import { Button } from './ui/button'

interface ModeSelectionLandingProps {
  onSelectMode: (mode: 'long_term' | 'quick') => void
}

export function ModeSelectionLanding({ onSelectMode }: ModeSelectionLandingProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-amber-50 flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-3">🍔 EatOrNot</h1>
          <p className="text-lg text-gray-500">你的智能饮食决策助手</p>
        </div>

        {/* Mode Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card
            className="cursor-pointer hover:shadow-lg hover:-translate-y-1 transition-all duration-200 border-orange-200"
            onClick={() => onSelectMode('long_term')}
          >
            <CardHeader>
              <div className="text-4xl mb-2">📊</div>
              <CardTitle className="text-xl">长期管理我的饮食</CardTitle>
              <CardDescription>建立个人档案，追踪体重、预算、营养目标</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-gray-600 mb-6">
                <li className="flex items-center gap-2"><span className="text-orange-500">✓</span> 设定减脂/增肌/维持目标</li>
                <li className="flex items-center gap-2"><span className="text-orange-500">✓</span> 追踪每日热量和预算</li>
                <li className="flex items-center gap-2"><span className="text-orange-500">✓</span> 记录用餐历史</li>
                <li className="flex items-center gap-2"><span className="text-orange-500">✓</span> 个性化推荐</li>
              </ul>
              <Button className="w-full" size="lg">开始建档</Button>
            </CardContent>
          </Card>

          <Card
            className="cursor-pointer hover:shadow-lg hover:-translate-y-1 transition-all duration-200 border-amber-200"
            onClick={() => onSelectMode('quick')}
          >
            <CardHeader>
              <div className="text-4xl mb-2">⚡</div>
              <CardTitle className="text-xl">就这顿帮我选一下</CardTitle>
              <CardDescription>快速选择，无需注册，30秒搞定</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2 text-sm text-gray-600 mb-6">
                <li className="flex items-center gap-2"><span className="text-amber-500">✓</span> 告诉我你的预算和心情</li>
                <li className="flex items-center gap-2"><span className="text-amber-500">✓</span> 3个方案即刻呈现</li>
                <li className="flex items-center gap-2"><span className="text-amber-500">✓</span> 无需建档</li>
                <li className="flex items-center gap-2"><span className="text-amber-500">✓</span> 快速下单</li>
              </ul>
              <Button variant="outline" className="w-full border-amber-300 text-amber-700 hover:bg-amber-50" size="lg">快速选择</Button>
            </CardContent>
          </Card>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-gray-400 mt-8">
          ⚕️ 本工具仅供参考，不构成医疗建议。如有特殊饮食需求请咨询医生。
        </p>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/ModeSelectionLanding.tsx
git commit -m "feat: 重写 Landing 页 (Tailwind + shadcn Card)"
```

---

### Task 4: 重写建档表单 (ProfileOnboardingForm + QuickProfileForm)

**Files:**
- Rewrite: `apps/web/src/components/ProfileOnboardingForm.tsx`
- Rewrite: `apps/web/src/components/QuickProfileForm.tsx`

用 Tailwind + shadcn Card/Button/Input 重写表单。设计方向：
- 分步表单（基本信息 → 目标设定 → 饮食偏好）
- 进度条显示步骤
- 表单验证更友好

注意：这两个组件的 props 接口不变（onComplete 回调），只是 UI 重写。保留原有的状态逻辑和数据提交逻辑。

- [ ] **Step 1: 重写 ProfileOnboardingForm** - 用 Tailwind 样式替换所有 className，用 shadcn Card/Button/Input，添加分步进度条
- [ ] **Step 2: 重写 QuickProfileForm** - 用 Tailwind 样式，更简洁的快速表单布局
- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/ProfileOnboardingForm.tsx apps/web/src/components/QuickProfileForm.tsx
git commit -m "feat: 重写建档表单 (Tailwind + shadcn, 分步进度条)"
```

---

### Task 5: 重写主应用布局 (App.tsx + header + sidebar)

**Files:**
- Rewrite: `apps/web/src/App.tsx` (主布局部分)

设计方向：
- 顶部导航栏：品牌名 + 模式标签 + ProviderBadge + 重置按钮
- 三栏布局：左侧仪表盘 | 中间对话/推荐 | 右侧（可选）
- 所有 Tailwind class 替换旧 className
- 响应式：移动端折叠 sidebar

App.tsx 的状态逻辑和事件处理不变，只改 JSX 和 className。

- [ ] **Step 1: 重写 App.tsx 布局** - header 用 flex + gap，sidebar 用 sticky + overflow，main 用 flex-1
- [ ] **Step 2: Commit**

```bash
git add apps/web/src/App.tsx
git commit -m "feat: 重写主应用布局 (Tailwind 三栏响应式)"
```

---

### Task 6: 重写核心交互组件

**Files:**
- Rewrite: `apps/web/src/components/RecommendationCard.tsx`
- Rewrite: `apps/web/src/components/RoundTableDebate.tsx`
- Rewrite: `apps/web/src/components/ActivePlanPanel.tsx`
- Rewrite: `apps/web/src/components/OrderConfirmModal.tsx`

设计方向：
- RecommendationCard: shadcn Card + Badge，更清晰的方案对比
- RoundTableDebate: shadcn Tabs 替换手动 tab 切换，Agent 头像色彩区分
- ActivePlanPanel: 精炼输入 + 营养进度条 (shadcn Progress)
- OrderConfirmModal: shadcn Dialog 替换自定义 modal

Props 接口保持不变。

- [ ] **Step 1: 重写 RecommendationCard** - Card + Badge + 渐变边框
- [ ] **Step 2: 重写 RoundTableDebate** - Tabs + Agent 颜色标识
- [ ] **Step 3: 重写 ActivePlanPanel** - Card + Progress + 输入区
- [ ] **Step 4: 重写 OrderConfirmModal** - Dialog + 列表 + 按钮
- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/RecommendationCard.tsx apps/web/src/components/RoundTableDebate.tsx apps/web/src/components/ActivePlanPanel.tsx apps/web/src/components/OrderConfirmModal.tsx
git commit -m "feat: 重写核心交互组件 (shadcn Card/Tabs/Dialog/Progress)"
```

---

### Task 7: 重写辅助组件

**Files:**
- Rewrite: `apps/web/src/components/TodayDashboard.tsx`
- Rewrite: `apps/web/src/components/ReminderCard.tsx`
- Rewrite: `apps/web/src/components/AutoDraft.tsx`
- Rewrite: `apps/web/src/components/BudgetBar.tsx`
- Rewrite: `apps/web/src/components/NutritionBalancePanel.tsx`
- Rewrite: `apps/web/src/components/SafetyBanner.tsx`
- Rewrite: `apps/web/src/components/ProfileCard.tsx`
- Rewrite: `apps/web/src/components/BalanceMode.tsx`
- Rewrite: `apps/web/src/components/LearningPanel.tsx`
- Rewrite: `apps/web/src/components/MetricsPanel.tsx`
- Rewrite: `apps/web/src/components/ProviderBadge.tsx`
- Rewrite: `apps/web/src/components/ResetButtons.tsx`

这些组件较简单，主要是 Card + Badge + Progress 的组合。用 Tailwind 替换 className。

- [ ] **Step 1: 批量重写所有辅助组件** - 保持 props 不变，Tailwind 样式替换
- [ ] **Step 2: Commit**

```bash
git add apps/web/src/components/
git commit -m "feat: 重写辅助组件 (Tailwind + shadcn)"
```

---

### Task 8: 清理 + 构建验证

**Files:**
- Verify: `apps/web/src/styles.css` (只保留 Tailwind 指令)
- Verify: 所有组件编译通过

- [ ] **Step 1: 删除 styles.css 中残留的旧样式** - 只保留 `@import "tailwindcss"` 和自定义变量
- [ ] **Step 2: 构建验证**
```bash
cd apps/web && pnpm build
```
修复所有 TypeScript 编译错误。

- [ ] **Step 3: 视觉验证** - 启动 dev server，逐页检查
- [ ] **Step 4: Commit + Push**

```bash
git add -A
git commit -m "chore: 清理旧CSS，完成 UI 重做"
git push origin feat/ui-and-agent-experience
```

---

## 依赖关系

```
Task 1 (基础设施) → Task 2 (shadcn组件) → Task 3 (Landing)
                                     → Task 4 (表单)
                                     → Task 5 (主布局)
                                     → Task 6 (核心组件)
                                     → Task 7 (辅助组件)
Task 3-7 可并行但建议顺序执行（共享样式约定）
→ Task 8 (清理验证)
```
