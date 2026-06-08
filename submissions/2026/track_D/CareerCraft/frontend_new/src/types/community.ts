export type EngineerIssueStatus = 'open' | 'triaged' | 'solved';
export type EngineerIssuePriority = 'low' | 'normal' | 'high';

export interface EngineerReply {
  id: string;
  issueId: string;
  authorName: string;
  authorRole: string;
  content: string;
  createdAt: string;
  helpfulCount: number;
}

export interface EngineerIssue {
  id: string;
  careerId: string;
  authorId: string;
  authorName: string;
  title: string;
  content: string;
  tags: string[];
  status: EngineerIssueStatus;
  priority: EngineerIssuePriority;
  createdAt: string;
  replies: EngineerReply[];
}
