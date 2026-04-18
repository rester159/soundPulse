import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
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

export function useCreateArtistManual() {
  return useMutation({
    mutationFn: ({ body }) =>
      makeRequest('POST', '/admin/artists/create-manual', {}, body),
  })
}

export function useUpdateArtistManual() {
  // Partial update — only fields present in body get written. Mirrors
  // the create-manual body shape so the same form component can drive
  // both create + edit modes.
  return useMutation({
    mutationFn: ({ artistId, body }) =>
      makeRequest('PATCH', `/admin/artists/${artistId}`, {}, body),
  })
}

// -------- Submissions (task #86..#92) --------

export function useSubmissionTargets() {
  return useQuery({
    queryKey: ['admin', 'submission-targets'],
    queryFn: () => makeRequest('GET', '/admin/submission-targets'),
    staleTime: 30_000,
  })
}

export function useExternalSubmissions({ target_service = null, status = null, limit = 100 } = {}) {
  return useQuery({
    queryKey: ['admin', 'external-submissions', target_service, status, limit],
    queryFn: () => {
      const params = { limit }
      if (target_service) params.target_service = target_service
      if (status) params.status = status
      return makeRequest('GET', '/admin/external-submissions', params)
    },
    staleTime: 15_000,
    refetchOnWindowFocus: true,
  })
}

export function useAscapSubmissions(status = null) {
  return useQuery({
    queryKey: ['admin', 'ascap-submissions', status],
    queryFn: () => makeRequest('GET', '/admin/ascap-submissions', status ? { status } : {}),
    staleTime: 15_000,
  })
}

export function useGenreTraits() {
  return useQuery({
    queryKey: ['admin', 'genre-traits'],
    queryFn: () => makeRequest('GET', '/admin/genre-traits'),
    staleTime: 60_000,
  })
}

export function useTriggerSubmission() {
  return useMutation({
    mutationFn: ({ body }) =>
      makeRequest('POST', '/admin/external-submissions/submit', {}, body),
  })
}

export function useDownstreamSweep() {
  return useMutation({
    mutationFn: ({ limit = 20 } = {}) =>
      makeRequest('POST', '/admin/sweeps/downstream-pipeline', { limit }, {}),
  })
}

// -------- Instrumentals (task #86) --------

export function useInstrumentals(activeOnly = true) {
  return useQuery({
    queryKey: ['admin', 'instrumentals', activeOnly],
    queryFn: () => makeRequest('GET', '/admin/instrumentals', { active_only: activeOnly }),
    staleTime: 10_000,
    refetchOnWindowFocus: true,
  })
}

