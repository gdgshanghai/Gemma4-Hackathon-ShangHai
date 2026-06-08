# shadcn/ui 组件参考

> 本项目已安装的 shadcn 组件清单，所有组件从 `@/components/ui/<name>` 导入。

## 目录

- [Button](#button) — 按钮
- [Badge](#badge) — 徽章/标签
- [Card](#card) — 卡片容器
- [Dialog](#dialog) — 模态对话框
- [DropdownMenu](#dropdownmenu) — 下拉菜单
- [Input](#input) — 文本输入
- [InputGroup](#inputgroup) — 输入框组（带前后缀）
- [Textarea](#textarea) — 多行文本
- [Select](#select) — 下拉选择
- [Tabs](#tabs) — 选项卡
- [Sheet](#sheet) — 侧边面板
- [Tooltip](#tooltip) — 悬浮提示
- [Popover](#popover) — 弹出气泡
- [Command](#command) — 命令面板/搜索
- [Toggle](#toggle) — 开关按钮
- [ToggleGroup](#togglegroup) — 开关组
- [ScrollArea](#scrollarea) — 可滚动区域
- [Separator](#separator) — 分隔线

---

## Button

**导入**: `import { Button } from "@/components/ui/button"`

**Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `variant` | `"default" \| "outline" \| "secondary" \| "ghost" \| "destructive" \| "link"` | `"default"` | 按钮风格 |
| `size` | `"default" \| "xs" \| "sm" \| "lg" \| "icon" \| "icon-xs" \| "icon-sm" \| "icon-lg"` | `"default"` | 按钮尺寸 |
| `asChild` | `boolean` | `false` | 渲染为 Slot（包裹自定义元素） |

**示例**:
```tsx
<Button variant="default" size="default">保存</Button>
<Button variant="outline" size="sm">取消</Button>
<Button variant="ghost" size="icon"><Settings /></Button>
<Button variant="destructive" size="xs">删除</Button>
```

---

## Badge

**导入**: `import { Badge } from "@/components/ui/badge"`

**Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `variant` | `"default" \| "secondary" \| "destructive" \| "outline" \| "ghost" \| "link"` | `"default"` | 徽章风格 |
| `asChild` | `boolean` | `false` | 渲染为 Slot |

**示例**:
```tsx
<Badge>默认</Badge>
<Badge variant="secondary">次要</Badge>
<Badge variant="destructive">错误</Badge>
<Badge variant="outline">轮廓</Badge>
```

---

## Card

**导入**: `import { Card, CardHeader, CardContent, CardFooter, CardTitle, CardDescription, CardAction } from "@/components/ui/card"`

**Card Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `size` | `"default" \| "sm"` | `"default"` | 卡片尺寸 |

**子组件**: `CardHeader`, `CardTitle`, `CardDescription`, `CardAction`, `CardContent`, `CardFooter`

**示例**:
```tsx
<Card>
  <CardHeader>
    <CardTitle>标题</CardTitle>
    <CardDescription>描述文字</CardDescription>
    <CardAction><Button size="icon-sm" variant="ghost"><Settings /></Button></CardAction>
  </CardHeader>
  <CardContent>内容区域</CardContent>
  <CardFooter>底部操作</CardFooter>
</Card>
```

---

## Dialog

**导入**: `import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogDescription, DialogClose } from "@/components/ui/dialog"`

**DialogContent Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `showCloseButton` | `boolean` | `true` | 是否显示关闭按钮 |

**DialogFooter Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `showCloseButton` | `boolean` | `false` | 是否显示底部"Close"按钮 |

**示例**:
```tsx
<Dialog>
  <DialogTrigger asChild>
    <Button>打开对话框</Button>
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>确认操作</DialogTitle>
      <DialogDescription>此操作不可撤销。</DialogDescription>
    </DialogHeader>
    <DialogFooter showCloseButton>
      <Button variant="destructive">确认删除</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

---

## DropdownMenu

**导入**: `import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuLabel, DropdownMenuGroup, DropdownMenuSub, DropdownMenuSubTrigger, DropdownMenuSubContent, DropdownMenuCheckboxItem, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuShortcut } from "@/components/ui/dropdown-menu"`

**DropdownMenuItem Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `variant` | `"default" \| "destructive"` | `"default"` | 菜单项风格 |
| `inset` | `boolean` | `false` | 左边距缩进 |

**DropdownMenuContent Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `align` | `"start" \| "center" \| "end"` | `"start"` | 对齐方式 |
| `sideOffset` | `number` | `4` | 触发元素间距 |

**示例**:
```tsx
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="outline">操作</Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent>
    <DropdownMenuLabel>操作菜单</DropdownMenuLabel>
    <DropdownMenuSeparator />
    <DropdownMenuItem>编辑</DropdownMenuItem>
    <DropdownMenuItem>复制</DropdownMenuItem>
    <DropdownMenuSeparator />
    <DropdownMenuItem variant="destructive">删除</DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

---

## Input

**导入**: `import { Input } from "@/components/ui/input"`

标准 `<input>` 所有原生属性均支持，已预置 shadcn 样式。

**示例**:
```tsx
<Input type="text" placeholder="输入文字..." />
<Input type="email" placeholder="email@example.com" />
<Input type="password" />
```

---

## InputGroup

**导入**: `import { InputGroup, InputGroupInput, InputGroupAddon, InputGroupButton, InputGroupText, InputGroupTextarea } from "@/components/ui/input-group"`

**InputGroupAddon Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `align` | `"inline-start" \| "inline-end" \| "block-start" \| "block-end"` | `"inline-start"` | 附加元素位置 |

**InputGroupButton Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `size` | `"xs" \| "sm" \| "icon-xs" \| "icon-sm"` | `"xs"` | 按钮尺寸 |
| `variant` | Button variant | `"ghost"` | 按钮风格 |

**示例**:
```tsx
// 搜索框
<InputGroup>
  <InputGroupInput placeholder="搜索..." />
  <InputGroupAddon align="inline-end">
    <SearchIcon className="size-4" />
  </InputGroupAddon>
</InputGroup>

// 带按钮的输入框
<InputGroup>
  <InputGroupInput placeholder="输入 URL" />
  <InputGroupAddon align="inline-end">
    <InputGroupButton>提交</InputGroupButton>
  </InputGroupAddon>
</InputGroup>
```

---

## Textarea

**导入**: `import { Textarea } from "@/components/ui/textarea"`

标准 `<textarea>` 所有原生属性均支持，已预置 shadcn 样式。

---

## Select

**导入**: `import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem, SelectGroup, SelectLabel, SelectSeparator } from "@/components/ui/select"`

**SelectTrigger Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `size` | `"sm" \| "default"` | `"default"` | 触发器尺寸 |

**示例**:
```tsx
<Select>
  <SelectTrigger>
    <SelectValue placeholder="选择主题" />
  </SelectTrigger>
  <SelectContent>
    <SelectGroup>
      <SelectLabel>主题</SelectLabel>
      <SelectItem value="light">浅色</SelectItem>
      <SelectItem value="dark">深色</SelectItem>
      <SelectItem value="system">跟随系统</SelectItem>
    </SelectGroup>
  </SelectContent>
</Select>
```

---

## Tabs

**导入**: `import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"`

**Tabs Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `orientation` | `"horizontal" \| "vertical"` | `"horizontal"` | 选项卡方向 |

**TabsList Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `variant` | `"default" \| "line"` | `"default"` | 选项卡风格 |

**示例**:
```tsx
<Tabs defaultValue="tab1">
  <TabsList>
    <TabsTrigger value="tab1">选项卡 1</TabsTrigger>
    <TabsTrigger value="tab2">选项卡 2</TabsTrigger>
  </TabsList>
  <TabsContent value="tab1">内容 1</TabsContent>
  <TabsContent value="tab2">内容 2</TabsContent>
</Tabs>
```

**常见模式 — 单 tab 药丸（如 Live Tab）**:
- `TabsList` 保持默认（去掉 `w-full`），使用 `inline-flex w-fit`，灰色药丸容器只包裹内容
- `TabsTrigger` 本身有 `flex-1`，在 `w-fit` 容器下自动取内容宽度
- 需要加宽白色药丸时，给 `TabsTrigger` 加 `min-w-[...]`，文字保持居中不变形

```tsx
// ✅ 单 tab 紧凑药丸，白色药丸宽度约三倍于内容
<TabsList>
  <TabsTrigger value="live" className="min-w-[9rem]">Live</TabsTrigger>
</TabsList>

// ✅ 多 tab 均分药丸，灰色容器贯穿卡片
<TabsList className="w-full">
  <TabsTrigger value="script">剧本</TabsTrigger>
  <TabsTrigger value="history">History</TabsTrigger>
</TabsList>
```

---

## Sheet

**导入**: `import { Sheet, SheetTrigger, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter, SheetClose } from "@/components/ui/sheet"`

**SheetContent Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `side` | `"top" \| "right" \| "bottom" \| "left"` | `"right"` | 滑出方向 |
| `showCloseButton` | `boolean` | `true` | 是否显示关闭按钮 |

**示例**:
```tsx
<Sheet>
  <SheetTrigger asChild>
    <Button variant="outline">打开面板</Button>
  </SheetTrigger>
  <SheetContent side="right">
    <SheetHeader>
      <SheetTitle>面板标题</SheetTitle>
      <SheetDescription>面板描述</SheetDescription>
    </SheetHeader>
    <div>内容区域</div>
    <SheetFooter>
      <Button>保存</Button>
    </SheetFooter>
  </SheetContent>
</Sheet>
```

---

## Tooltip

**导入**: `import { TooltipProvider, Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip"`

**TooltipProvider Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `delayDuration` | `number` | `0` | 延迟显示毫秒数 |

**示例**:
```tsx
<TooltipProvider>
  <Tooltip>
    <TooltipTrigger asChild>
      <Button variant="ghost" size="icon"><HelpCircle /></Button>
    </TooltipTrigger>
    <TooltipContent>
      帮助说明文字
    </TooltipContent>
  </Tooltip>
</TooltipProvider>
```

---

## Popover

**导入**: `import { Popover, PopoverTrigger, PopoverContent, PopoverHeader, PopoverTitle, PopoverDescription } from "@/components/ui/popover"`

**示例**:
```tsx
<Popover>
  <PopoverTrigger asChild>
    <Button variant="outline">打开气泡</Button>
  </PopoverTrigger>
  <PopoverContent>
    <PopoverHeader>
      <PopoverTitle>气泡标题</PopoverTitle>
      <PopoverDescription>气泡描述</PopoverDescription>
    </PopoverHeader>
  </PopoverContent>
</Popover>
```

---

## Command

**导入**: `import { Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem, CommandShortcut, CommandSeparator } from "@/components/ui/command"`

**示例**:
```tsx
<Command>
  <CommandInput placeholder="搜索..." />
  <CommandList>
    <CommandEmpty>无结果</CommandEmpty>
    <CommandGroup heading="建议">
      <CommandItem>选项 1<CommandShortcut>⌘1</CommandShortcut></CommandItem>
      <CommandItem>选项 2<CommandShortcut>⌘2</CommandShortcut></CommandItem>
    </CommandGroup>
  </CommandList>
</Command>
```

---

## Toggle

**导入**: `import { Toggle } from "@/components/ui/toggle"`

**Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `variant` | `"default" \| "outline"` | `"default"` | 开关风格 |
| `size` | `"default" \| "sm" \| "lg"` | `"default"` | 开关尺寸 |

---

## ToggleGroup

**导入**: `import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"`

**ToggleGroup Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `variant` | `"default" \| "outline"` | `"default"` | 开关组风格 |
| `size` | `"default" \| "sm" \| "lg"` | `"default"` | 开关尺寸 |
| `spacing` | `number` | `2` | 元素间距 |
| `orientation` | `"horizontal" \| "vertical"` | `"horizontal"` | 排列方向 |

---

## ScrollArea

**导入**: `import { ScrollArea } from "@/components/ui/scroll-area"`

**示例**:
```tsx
<ScrollArea className="h-64">
  <div>很长的内容...</div>
</ScrollArea>
```

---

## Separator

**导入**: `import { Separator } from "@/components/ui/separator"`

**Props**:
| Prop | 类型 | 默认值 | 说明 |
|---|---|---|---|
| `orientation` | `"horizontal" \| "vertical"` | `"horizontal"` | 分隔线方向 |
| `decorative` | `boolean` | `true` | 纯装饰（跳过无障碍） |

---

## 工具函数

```tsx
import { cn } from "@/lib/utils"
// 用法：cn("base-class", condition && "conditional-class", className)
```
