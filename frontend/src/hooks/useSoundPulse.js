import { useQuery, useMutation } from '@tanstack/react-query'
import axios from 'axios'

export function getApiKey() {
  return localStorage.getItem('soundpulse_api_key') || ''
}

export function getBaseUrl() {
  return localStorage.getItem('soundpulse_base_url') || '/api/v1'
}

function createClient() {
  const client = axios.create({
    baseURL: getBaseUrl(),
  })

  client.interceptors.request.use((config) => {
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
    staleTime: 300_000,
  })
}

export function useGenerateBlueprint() {
  return useMutation({
    mutationFn: ({ body }) => makeRequest('POST', '/blueprint/generate', {}, body),
  })
}
