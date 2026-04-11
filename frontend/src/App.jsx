import { Component } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AssistantVisibilityProvider } from './contexts/AssistantVisibilityContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Explore from './pages/Explore'
import ApiPlayground from './pages/ApiPlayground'
import ModelValidation from './pages/ModelValidation'
import SongLab from './pages/SongLab'
import Assistant from './pages/Assistant'
import DataFlow from './pages/DataFlow'
import DbStats from './pages/DbStats'
import HydrationDashboard from './pages/HydrationDashboard'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

class ErrorBoundary extends Component {
  state = { error: null }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <div className="text-rose-400 text-sm font-medium mb-2">Something went wrong on this page</div>
          <div className="text-zinc-500 text-xs mb-4 max-w-sm">{this.state.error?.message}</div>
          <button
            onClick={() => this.setState({ error: null })}
            className="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm rounded-lg transition-colors"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
     <AssistantVisibilityProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<ErrorBoundary><Dashboard /></ErrorBoundary>} />
            <Route path="/explore" element={<ErrorBoundary><Explore /></ErrorBoundary>} />
            <Route path="/api-tester" element={<ErrorBoundary><ApiPlayground /></ErrorBoundary>} />
            <Route path="/model-validation" element={<ErrorBoundary><ModelValidation /></ErrorBoundary>} />
            <Route path="/song-lab" element={<ErrorBoundary><SongLab /></ErrorBoundary>} />
            <Route path="/assistant" element={<ErrorBoundary><Assistant /></ErrorBoundary>} />
            <Route path="/data-flow" element={<ErrorBoundary><DataFlow /></ErrorBoundary>} />
            <Route path="/db-stats" element={<ErrorBoundary><DbStats /></ErrorBoundary>} />
            <Route path="/hydration" element={<ErrorBoundary><HydrationDashboard /></ErrorBoundary>} />
          </Route>
        </Routes>
      </BrowserRouter>
     </AssistantVisibilityProvider>
    </QueryClientProvider>
  )
}

export default App