export function useUploadInstrumental() {
  // Multipart form POST — FormData must go through the shared axios
  // instance so the API key interceptor fires. Setting Content-Type
  // explicitly to undefined forces axios to compute the multipart
  // boundary header on its own.
  return useMutation({
    mutationFn: async ({ title, file, tempo_bpm, key_hint, genre_hint, notes }) => {
      const fd = new FormData()
      fd.append('title', title)
      fd.append('file', file)
      if (tempo_bpm) fd.append('tempo_bpm', tempo_bpm)
      if (key_hint) fd.append('key_hint', key_hint)
      if (genre_hint) fd.append('genre_hint', genre_hint)
      if (notes) fd.append('notes', notes)
      const res = await api.post('/admin/instrumentals/upload', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return { data: res.data }
    },
  })
}

export function useDeleteInstrumental() {
  return useMutation({
    mutationFn: ({ instrumental_id }) =>
      makeRequest('DELETE', `/admin/instrumentals/${instrumental_id}`, {}, {}),
  })
}

export function useGenerateSongWithInstrumental() {
  return useMutation({
    mutationFn: ({ blueprintId, body }) =>
      makeRequest('POST', `/admin/blueprints/${blueprintId}/generate-song-with-instrumental`, {}, body),
  })
}

export function useGenerateInstrumentalSongForArtist() {
  return useMutation({
    mutationFn: ({ instrumentalId, body }) =>
      makeRequest('POST', `/admin/instrumentals/${instrumentalId}/generate-song`, {}, body),
  })
}

// Vocal stems pipeline (song_stems table, populated by
// services/stem-extractor/ after add-vocals generations complete).
export function useSongStems(songId) {
  return useQuery({
    queryKey: ['admin', 'songs', songId, 'stems'],
    queryFn: () => makeRequest('GET', `/admin/songs/${songId}/stems`),
    enabled: !!songId,
    // Refetch while the job is in progress so the UI flips to the
    // mixed player automatically once the microservice finishes.
    refetchInterval: (q) => {
      const status = q.state.data?.data?.job?.status
      if (status === 'done' || status === 'failed' || !status) return false
      return 15_000
    },
    staleTime: 10_000,
  })
}

// Cached librosa analysis for an instrumental (detected BPM, key,
// vocal entry, etc). Used by the Nudge Vocal Entry control on the
// Songs page so the CEO can see what the worker auto-detected and
// correct it if wrong.
export function useInstrumentalAnalysis(instrumentalId) {
  return useQuery({
    queryKey: ['admin', 'instrumentals', instrumentalId, 'analysis'],
    queryFn: () =>
      makeRequest('GET', `/admin/instrumentals/${instrumentalId}/analysis`),
    enabled: !!instrumentalId,
    staleTime: 5_000,
  })
}

// Nudge vocal entry for an instrumental. When songId is provided, the
// API will enqueue a remix_only stem job that reuses the cached
// vocals_only stem and only re-runs the ffmpeg mix — ~10 s instead of
// 15 min. Use cases: (1) auto-detected entry is off by a bar, (2) CEO
// wants to try a different section as the vocal drop.
// Update the per-instrumental visual marker pins the CEO drops in
// the VocalEntryStudio. Optimistic: writes to the analysis cache
// immediately so the UI never flickers between add → server confirm.
export function useUpdateInstrumentalMarkers() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ instrumentalId, markers }) =>
      makeRequest(
        'PATCH',
        `/admin/instrumentals/${instrumentalId}/markers`,
        {},
        { markers },
      ),
    onMutate: async ({ instrumentalId, markers }) => {
      const key = ['admin', 'instrumentals', instrumentalId, 'analysis']
      await qc.cancelQueries({ queryKey: key })
      const prev = qc.getQueryData(key)
      qc.setQueryData(key, (old) => {
        if (!old?.data) return old
        return {
          ...old,
          data: {
            ...old.data,
            analysis_json: { ...(old.data.analysis_json || {}), markers },
          },
        }
      })
      return { prev }
    },
    onError: (_err, vars, ctx) => {
      if (ctx?.prev) {
        qc.setQueryData(
          ['admin', 'instrumentals', vars.instrumentalId, 'analysis'],
          ctx.prev,
        )
      }
    },
    onSettled: (_data, _err, vars) => {
      qc.invalidateQueries({
        queryKey: ['admin', 'instrumentals', vars.instrumentalId, 'analysis'],
      })
    },
  })
}


export function useNudgeVocalEntry() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ instrumentalId, vocalEntrySeconds, songId }) =>
      makeRequest(
        'PATCH',
        `/admin/instrumentals/${instrumentalId}/vocal-entry`,
        {},
        { vocal_entry_seconds: vocalEntrySeconds, song_id: songId },
      ),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({
        queryKey: ['admin', 'instrumentals', variables.instrumentalId, 'analysis'],
      })
      if (variables.songId) {
        qc.invalidateQueries({
          queryKey: ['admin', 'songs', variables.songId, 'stems'],
        })
      }
    },
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

// -------- Genre structures (task #109) --------

export function useGenreStructures() {
  return useQuery({
    queryKey: ['admin', 'genre-structures'],
    queryFn: () => makeRequest('GET', '/admin/genre-structures'),
    staleTime: 60_000,
  })
}

export function useGenreStructure(primaryGenre) {
  return useQuery({
    queryKey: ['admin', 'genre-structures', primaryGenre],
    queryFn: () => makeRequest('GET', `/admin/genre-structures/${encodeURIComponent(primaryGenre)}`),
    enabled: Boolean(primaryGenre),
    staleTime: 60_000,
  })
}

export function useUpdateGenreStructure() {
  return useMutation({
    mutationFn: ({ primaryGenre, structure, notes, updatedBy }) =>
      makeRequest(
        'PUT',
        `/admin/genre-structures/${encodeURIComponent(primaryGenre)}`,
        {},
        { structure, notes, updated_by: updatedBy },
      ),
  })
}

export function useDeleteGenreStructure() {
  return useMutation({
    mutationFn: ({ primaryGenre }) =>
      makeRequest(
        'DELETE',
        `/admin/genre-structures/${encodeURIComponent(primaryGenre)}`,
      ),
  })
}

export function usePatchArtistStructure() {
  return useMutation({
    mutationFn: ({ artistId, structure_template, genre_structure_override }) => {
      const body = {}
      if (structure_template !== undefined) body.structure_template = structure_template
      if (genre_structure_override !== undefined) body.genre_structure_override = genre_structure_override
      return makeRequest(
        'PATCH',
        `/admin/artists/${artistId}/structure`,
        {},
        body,
      )
    },
  })
}
