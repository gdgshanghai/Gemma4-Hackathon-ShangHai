import React from 'react';
import { EmptyState } from '@/components/common';

interface ReviewHighlight {
  missionId: string;
  missionTitle: string;
  score: number;
  maxScore: number;
  grade: string;
  comment: string;
}

interface PortfolioReviewHighlightsProps {
  reviews: ReviewHighlight[];
}

export default function PortfolioReviewHighlights({
  reviews
}: PortfolioReviewHighlightsProps) {
  if (reviews.length === 0) {
    return (
      <div>
        <h2 className="text-xl font-bold text-amber-500 mb-3 flex items-center gap-2">
          <span>✨</span>
          <span>评审高光</span>
        </h2>
        <EmptyState
          description="完成任务并获得评审后会在这里显示。"
        />
      </div>
    );
  }

  const getGradeColor = (grade: string) => {
    switch (grade) {
      case 'S': return '#fbbf24';
      case 'A': return '#f59e0b';
      case 'B+': return '#3b82f6';
      case 'B': return '#2563eb';
      default: return '#64748b';
    }
  };

  return (
    <div>
      <h2 className="text-xl font-bold text-amber-500 mb-3 flex items-center gap-2">
        <span>✨</span>
        <span>评审高光</span>
      </h2>
      <div className="space-y-2">
        {reviews.map((review, index) => (
          <div 
            key={review.missionId}
            className="p-3 bg-slate-800 border-3 border-slate-700"
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex-1">
                <h4 className="text-slate-200 font-bold text-sm">{review.missionTitle}</h4>
              </div>
              <div className="text-right">
                <div className="text-xl font-bold" style={{ color: getGradeColor(review.grade) }}>
                  {review.grade}
                </div>
                <div className="text-xs text-amber-500">
                  {review.score}/{review.maxScore}
                </div>
              </div>
            </div>
            <p className="text-slate-400 text-xs italic">
              "{review.comment}"
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
