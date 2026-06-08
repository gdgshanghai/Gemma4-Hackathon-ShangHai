'use client';

import React, { useState } from 'react';
import { PixelButton, PixelDialog, PixelTextarea } from '@/components/pixel';

interface MentorChatDialogProps {
  open: boolean;
  onClose: () => void;
}

export default function MentorChatDialog({ open, onClose }: MentorChatDialogProps) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<Array<{ role: 'user' | 'mentor'; content: string }>>([]);
  const [isTyping, setIsTyping] = useState(false);

  const handleSend = () => {
    if (!question.trim()) return;

    const newUserMessage = { role: 'user' as const, content: question };
    setMessages((prev) => [...prev, newUserMessage]);
    setQuestion('');
    setIsTyping(true);

    window.setTimeout(() => {
      setIsTyping(false);
      setMessages((prev) => [
        ...prev,
        {
          role: 'mentor',
          content: '建议你先回到任务目标，确认交付物是否覆盖评审标准。再把不确定的地方拆成一个可验证的小问题。',
        },
      ]);
    }, 800);
  };

  return (
    <PixelDialog open={open} onClose={onClose} title="AI 导师">
      <div className="space-y-4">
        <div className="flex items-start gap-3 border-2 border-slate-700 bg-slate-950 p-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center border-2 border-amber-600 bg-slate-900 font-mono text-sm font-bold text-amber-300">
            AI
          </div>
          <p className="flex-1 text-sm leading-7 text-slate-300">
            你可以先描述遇到的问题，我会帮你拆解思路、补齐资料，并给出下一步行动建议。
          </p>
        </div>

        {messages.length > 0 ? (
          <div className="max-h-64 space-y-3 overflow-y-auto">
            {messages.map((message, index) => (
              <div key={index} className={`flex gap-3 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[82%] border-2 px-4 py-2 ${
                    message.role === 'user'
                      ? 'border-amber-700 bg-amber-950/35'
                      : 'border-slate-700 bg-slate-950'
                  }`}
                  style={{
                    boxShadow: 'inset -2px -2px 0px 0px #020617, inset 2px 2px 0px 0px #475569',
                  }}
                >
                  <p className="text-sm leading-7 text-slate-200">{message.content}</p>
                </div>
              </div>
            ))}
            {isTyping ? (
              <div className="flex gap-3">
                <div className="border-2 border-slate-700 bg-slate-950 px-4 py-2">
                  <span className="animate-pulse text-sm text-slate-400">导师正在思考...</span>
                </div>
              </div>
            ) : null}
          </div>
        ) : null}

        <div className="space-y-3">
          <PixelTextarea value={question} onChange={setQuestion} placeholder="请输入你的问题..." rows={3} />
          <div className="flex justify-end">
            <PixelButton onClick={handleSend} disabled={isTyping || !question.trim()}>
              发送
            </PixelButton>
          </div>
        </div>
      </div>
    </PixelDialog>
  );
}
