import { useQuery, useMutation } from '@tanstack/react-query'
import axios from 'axios'

export function getApiKey() {
  return localStorage.getItem('soundpulse_api_key') || ''
}

export function getBaseUrl() {
  return (
    localStorage.getItem('soundpulse_base_url') ||
    import.meta.env.VITE_API_BASE_URL ||
    '/api/v1'
  )
}

function createClient() {
  const client = axios.create({
    baseURL: getBaseUrl(),
  })

  client.interceptors.request.use((config) => {
    // Re-read on every request so Settings changes take effect without a page reload
    config.baseURL = getBaseUrl()
    const key = getApiKey()
    if (key) {
      config.headers['X-API-Key'] = key
    }
    config.metadata = { startTime: performance.now() }
    return config
  })

  client.interceptors.response.use(
    (response) => {
      const duration = performance.now() - response.config.metadata.startTime
      response.duration = duration
      return response
    },
    (error) => {
      if (error.config?.metadata) {
        const duration = performance.now() - error.config.metadata.startTime
        if (error.response) {
          error.response.duration = duration
        }
        error.duration = duration
      }
      return Promise.reject(error)
    }
  )

  return client
}

const api = createClient()

export function generateCurl(method, path, params = {}, body = null) {
  const baseUrl = getBaseUrl()
  const apiKey = getApiKey()

  let url = `${baseUrl}${path}`

  // Replace path params
  const pathParams = {}
  const queryParams = {}
  for (const [key, value] of Object.entries(params)) {
    if (value === '' || value === undefined || value === null) continue
    if (path.includes(`{${key}}`)) {
      url = url.replace(`{${key}}`, encodeURIComponent(value))
      pathParams[key] = value
    } else {
      queryParams[key] = value
    }
  }

  const queryString = new URLSearchParams(queryParams).toString()
  if (queryString) {
    url += `?${queryString}`
  }

  let curl = `curl -X ${method} '${url}'`
  if (apiKey) {
    curl += ` \\\n  -H 'X-API-Key: ${apiKey}'`
  }
  curl += ` \\\n  -H 'Content-Type: application/json'`

  if (body && method !== 'GET') {
    curl += ` \\\n  -d '${JSON.stringify(body, null, 2)}'`
  }

  return curl
}

async function makeRequest(method, path, params = {}, body = null) {
  let resolvedPath = path
  const queryParams = {}

  for (const [key, value] of Object.entries(params)) {
    if (value === '' || value === undefined || value === null) continue
    if (path.includes(`{${key}}`)) {
      resolvedPath = resolvedPath.replace(`{${key}}`, encodeURIComponent(value))
    } else {
      queryParams[key] = value
    }
  }

  const config = {
    method,
    url: resolvedPath,
    params: method === 'GET' ? queryParams : undefined,
    data: method !== 'GET' ? (body || queryParams) : undefined,
  }

  const response = await api(config)
  return {
    data: response.data,
    status: response.status,
    headers: Object.fromEntries(
      Object.entries(response.headers).filter(([, v]) => typeof v === 'string')
    ),
    duration: response.duration,
  }
}

export function useTrending(params = {}) {
  return useQuery({
    queryKey: ['trending', params],
    queryFn: () => makeRequest('GET', '/trending', params),
    refetchInterval: 60_000,
    enabled: !!params.entity_type,
  })
}

export function useSearch(query, type = 'all') {
  return useQuery({
    queryKey: ['search', query, type],
    queryFn: () => makeRequest('GET', '/search', { q: query, type }),
    enabled: !!query && query.length >= 2,
  })
}

export function usePredictions(params = {}) {
  return useQuery({
    queryKey: ['predictions', params],
    queryFn: () => makeRequest('GET', '/predictions', params),
  })
}

export function useGenres(params = {}) {
  return useQuery({
    queryKey: ['genres', params],
    queryFn: () => makeRequest('GET', '/genres', params),
  })
}

export function useGenreDetail(genreId) {
  return useQuery({
    queryKey: ['genre', genreId],
    queryFn: () => makeRequest('GET', `/genres/${encodeURIComponent(genreId)}`),
    enabled: !!genreId,
  })
}

export function useApiRequest() {
  return useMutation({
    mutationFn: ({ method, path, params, body }) =>
      makeRequest(method, path, params, body),
  })
}

