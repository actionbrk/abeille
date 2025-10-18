export interface RankResult {
  rank: number;
  author_id: string;
  count: number;
}

export interface RankFirstUsedResult {
  author_id: string;
  first_used_at: string; // ISO date string
}
