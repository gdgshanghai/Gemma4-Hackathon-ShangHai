export interface Resource {
  id: string;
  title: string;
  type: string;
  url?: string;
  summary?: string;
  relevance?: number;
  tags?: string[];
}