// Backtesting hooks
export function useBacktestResults(params = {}) {
  return useQuery({
    queryKey: ['backtesting', 'results', params],
    queryFn: () => makeRequest('GET', '/backtesting/results', params),
    staleTime: 300_000,
  })
}

export function useBacktestRuns() {
  return useQuery({
    queryKey: ['backtesting', 'runs'],
    queryFn: () => makeRequest('GET', '/backtesting/runs'),
  })
}

export function useBacktestGenres(params = {}) {
  return useQuery({
    queryKey: ['backtesting', 'genres', params],
    queryFn: () => makeRequest('GET', '/backtesting/genres', params),
    staleTime: 300_000,
  })
}

export function useRunBacktest() {
  return useMutation({
    mutationFn: ({ body }) => makeRequest('POST', '/backtesting/run', {}, body),
  })
}

// Blueprint / Song Lab hooks
export function useGenreOpportunities() {
  return useQuery({
    queryKey: ['blueprint', 'genres'],
    queryFn: () => makeRequest('GET', '/blueprint/genres'),
    staleTime: 30_000,
    refetchOnWindowFocus: true,
    refetchOnMount: true,
  })
}

export function useGenerateBlueprint() {
  return useMutation({
    mutationFn: ({ body }) => makeRequest('POST', '/blueprint/generate', {}, body),
  })
}

export function useTopOpportunities(n = 10, model = 'suno', sortBy = 'opportunity') {
  return useQuery({
    queryKey: ['blueprint', 'top-opportunities', n, model, sortBy],
    queryFn: () => makeRequest('GET', '/blueprint/top-opportunities', { n, model, sort_by: sortBy }),
    staleTime: 5 * 60_000,  // 5 min — LLM calls are expensive
    refetchOnWindowFocus: false,
  })
}

// Settings hooks
export function useCeoProfile() {
  return useQuery({
    queryKey: ['admin', 'ceo-profile'],
    queryFn: () => makeRequest('GET', '/admin/ceo-profile'),
    staleTime: 60_000,
  })
}

export function useUpdateCeoProfile() {
  return useMutation({
    mutationFn: ({ body }) => makeRequest('PUT', '/admin/ceo-profile', {}, body),
  })
}

export function useAgents() {
  return useQuery({
    queryKey: ['admin', 'agents'],
    queryFn: () => makeRequest('GET', '/admin/agents'),
    staleTime: 5 * 60_000,
  })
}

export function useTools() {
  return useQuery({
    queryKey: ['admin', 'tools'],
    queryFn: () => makeRequest('GET', '/admin/tools'),
    staleTime: 60_000,
  })
}

export function useAgentToolGrants(pivot = 'by_tool') {
  return useQuery({
    queryKey: ['admin', 'agent-tool-grants', pivot],
    queryFn: () => makeRequest('GET', '/admin/agent-tool-grants', { pivot }),
    staleTime: 30_000,
  })
}

export function useCreateGrant() {
  return useMutation({
    mutationFn: ({ body }) => makeRequest('POST', '/admin/agent-tool-grants', {}, body),
  })
}

export function useDeleteGrant() {
  return useMutation({
    mutationFn: ({ agent_id, tool_id }) =>
      makeRequest('DELETE', '/admin/agent-tool-grants', { agent_id, tool_id }),
  })
}

// Assistant hook
export function useAssistantChat() {
  return useMutation({
    mutationFn: ({ body }) => makeRequest('POST', '/assistant/chat', {}, body),
  })
}

// Data Flow / Architecture diagram hook
export function useDataFlow() {
  return useQuery({
    queryKey: ['admin', 'data-flow'],
    queryFn: () => makeRequest('GET', '/admin/data-flow'),
    refetchInterval: 60_000,  // auto-refresh every 60s
    staleTime: 30_000,
  })
}

// DB Stats hooks (P2.I, PRD §22.2)
export function useDbStats() {
  return useQuery({
    queryKey: ['admin', 'db-stats'],
    queryFn: () => makeRequest('GET', '/admin/db-stats'),
    refetchInterval: 60_000,  // auto-refresh every 60s
    staleTime: 30_000,
  })
}

export function useDbStatsHistory(days = 90) {
  return useQuery({
    queryKey: ['admin', 'db-stats', 'history', days],
    queryFn: () => makeRequest('GET', '/admin/db-stats/history', { days }),
    refetchInterval: 300_000,  // 5 min — historical data doesn't change rapidly
    staleTime: 60_000,
  })
}

