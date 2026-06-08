import React from 'react';
import Image from 'next/image';
import { PixelCard } from '@/components/pixel';
import { getMentorImage } from '@/constants/images';

interface FeedbackMentorCommentProps {
  mentorName: string;
  mentorAvatar: string;
  summaryComment: string;
  highlights: string[];
  suggestions: string[];
}

export default function FeedbackMentorComment({
  mentorName,
  summaryComment,
  highlights,
  suggestions,
}: FeedbackMentorCommentProps) {
  const isSoftware = mentorName.includes('工程') || mentorName.includes('代码');
  const careerId = isSoftware ? 'software-engineer' : 'data-analyst';

  return (
    <>
      <PixelCard title="导师评语">
        <div className="flex items-start gap-4">
          <div className="relative h-20 w-20 shrink-0 overflow-hidden border-4 border-amber-500 bg-slate-950">
            <Image src={getMentorImage(careerId)} alt={mentorName} fill className="object-cover" sizes="80px" />
          </div>
          <div>
            <h4 className="mb-2 font-bold text-amber-300">{mentorName}</h4>
            <p className="text-sm leading-6 text-slate-200">{summaryComment}</p>
          </div>
        </div>
      </PixelCard>

      <PixelCard title="做得好的地方">
        <ul className="space-y-2">
          {highlights.map((highlight) => (
            <li key={highlight} className="border-2 border-emerald-700 bg-emerald-950/30 p-3 text-sm leading-6 text-slate-200">
              <span className="mr-2 font-bold text-emerald-300">✓</span>
              {highlight}
            </li>
          ))}
        </ul>
      </PixelCard>

      <PixelCard title="下一次可以加强">
        <ul className="space-y-2">
          {suggestions.map((suggestion) => (
            <li key={suggestion} className="border-2 border-amber-700 bg-amber-950/25 p-3 text-sm leading-6 text-slate-200">
              <span className="mr-2 font-bold text-amber-300">+</span>
              {suggestion}
            </li>
          ))}
        </ul>
      </PixelCard>
    </>
  );
}
