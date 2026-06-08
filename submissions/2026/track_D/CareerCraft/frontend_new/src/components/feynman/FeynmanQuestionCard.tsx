'use client';

import React from 'react';
import { PixelBadge } from '@/components/pixel';

interface Question {
  id: string;
  text: string;
  type: string;
  difficulty: 'easy' | 'medium' | 'hard';
}

interface FeynmanQuestionCardProps {
  question: Question;
  questionNumber: number;
  totalQuestions: number;
}

export default function FeynmanQuestionCard({
  question,
  questionNumber,
  totalQuestions,
}: FeynmanQuestionCardProps) {
  return (
    <section className="border-4 border-slate-700 bg-slate-950/82 p-5 backdrop-blur-sm">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <div className="text-xs text-slate-500">问题 {questionNumber} / {totalQuestions}</div>
          <h3 className="mt-1 font-bold text-amber-300">{typeLabel(question.type)}</h3>
        </div>
        <PixelBadge
          variant={
            question.difficulty === 'hard'
              ? 'danger'
              : question.difficulty === 'easy'
                ? 'success'
                : 'warning'
          }
        >
          {difficultyLabel(question.difficulty)}
        </PixelBadge>
      </div>

      <div className="border-2 border-slate-700 bg-slate-900/75 p-5">
        <p className="text-lg leading-8 text-slate-100">{question.text}</p>
      </div>

      <p className="mt-3 text-xs leading-5 text-slate-500">
        提示：假设你在给完全不了解这个岗位的同学解释，不要堆术语，最好给一个任务里的例子。
      </p>
    </section>
  );
}

function typeLabel(type: string) {
  if (type === 'definition') return '定义题';
  if (type === 'why') return '原因题';
  if (type === 'how') return '方法题';
  if (type === 'comparison') return '比较题';
  return type;
}

function difficultyLabel(difficulty: Question['difficulty']) {
  if (difficulty === 'easy') return '入门';
  if (difficulty === 'medium') return '进阶';
  return '挑战';
}
