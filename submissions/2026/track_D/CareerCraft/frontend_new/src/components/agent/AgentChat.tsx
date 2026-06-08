'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import Image from 'next/image';
import { getCareerMentor, MentorStage } from '@/data';
import { mentorService } from '@/services';

interface Message {
  id: string;
  role: 'user' | 'agent';
  text: string;
  timestamp: number;
}

interface AgentChatProps {
  careerId?: string;
  stage?: MentorStage;
  missionTitle?: string;
  pageTopic?: string;
  agentName?: string;
  agentAvatar?: string;
  agentRole?: string;
  compact?: boolean;
  className?: string;
}

export default function AgentChat({
  careerId = 'data-analyst',
  stage = 'career',
  missionTitle,
  pageTopic,
  agentName,
  agentAvatar,
  agentRole,
  compact = false,
  className = '',
}: AgentChatProps) {
  const mentor = useMemo(() => getCareerMentor(careerId), [careerId]);
  const displayName = agentName || mentor.name;
  const displayAvatar = agentAvatar || mentor.avatar;
  const displayRole = agentRole || mentor.title;
  const stagePrompt = mentor.stagePrompts[stage];
  const shellHeight = compact ? 'h-[360px]' : 'h-[520px]';

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'mock'>('mock');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setMessages([
      {
        id: `welcome-${mentor.id}-${stage}`,
        role: 'agent',
        text: `${mentor.greeting}\n\n当前我会重点帮你：${stagePrompt}`,
        timestamp: Date.now(),
      },
    ]);
  }, [mentor, stage, stagePrompt]);

  useEffect(() => {
    let alive = true;
    mentorService.checkHealth().then((ok) => {
      if (alive) setConnectionStatus(ok ? 'connected' : 'mock');
    });
    return () => {
      alive = false;
      abortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages]);

  const sendMessage = async (value?: string) => {
    const trimmed = (value ?? input).trim();
    if (!trimmed || isStreaming) return;

    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      text: trimmed,
      timestamp: Date.now(),
    };
    const agentMessageId = `agent-${Date.now()}`;
    setMessages((current) => [
      ...current,
      userMessage,
      { id: agentMessageId, role: 'agent', text: '', timestamp: Date.now() },
    ]);
    setInput('');
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await mentorService.streamChat(
        trimmed,
        (chunk) => {
          setMessages((current) =>
            current.map((message) =>
              message.id === agentMessageId ? { ...message, text: message.text + chunk } : message,
            ),
          );
        },
        { careerId, stage, missionTitle, pageTopic },
        controller.signal,
      );
      const ok = await mentorService.checkHealth();
      setConnectionStatus(ok ? 'connected' : 'mock');
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <section
      className={`${shellHeight} min-h-0 overflow-hidden border-2 border-slate-700 bg-slate-950/90 shadow-[0_0_0_1px_rgba(245,158,11,0.16),0_18px_40px_rgba(2,6,23,0.42)] ${className}`}
      aria-label={`${displayName}导师对话`}
    >
      <div className="flex h-full min-h-0 flex-col">
        <div className="border-b-4 border-slate-700 bg-slate-900/95 p-3">
          <div className="flex items-center gap-3">
            <div className="relative h-12 w-12 shrink-0 overflow-hidden border-2 border-amber-600 bg-slate-950">
              <Image src={mentor.image} alt={displayName} fill sizes="48px" className="object-cover" />
              <span className="absolute bottom-0 right-0 border-l border-t border-slate-800 bg-slate-950 px-1 font-mono text-[9px] text-amber-300">
                {displayAvatar}
              </span>
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate font-bold text-amber-200">{displayName}</p>
                <span className={`h-2 w-2 shrink-0 rounded-full ${connectionStatus === 'connected' ? 'bg-emerald-400' : 'bg-amber-400'}`} />
              </div>
              <p className="truncate text-xs text-slate-400">{displayRole}</p>
              <p className="mt-1 line-clamp-1 text-xs text-slate-500">{mentor.specialty}</p>
            </div>
          </div>
          {!compact ? <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-400">{stagePrompt}</p> : null}
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
          {messages.map((message) => (
            <div key={message.id} className={`flex gap-2 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {message.role === 'agent' ? (
                <div className="flex h-7 w-7 shrink-0 items-center justify-center border-2 border-slate-700 bg-slate-900 font-mono text-[11px] font-bold text-amber-300">
                  {displayAvatar}
                </div>
              ) : null}
              <div
                className={`max-w-[84%] border-2 px-3 py-2 text-xs leading-5 md:text-sm ${
                  message.role === 'user'
                    ? 'border-amber-700 bg-amber-950/35 text-amber-50'
                    : 'border-slate-700 bg-slate-900 text-slate-200'
                }`}
                style={{ boxShadow: 'inset -2px -2px 0 #020617, inset 2px 2px 0 rgba(148,163,184,0.22)' }}
              >
                <p className="whitespace-pre-wrap break-words">
                  {message.text}
                  {message.role === 'agent' && isStreaming && message.id === messages[messages.length - 1]?.id ? (
                    <span className="ml-1 animate-pulse text-amber-300">_</span>
                  ) : null}
                </p>
                <p className="mt-1 font-mono text-[10px] text-slate-500">
                  {new Date(message.timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
                </p>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {!compact ? (
          <div className="border-t border-slate-800 px-3 py-2">
            <div className="flex flex-wrap gap-2">
              {mentor.quickQuestions.slice(0, 3).map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => sendMessage(question)}
                  disabled={isStreaming}
                  className="border border-slate-700 bg-slate-900 px-2 py-1 text-left text-xs text-slate-300 hover:border-amber-600 hover:text-amber-200 disabled:opacity-50"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : null}

        <div className="border-t-4 border-slate-700 bg-slate-900/95 p-3">
          <div className="flex gap-2">
            <textarea
              data-agent-chat-input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="向导师提问，Enter 发送"
              rows={compact ? 1 : 2}
              disabled={isStreaming}
              className="min-h-[42px] flex-1 resize-none border-2 border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-amber-500 disabled:opacity-60"
            />
            <button
              type="button"
              onClick={() => sendMessage()}
              disabled={isStreaming || !input.trim()}
              className="shrink-0 border-2 border-amber-700 bg-amber-500 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
              style={{ boxShadow: 'inset -2px -2px 0 #92400e, inset 2px 2px 0 #fde68a' }}
            >
              {isStreaming ? '...' : '发送'}
            </button>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {connectionStatus === 'connected' ? '导师在线，随时为你解答' : '导师暂离，助手代为服务'}
          </p>
        </div>
      </div>
    </section>
  );
}
