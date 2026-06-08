import React, { useState } from 'react';
import { PixelBadge } from '@/components/pixel';

interface DeliverableItem {
  id: string;
  title: string;
  type: 'required' | 'suggested' | 'bonus';
}

const DEFAULT_DELIVERABLES: DeliverableItem[] = [
  { id: 'd1', title: '任务完成说明文档', type: 'required' },
  { id: 'd2', title: '核心问题解决方案', type: 'required' },
  { id: 'd3', title: '思考过程记录', type: 'required' },
  { id: 'd4', title: '截图、代码片段或分析图表', type: 'suggested' },
  { id: 'd5', title: '额外优化建议', type: 'suggested' },
  { id: 'd6', title: '相关资源和参考链接', type: 'bonus' },
];

export default function MissionDeliverableBoard() {
  const [checkedItems, setCheckedItems] = useState<Set<string>>(new Set());

  const toggleItem = (id: string) => {
    const next = new Set(checkedItems);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setCheckedItems(next);
  };

  return (
    <section className="border-2 border-slate-700 bg-slate-950/86 p-5 backdrop-blur-sm">
      <div className="mb-5">
        <div className="font-mono text-xs uppercase tracking-[0.22em] text-emerald-300">Deliverables</div>
        <h2 className="mt-2 text-xl font-bold text-amber-300">交付物清单</h2>
        <p className="mt-2 text-sm text-slate-400">勾选清单，确认你的提交足够完整。</p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {DEFAULT_DELIVERABLES.map((item) => {
          const checked = checkedItems.has(item.id);
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => toggleItem(item.id)}
              className="flex items-center gap-3 border border-slate-700 bg-slate-900/56 p-3 text-left transition hover:border-amber-500"
            >
              <span className={`h-6 w-6 shrink-0 border-2 ${checked ? 'border-emerald-400 bg-emerald-500/30' : 'border-slate-600 bg-slate-950'}`} />
              <span className={`flex-1 text-sm ${checked ? 'text-slate-500 line-through' : 'text-slate-300'}`}>
                {item.title}
              </span>
              <PixelBadge variant={item.type === 'required' ? 'warning' : item.type === 'bonus' ? 'success' : 'neutral'}>
                {typeLabel(item.type)}
              </PixelBadge>
            </button>
          );
        })}
      </div>
    </section>
  );
}

function typeLabel(type: DeliverableItem['type']) {
  if (type === 'required') return '必交';
  if (type === 'suggested') return '建议';
  return '加分';
}