export function useSweepStatus() {
  return useQuery({
    queryKey: ['admin', 'sweeps', 'status'],
    queryFn: () => makeRequest('GET', '/admin/sweeps/status'),
    refetchInterval: 30_000,
  })
}

export function useTriggerClassificationSweep() {
  return useMutation({
    mutationFn: ({ batchSize = 500, forceReclassify = false } = {}) =>
      makeRequest('POST', '/admin/sweeps/classification', {
        batch_size: batchSize,
        force_reclassify: forceReclassify,
      }),
  })
}

export function useTriggerCompositeSweep() {
  return useMutation({
    mutationFn: ({ batchSize = 1000 } = {}) =>
      makeRequest('POST', '/admin/sweeps/composite', { batch_size: batchSize }),
  })
}

// Hydration dashboard hooks
export function useHydrationSnapshot() {
  return useQuery({
    queryKey: ['admin', 'hydration'],
    queryFn: () => makeRequest('GET', '/admin/db-stats/hydration'),
    refetchInterval: 10_000,  // auto-refresh every 10s, no page reload
    staleTime: 5_000,
  })
}

export function useHydrationHistory(hours = 24) {
  return useQuery({
    queryKey: ['admin', 'hydration', 'history', hours],
    queryFn: () => makeRequest('GET', '/admin/db-stats/hydration/history', { hours }),
    refetchInterval: 10_000,
    staleTime: 5_000,
  })
}

// Songs, releases, generation orchestrator (§17, §24, §30)
export function useSongs({ status = null, artistId = null, limit = 50 } = {}) {
  return useQuery({
    queryKey: ['admin', 'songs', status, artistId, limit],
    queryFn: () => {
      const params = { limit }
      if (status) params.status = status
      if (artistId) params.primary_artist_id = artistId
      return makeRequest('GET', '/admin/songs', params)
    },
    refetchInterval: 15_000,
    staleTime: 5_000,
  })
}

export function useSong(songId) {
  return useQuery({
    queryKey: ['admin', 'songs', songId],
    queryFn: () => makeRequest('GET', `/admin/songs/${songId}`),
    enabled: !!songId,
    staleTime: 10_000,
  })
}

export function useMarkQaPassed() {
  return useMutation({
    mutationFn: ({ songId }) =>
      makeRequest('POST', `/admin/songs/${songId}/mark-qa-passed`, {}, {}),
  })
}

export function useGenerateSongForBlueprint() {
  return useMutation({
    mutationFn: ({ blueprintId, body }) =>
      makeRequest('POST', `/admin/blueprints/${blueprintId}/generate-song`, {}, body),
  })
}

export function useReleases({ status = null, artistId = null } = {}) {
  return useQuery({
    queryKey: ['admin', 'releases', status, artistId],
    queryFn: () => {
      const params = {}
      if (status) params.status = status
      if (artistId) params.artist_id = artistId
      return makeRequest('GET', '/admin/releases', params)
    },
    staleTime: 15_000,
  })
}

export function useRelease(releaseId) {
  return useQuery({
    queryKey: ['admin', 'releases', releaseId],
    queryFn: () => makeRequest('GET', `/admin/releases/${releaseId}`),
    enabled: !!releaseId,
  })
}

export function useCreateRelease() {
  return useMutation({
    mutationFn: ({ body }) => makeRequest('POST', '/admin/releases', {}, body),
  })
}

export function useAddTrackToRelease() {
  return useMutation({
    mutationFn: ({ releaseId, body }) =>
      makeRequest('POST', `/admin/releases/${releaseId}/tracks`, {}, body),
  })
}

export function useRemoveTrackFromRelease() {
  return useMutation({
    mutationFn: ({ releaseId, songId }) =>
      makeRequest('DELETE', `/admin/releases/${releaseId}/tracks/${songId}`),
  })
}

// Music generation provider hooks (§24, §56)
export function useMusicProviders() {
  return useQuery({
    queryKey: ['admin', 'music', 'providers'],
    queryFn: () => makeRequest('GET', '/admin/music/providers'),
    staleTime: 60_000,
  })
}

export function useMusicGenerate() {
  return useMutation({
    mutationFn: ({ body }) => makeRequest('POST', '/admin/music/generate', {}, body),
  })
}

