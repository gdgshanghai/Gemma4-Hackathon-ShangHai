'use client';

import React, { useState } from 'react';
import { PixelBadge, PixelButton, PixelCard, PixelProgress } from '@/components/pixel';

export interface RAGResource {
  id: string;
  title: string;
  type: string;
  relevance: number;
  hitSnippet: string;
  whyRecommend: string;
  solveProblems: string[];
  tags: string[];
  summary?: {
    coreConcept: string;
    useCase: string;
    howToApply: string;
  };
}

interface RAGSearchResultCardProps {
  resource: RAGResource;
}

export default function RAGSearchResultCard({ resource }: RAGSearchResultCardProps) {
  const [showSummary, setShowSummary] = useState(false);
  const [addedToList, setAddedToList] = useState(false);
  const [showToast, setShowToast] = useState(false);

  const typeToken = resource.type.charAt(0).toUpperCase();
  const typeVariant = 'neutral';

  const handleAddToList = () => {
    setAddedToList(true);
    setShowToast(true);
    window.setTimeout(() => setShowToast(false), 2000);
  };

  return (
    <div className="relative">
      <PixelCard>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start">        
          <div className="flex h-14 w-14 shrink-0 items-center justify-center border-2 border-amber-600 bg-slate-950 font-mono text-lg font-bold text-amber-300 shadow-[0_0_18px_rgba(245,158,11,0.18)]">
            {typeToken}
          </div>

          <div className="min-w-0 flex-1">
            <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div className="min-w-0 flex-1">
                <div className="mb-2 flex flex-wrap items-center gap-2">        
                  <h4 className="text-lg font-bold leading-7 text-slate-100">{resource.title}</h4>
                  <PixelBadge variant={typeVariant}>{resource.type}</PixelBadge>
                </div>
                <PixelProgress value={resource.relevance} label="Relevance" />   
              </div>
            </div>

            <div className="mb-4">
              <div className="mb-2 text-sm font-bold text-amber-300">Key Snippet</div>
              <p className="border-2 border-amber-800 bg-slate-950 p-3 leading-7 text-amber-200">
                "{resource.hitSnippet}"
              </p>
            </div>

            <div className="mb-4">
              <div className="mb-2 text-sm font-bold text-amber-300">Why Recommended</div>
              <p className="border-2 border-slate-700 bg-slate-950 p-3 leading-7 text-slate-200">
                {resource.whyRecommend}
              </p>
            </div>

            <div className="mb-4">
              <div className="mb-2 text-sm font-bold text-amber-300">Solves</div>
              <div className="flex flex-wrap gap-2">
                {resource.solveProblems.map((problem) => (
                  <PixelBadge key={problem} variant="neutral">
                    {problem}
                  </PixelBadge>
                ))}
              </div>
            </div>

            <div className="mb-4 flex flex-wrap gap-2">
              {resource.tags.map((tag) => (
                <PixelBadge key={tag} variant="fun">
                  {tag}
                </PixelBadge>
              ))}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <PixelButton variant="secondary" onClick={() => setShowSummary(!showSummary)} fullWidth>
                {showSummary ? 'Hide Summary' : 'View Summary'}
              </PixelButton>
              <PixelButton variant={addedToList ? 'ghost' : 'primary'} onClick={handleAddToList} disabled={addedToList} fullWidth>
                {addedToList ? 'Added' : 'Add to Study List'}
              </PixelButton>
            </div>

            {showSummary && resource.summary ? (
              <div className="mt-4 space-y-3 border-t-2 border-slate-600 pt-4"> 
                <SummaryBlock title="Core Concept" content={resource.summary.coreConcept} />
                <SummaryBlock title="Use Case" content={resource.summary.useCase} />
                <SummaryBlock title="How to Apply" content={resource.summary.howToApply} />
              </div>
            ) : null}
          </div>
        </div>
      </PixelCard>

      {showToast ? (
        <div className="absolute right-4 top-4 z-10 border-2 border-emerald-800 bg-emerald-700 px-4 py-2 font-bold text-white">
          Added to study list (Mock)
        </div>
      ) : null}
    </div>
  );
}

function SummaryBlock({ title, content }: { title: string; content: string }) { 
  return (
    <div>
      <div className="mb-1 text-sm font-bold text-slate-400">{title}</div>      
      <p className="border border-slate-700 bg-slate-950 p-3 leading-7 text-slate-200">{content}</p>
    </div>
  );
}