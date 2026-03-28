import type { PaginatedResponse } from './common'

export interface SearchResult {
  test_case_id: string
  test_run_id: string
  test_name: string
  suite_name?: string
  status: string
  failure_count: number
  last_run_date: string
}

export interface SearchResponse extends PaginatedResponse<SearchResult> {
  query: string
}
