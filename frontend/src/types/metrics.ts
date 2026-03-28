export interface TrendPoint {
  date: string
  passed: number
  failed: number
  skipped: number
  broken: number
  total?: number
  pass_rate: number
}
