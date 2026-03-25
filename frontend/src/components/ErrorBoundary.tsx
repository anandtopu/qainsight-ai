/**
 * QA Insight AI — React Error Boundary.
 *
 * Catches any uncaught render-phase or lifecycle errors in its child tree.
 * Reports them to the backend telemetry endpoint via reportBoundaryError().
 * Shows a minimal fallback UI instead of a blank screen.
 */
import React, { Component, ErrorInfo, ReactNode } from 'react'
import { reportBoundaryError } from '../utils/errorReporting'

interface Props {
  children: ReactNode
  /** Optional custom fallback. Receives the error if you want to display details. */
  fallback?: (error: Error) => ReactNode
}

interface State {
  error: Error | null
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    reportBoundaryError(error, info.componentStack ?? '')
  }

  private handleReload = (): void => {
    window.location.reload()
  }

  private handleReset = (): void => {
    this.setState({ error: null })
  }

  render(): ReactNode {
    const { error } = this.state

    if (!error) {
      return this.props.children
    }

    if (this.props.fallback) {
      return this.props.fallback(error)
    }

    return (
      <div className="min-h-screen bg-slate-900 flex items-center justify-center p-6">
        <div className="max-w-md w-full bg-slate-800 rounded-xl border border-slate-700 p-8 text-center space-y-4">
          <div className="text-4xl">⚠️</div>
          <h1 className="text-xl font-semibold text-slate-100">Something went wrong</h1>
          <p className="text-sm text-slate-400">
            An unexpected error occurred in the application. The error has been reported
            automatically.
          </p>
          <p className="text-xs text-red-400 font-mono bg-slate-900 rounded p-2 text-left break-all">
            {error.message}
          </p>
          <div className="flex gap-3 justify-center pt-2">
            <button
              onClick={this.handleReset}
              className="px-4 py-2 text-sm rounded-lg bg-slate-700 hover:bg-slate-600 text-slate-200 transition-colors"
            >
              Try again
            </button>
            <button
              onClick={this.handleReload}
              className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-500 text-white transition-colors"
            >
              Reload page
            </button>
          </div>
        </div>
      </div>
    )
  }
}
