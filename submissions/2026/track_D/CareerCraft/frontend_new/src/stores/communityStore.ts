'use client';

import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import { STORAGE_KEYS } from '@/constants';
import { seededEngineerIssues } from '@/data/communitySeeds';
import { EngineerIssue, EngineerIssuePriority, EngineerIssueStatus, EngineerReply } from '@/types';

interface CommunityStore {
  userId: string;
  displayName: string;
  issues: EngineerIssue[];
  setDisplayName: (name: string) => void;
  publishIssue: (input: {
    careerId: string;
    title: string;
    content: string;
    tags: string[];
    priority?: EngineerIssuePriority;
  }) => EngineerIssue;
  addReply: (issueId: string, content: string) => void;
  markReplyHelpful: (issueId: string, replyId: string) => void;
  updateIssueStatus: (issueId: string, status: EngineerIssueStatus) => void;
  getIssueById: (issueId: string) => EngineerIssue | undefined;
}

const createId = (prefix: string) => `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
const createUserId = () => `local-user-${Math.random().toString(16).slice(2, 10)}`;

function normalizeTags(tags: string[]): string[] {
  return Array.from(new Set(tags.map((tag) => tag.trim()).filter(Boolean).slice(0, 5)));
}

if (typeof window !== 'undefined') {
  window.localStorage.removeItem(STORAGE_KEYS.ENGINEER_COMMUNITY);
}

export const useCommunityStore = create<CommunityStore>()(
  persist(
    (set, get) => ({
      userId: createUserId(),
      displayName: '本地学员',
      issues: seededEngineerIssues,

      setDisplayName: (name) => set({ displayName: name.trim() || '本地学员' }),

      publishIssue: ({ careerId, title, content, tags, priority = 'normal' }) => {
        const state = get();
        const issue: EngineerIssue = {
          id: createId('issue'),
          careerId,
          authorId: state.userId,
          authorName: state.displayName,
          title: title.trim(),
          content: content.trim(),
          tags: normalizeTags(tags),
          status: 'open',
          priority,
          createdAt: new Date().toISOString(),
          replies: [],
        };
        set((current) => ({ issues: [issue, ...current.issues] }));
        return issue;
      },

      addReply: (issueId, content) => {
        const trimmed = content.trim();
        if (!trimmed) return;
        set((state) => ({
          issues: state.issues.map((issue) => {
            if (issue.id !== issueId) return issue;
            const reply: EngineerReply = {
              id: createId('reply'),
              issueId,
              authorName: state.displayName,
              authorRole: issue.authorId === state.userId ? '提问者补充' : '社区同学',
              content: trimmed,
              createdAt: new Date().toISOString(),
              helpfulCount: 0,
            };
            return { ...issue, replies: [...issue.replies, reply] };
          }),
        }));
      },

      markReplyHelpful: (issueId, replyId) =>
        set((state) => ({
          issues: state.issues.map((issue) =>
            issue.id !== issueId
              ? issue
              : {
                  ...issue,
                  replies: issue.replies.map((reply) =>
                    reply.id === replyId ? { ...reply, helpfulCount: reply.helpfulCount + 1 } : reply,
                  ),
                },
          ),
        })),

      updateIssueStatus: (issueId, status) =>
        set((state) => ({
          issues: state.issues.map((issue) => (issue.id === issueId ? { ...issue, status } : issue)),
        })),

      getIssueById: (issueId) => get().issues.find((issue) => issue.id === issueId),
    }),
    {
      name: STORAGE_KEYS.ENGINEER_COMMUNITY,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        userId: state.userId,
        displayName: state.displayName,
        issues: state.issues,
      }),
    },
  ),
);
