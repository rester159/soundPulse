import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Explore from './pages/Explore'
import ApiPlayground from './pages/ApiPlayground'
import ModelValidation from './pages/ModelValidation'
import SongLab from './pages/SongLab'
import Assistant from './pages/Assistant'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/explore" element={<Explore />} />
            <Route path="/api-tester" element={<ApiPlayground />} />
            <Route path="/model-validation" element={<ModelValidation />} />
            <Route path="/song-lab" element={<SongLab />} />
            <Route path="/assistant" element={<Assistant />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
