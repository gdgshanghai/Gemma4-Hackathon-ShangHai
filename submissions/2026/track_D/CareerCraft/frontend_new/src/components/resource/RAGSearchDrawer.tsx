'use client';

import React, { useEffect } from 'react';
import { PixelButton } from '@/components/pixel';
import RAGQueryInsight from './RAGQueryInsight';
import KnowledgeSourceBadge, { KnowledgeSource } from './KnowledgeSourceBadge';
import RAGSearchResultCard, { RAGResource } from './RAGSearchResultCard';

interface RAGSearchDrawerProps {
  open: boolean;
  onClose: () => void;
  taskType?: 'data-analyst' | 'software-engineer';
  isDemoMode?: boolean;
}

const knowledgeSources: KnowledgeSource[] = [
  {
    name: 'CareerCraft 内部任务脚本库',
    hitCount: 5,
    confidence: '高',
    type: '任务脚本库',
  },
  {
    name: '计算机科学学习笔记',
    hitCount: 8,
    confidence: '高',
    type: '笔记库',
  },
  {
    name: '项目案例库',
    hitCount: 3,
    confidence: '中',
    type: '案例库',
  },
];

const dataAnalystResources: RAGResource[] = [
  {
    id: 'da-rag-1',
    title: 'Pandas Groupby Basics',
    type: 'Tutorial',
    relevance: 95,
    hitSnippet: 'groupby helps you aggregate metrics by user type, date, or behavior category.',
    whyRecommend: 'Current task requires comparing activity changes across time periods and user segments.',
    solveProblems: ['Data Grouping', 'Aggregation', 'Multi-dimensional Analysis'],
    tags: ['Pandas', 'Data Processing', 'Aggregation'],
    summary: {
      coreConcept: 'groupby is Pandas core capability for data grouping and aggregation.',
      useCase: 'Suitable for statistical analysis by time, user type, region, channel.',
      howToApply: 'Group by date and user segment, then calculate DAU and retention changes.',
    },
  },
  {
    id: 'da-rag-2',
    title: 'Trend Charts & Anomaly Detection',
    type: 'Example',
    relevance: 92,
    hitSnippet: 'Line charts are perfect for showing metric trends over time.',
    whyRecommend: 'Your report needs to show if activity decline is concentrated in specific time.',
    solveProblems: ['Trend Visualization', 'Time Series', 'Anomaly Detection'],
    tags: ['Matplotlib', 'Visualization', 'Trend'],
    summary: {
      coreConcept: 'Trend charts show metric changes through continuous data points.',
      useCase: 'DAU, conversion rate, completion rate, retention rate analysis.',
      howToApply: 'Plot daily active user chart and mark the sharpest decline points.',
    },
  },
];

const softwareEngineerResources: RAGResource[] = [
  {
    id: 'se-rag-1',
    title: 'Bug Reproduction Template',
    type: 'Template',
    relevance: 94,
    hitSnippet: 'Minimal reproduction path is key for quick bug localization.',
    whyRecommend: 'Current task requires systematic problem reproduction and localization.',
    solveProblems: ['Bug Reproduction', 'Issue Localization', 'Debug Flow'],
    tags: ['Debug', 'Bug', 'Reproduction'],
    summary: {
      coreConcept: 'Minimal reproduction uses fewest steps to reproduce the issue.',
      useCase: 'Complex system defect localization, production issue debugging.',
      howToApply: 'Reproduce locally, narrow down scope, record conditions.',
    },
  },
  {
    id: 'se-rag-2',
    title: 'Log Analysis Methodology',
    type: 'Guide',
    relevance: 91,
    hitSnippet: 'Search keywords and filter by time range to locate anomalies.',
    whyRecommend: 'Your task requires finding exception chains from logs.',
    solveProblems: ['Log Analysis', 'Issue Tracing', 'Anomaly Detection'],
    tags: ['Logs', 'Tracing', 'Monitoring'],
    summary: {
      coreConcept: 'Log analysis focuses on time, keywords, error levels, and request chains.',
      useCase: 'Production issue debugging, system anomaly analysis.',
      howToApply: 'Narrow by error time, search keywords, trace request chain.',
    },
  },
];

export default function RAGSearchDrawer({
  open,
  onClose,
  taskType = 'software-engineer',
  isDemoMode = false,
}: RAGSearchDrawerProps) {
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && open) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  const resources = taskType === 'data-analyst' ? dataAnalystResources : softwareEngineerResources;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 bg-black/70" onClick={onClose} />
      <div
        className="absolute right-0 top-0 h-full w-full max-w-2xl overflow-y-auto border-l-4 border-slate-600 bg-slate-950"
        style={{
          boxShadow:
            'inset -4px -4px 0px 0px #020617, inset 4px 4px 0px 0px #334155, -10px 0 40px rgba(0,0,0,0.55)',
        }}
      >
        <div className="sticky top-0 z-10 border-b-4 border-slate-700 bg-slate-950/95 p-4 backdrop-blur">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="mb-2 inline-flex border-2 border-amber-700 bg-amber-950/60 px-3 py-1 font-mono text-xs font-bold text-amber-200">
                {isDemoMode ? 'MVP FLOW / RAG' : 'CAREER ARCHIVE'}
              </div>
              <h2 className="text-xl font-bold text-amber-300">Knowledge Base Search</h2>
              <p className="mt-2 leading-7 text-slate-400">
                AI Mentor searches Career Island archives for tutorials, cases, and templates relevant to your current task.
              </p>
            </div>
            <button
              onClick={onClose}
              className="flex h-10 w-10 shrink-0 items-center justify-center border-2 border-red-900 bg-red-700 font-bold text-white"
              aria-label="Close knowledge base"
            >
              ×
            </button>
          </div>
        </div>

        <div className="space-y-6 p-4">
          <section>
            <RAGQueryInsight taskType={taskType} />
          </section>

          <section>
            <h3 className="mb-3 text-lg font-bold text-amber-300">Knowledge Sources</h3>
            <div className="space-y-3">
              {knowledgeSources.map((source) => (
                <KnowledgeSourceBadge key={source.name} source={source} />
              ))}
            </div>
          </section>

          <section>
            <h3 className="mb-3 text-lg font-bold text-amber-300">Resource Results</h3>
            <div className="space-y-4">
              {resources.map((resource) => (
                <RAGSearchResultCard key={resource.id} resource={resource} />
              ))}
            </div>
          </section>

          <div className="pb-8">
            <PixelButton variant="secondary" onClick={onClose} fullWidth>
              Return to Task Workspace
            </PixelButton>
          </div>
        </div>
      </div>
    </div>
  );
}