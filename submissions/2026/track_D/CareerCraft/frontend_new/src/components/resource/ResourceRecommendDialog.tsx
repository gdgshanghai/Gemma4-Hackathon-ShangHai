'use client';

import React, { useState } from 'react';
import { PixelBadge, PixelButton, PixelDialog } from '@/components/pixel';
import { getRecommendResources } from '@/data/resources';
import RAGSearchDrawer from './RAGSearchDrawer';

interface ResourceRecommendDialogProps {
  open: boolean;
  onClose: () => void;
  taskType?: 'data-analyst' | 'software-engineer';
}

export default function ResourceRecommendDialog({
  open,
  onClose,
  taskType = 'software-engineer',
}: ResourceRecommendDialogProps) {
  const resources = getRecommendResources(taskType).slice(0, 4);
  const [showRAGDrawer, setShowRAGDrawer] = useState(false);

  const handleOpenRAGSearch = () => {
    onClose();
    setShowRAGDrawer(true);
  };

  return (
    <>
      <PixelDialog open={open} onClose={onClose} title="推荐资源">
        <div className="space-y-5">
          <div className="border-2 border-amber-700 bg-amber-950/30 p-4">
            <div className="mb-2 font-mono text-xs font-bold text-amber-300">CAREER ARCHIVE</div>
            <p className="leading-7 text-slate-300">
              这些资料会帮助你把任务从“看懂题目”推进到“能交付成果”。需要更精确的上下文，可以进入 RAG 资料馆继续检索。
            </p>
          </div>

          <PixelButton variant="primary" onClick={handleOpenRAGSearch} fullWidth>
            进入 RAG 资料馆
          </PixelButton>

          {resources.length === 0 ? (
            <div className="border-2 border-slate-700 bg-slate-950 p-8 text-center text-slate-400">
              暂无推荐资源
            </div>
          ) : (
            <div className="space-y-3">
              {resources.map((resource) => (
                <div
                  key={resource.id}
                  className="border-2 border-slate-700 bg-slate-950 p-4 transition-all hover:translate-x-1 hover:border-amber-500"
                  style={{
                    boxShadow: 'inset -2px -2px 0px 0px #020617, inset 2px 2px 0px 0px #334155',
                  }}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center border-2 border-amber-700 bg-slate-900 font-mono text-xs font-bold text-amber-300">
                      DOC
                    </div>
                    <div className="min-w-0 flex-1">
                      <h4 className="font-bold text-slate-100">{resource.title}</h4>
                      <p className="mt-1 leading-7 text-slate-400">{resource.summary}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <PixelBadge variant="neutral" className="text-xs">
                          {resource.type}
                        </PixelBadge>
                        {resource.relevance ? (
                          <PixelBadge variant="fun" className="text-xs">
                            相关度 {resource.relevance}%
                          </PixelBadge>
                        ) : null}
                      </div>
                    </div>
                    <span className="font-mono text-amber-400">›</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </PixelDialog>

      <RAGSearchDrawer open={showRAGDrawer} onClose={() => setShowRAGDrawer(false)} taskType={taskType} />
    </>
  );
}