export function useMusicPoll(provider, taskId, { enabled = true } = {}) {
  return useQuery({
    queryKey: ['admin', 'music', 'poll', provider, taskId],
    queryFn: () => makeRequest('GET', `/admin/music/generate/${provider}/${taskId}`),
    enabled: enabled && !!provider && !!taskId,
    refetchInterval: (q) => {
      const status = q.state.data?.data?.status
      // Stop polling once terminal
      if (status === 'succeeded' || status === 'failed') return false
      return 3_000
    },
    staleTime: 0,
  })
}

// CEO decisions (§23) + artist spine hooks
export function useCeoDecisions({ status = 'pending', decisionType = null } = {}) {
  return useQuery({
    queryKey: ['admin', 'ceo-decisions', status, decisionType],
    queryFn: () => {
      const params = {}
      if (status) params.status = status
      if (decisionType) params.decision_type = decisionType
      return makeRequest('GET', '/admin/ceo-decisions', params)
    },
    refetchInterval: 15_000,
    staleTime: 5_000,
  })
}

export function useApproveCeoDecision() {
  return useMutation({
    mutationFn: ({ decisionId, notes, modifications }) =>
      makeRequest('POST', `/admin/ceo-decisions/${decisionId}/approve`, {}, {
        response_notes: notes,
        modifications,
      }),
  })
}

export function useRejectCeoDecision() {
  return useMutation({
    mutationFn: ({ decisionId, notes }) =>
      makeRequest('POST', `/admin/ceo-decisions/${decisionId}/reject`, {}, {
        response_notes: notes,
      }),
  })
}

export function useAIArtists(rosterStatus = 'active') {
  return useQuery({
    queryKey: ['admin', 'ai-artists', rosterStatus],
    queryFn: () => makeRequest('GET', '/admin/artists', { roster_status: rosterStatus }),
    // Short staleTime + always refetch on window focus so
    // portrait/persona updates become visible without a hard refresh.
    staleTime: 5_000,
    refetchOnWindowFocus: true,
  })
}

export function useRegenerateArtistPortrait() {
  return useMutation({
    mutationFn: ({ artistId }) =>
      makeRequest('POST', `/admin/artists/${artistId}/regenerate-portrait`, {}, {}),
  })
}

export function useArtistReferenceSheet(artistId) {
  return useQuery({
    queryKey: ['admin', 'artists', artistId, 'reference-sheet'],
    queryFn: () => makeRequest('GET', `/admin/artists/${artistId}/reference-sheet`),
    enabled: !!artistId,
    staleTime: 10_000,
  })
}

export function useGenerateReferenceSheet() {
  return useMutation({
    mutationFn: ({ artistId }) =>
      makeRequest('POST', `/admin/artists/${artistId}/generate-reference-sheet`, {}, {}),
  })
}

export function useCreateArtistFromDescription() {
  return useMutation({
    mutationFn: ({ body }) =>
      makeRequest('POST', '/admin/artists/from-description', {}, body),
  })
}

export function usePreviewPersona() {
  return useMutation({
    mutationFn: ({ body }) =>
      makeRequest('POST', '/admin/artists/preview-persona', {}, body),
  })
}

export function useCreateArtistFromPersona() {
  return useMutation({
    mutationFn: ({ body }) =>
      makeRequest('POST', '/admin/artists/create-from-persona', {}, body),
  })
}

export function useBlueprints({ status = null, limit = 50 } = {}) {
  return useQuery({
    queryKey: ['admin', 'blueprints', status, limit],
    queryFn: () => {
      const params = { limit }
      if (status) params.status = status
      return makeRequest('GET', '/admin/blueprints', params)
    },
    staleTime: 30_000,
  })
}

export function useMusicGenerations(limit = 20) {
  return useQuery({
    queryKey: ['admin', 'music', 'generations', limit],
    queryFn: () => makeRequest('GET', '/admin/music/generations', { limit }),
    refetchInterval: 15_000,
    staleTime: 10_000,
  })
}

// Version badge — displays deploy identity in the Layout top-right
export function useVersion() {
  return useQuery({
    queryKey: ['version'],
    queryFn: () => makeRequest('GET', '/version'),
    // Refetch every 60s so the badge catches a Railway redeploy even on
    // pages the user keeps open for a while
    refetchInterval: 60_000,
    staleTime: 30_000,
  })
}
