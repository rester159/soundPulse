# SoundPulse Frontend — Claude Code Build Prompt

> **Build a React testing dashboard for the SoundPulse API.**
> Dark mode. Music industry aesthetic. Functional API tester + visual trending data.

---

## SETUP

```bash
cd soundpulse/frontend
npm create vite@latest . -- --template react
npm install axios recharts lucide-react @tanstack/react-query
npm install -D tailwindcss @tailwindcss/vite
```

### `vite.config.js`
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
```

### `src/index.css`
```css
@import "tailwindcss";
```

---

## APP STRUCTURE

```
src/
├── App.jsx                 # Router + layout
├── index.css               # Tailwind base
├── hooks/
│   └── useSoundPulse.js    # API client hook (all API calls go through here)
├── components/
│   ├── Layout.jsx           # Sidebar nav + main content area
│   ├── TrendingTable.jsx    # Sortable table of trending entities
│   ├── TrendingCard.jsx     # Single entity card with sparkline
│   ├── SparkLine.jsx        # Mini 7-day trend chart
│   ├── PredictionCard.jsx   # Prediction with confidence bar + signals
│   ├── GenreTree.jsx        # Expandable genre taxonomy browser
│   ├── GenreHeatmap.jsx     # Visual grid of root genres by momentum
│   ├── SearchBar.jsx        # Autocomplete search
│   ├── ApiTester.jsx        # Interactive API playground
│   ├── RequestBuilder.jsx   # Parameter form builder for API tester
│   ├── ResponseViewer.jsx   # Formatted JSON response display
│   ├── SettingsDrawer.jsx   # API key config, base URL
│   └── FreshnessIndicator.jsx  # Data age indicator
├── pages/
│   ├── Dashboard.jsx        # Main dashboard with trending + predictions
│   ├── Explore.jsx          # Search + genre browsing + filtering
│   └── ApiPlayground.jsx    # API tester page
└── utils/
    ├── formatters.js        # Number formatting, date formatting
    └── endpoints.js         # Endpoint definitions for API tester
```

---

## CORE HOOK: `useSoundPulse.js`

```javascript
// hooks/useSoundPulse.js
import { useQuery, useMutation } from '@tanstack/react-query';
import axios from 'axios';

const getApiKey = () => localStorage.getItem('soundpulse_api_key') || '';
const getBaseUrl = () => localStorage.getItem('soundpulse_base_url') || '/api/v1';

const client = axios.create();

// Inject API key on every request
client.interceptors.request.use((config) => {
  config.baseURL = getBaseUrl();
  config.headers['X-API-Key'] = getApiKey();
  return config;
});

// Track response times for API tester
client.interceptors.response.use((response) => {
  response.duration = Date.now() - response.config._startTime;
  return response;
});

client.interceptors.request.use((config) => {
  config._startTime = Date.now();
  return config;
});

export function useTrending(params) {
  return useQuery({
    queryKey: ['trending', params],
    queryFn: () => client.get('/trending', { params }).then(r => r.data),
    refetchInterval: 60_000, // auto-refresh every minute
  });
}

export function useSearch(query, type = 'all') {
  return useQuery({
    queryKey: ['search', query, type],
    queryFn: () => client.get('/search', { params: { q: query, type } }).then(r => r.data),
    enabled: query.length >= 2,
  });
}

export function usePredictions(params) {
  return useQuery({
    queryKey: ['predictions', params],
    queryFn: () => client.get('/predictions', { params }).then(r => r.data),
  });
}

export function useGenres(params) {
  return useQuery({
    queryKey: ['genres', params],
    queryFn: () => client.get('/genres', { params }).then(r => r.data),
    staleTime: 24 * 60 * 60 * 1000, // 24h — taxonomy rarely changes
  });
}

export function useGenreDetail(genreId) {
  return useQuery({
    queryKey: ['genre', genreId],
    queryFn: () => client.get(`/genres/${genreId}`).then(r => r.data),
    enabled: !!genreId,
  });
}

// For the API tester — raw request with full response metadata
export function useApiRequest() {
  return useMutation({
    mutationFn: async ({ method, path, params, body }) => {
      const start = Date.now();
      const config = { method, url: path };
      if (method === 'GET') config.params = params;
      if (method === 'POST') config.data = body;
      
      const response = await client.request(config);
      return {
        status: response.status,
        headers: response.headers,
        data: response.data,
        duration: Date.now() - start,
        curl: generateCurl(method, path, params, body),
      };
    },
  });
}

function generateCurl(method, path, params, body) {
  const baseUrl = getBaseUrl();
  const url = new URL(path, baseUrl.startsWith('http') ? baseUrl : `http://localhost:8000${baseUrl}`);
  if (params) Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
  
  let cmd = `curl -X ${method} "${url.toString()}" \\\n  -H "X-API-Key: ${getApiKey()}"`;
  if (body) cmd += ` \\\n  -H "Content-Type: application/json" \\\n  -d '${JSON.stringify(body)}'`;
  return cmd;
}
```

---

## PAGES

### Dashboard (`/`)

Layout:
```
┌─────────────────────────────────────────────────────┐
│  SoundPulse              [data freshness] [settings] │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌──────────────────┐  ┌────────────────────────┐   │
│  │ TRENDING NOW     │  │ BREAKOUT PREDICTIONS   │   │
│  │ [Tracks|Artists] │  │ 🔥 About to blow up    │   │
│  │                  │  │                        │   │
│  │ 1. Track Name    │  │ Artist X  ↑108%  78%   │   │
│  │    ████████ 87.3 │  │ confidence ████████░░  │   │
│  │    ~~sparkline~~ │  │ top signal: shazam     │   │
│  │                  │  │                        │   │
│  │ 2. Track Name    │  │ Artist Y  ↑65%   62%   │   │
│  │    ██████░░ 72.1 │  │ confidence ██████░░░░  │   │
│  │    ~~sparkline~~ │  │ top signal: tiktok     │   │
│  │                  │  │                        │   │
│  │ ... top 20       │  │ ... top 5              │   │
│  └──────────────────┘  └────────────────────────┘   │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │ GENRE MOMENTUM HEATMAP                       │   │
│  │ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐  │   │
│  │ │POP │ │ROCK│ │ELEC│ │HIP │ │R&B │ │LATN│  │   │
│  │ │ 72 │ │ 45 │ │ 88 │ │ 65 │ │ 58 │ │ 81 │  │   │
│  │ └────┘ └────┘ └────┘ └────┘ └────┘ └────┘  │   │
│  │ (colored by momentum: red=hot, blue=cool)    │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

Key behaviors:
- Toggle between Tracks and Artists in trending panel
- Sparklines show last 7 days of composite_score
- Prediction cards show confidence as a filled bar
- Genre heatmap: each cell is a root category, color intensity = momentum
- Click any entity → navigate to `/explore?entity={id}` for detail view
- Auto-refresh trending every 60 seconds

### Explore (`/explore`)

Layout:
```
┌─────────────────────────────────────────────────────┐
│  [🔍 Search artists, tracks...              ]       │
│                                                      │
│  ┌──── FILTERS ────┐  ┌──── RESULTS ────────────┐  │
│  │                  │  │                          │  │
│  │ Entity Type      │  │ Filtered trending list   │  │
│  │ ○ Tracks         │  │ with full platform       │  │
│  │ ○ Artists        │  │ breakdown per entity     │  │
│  │                  │  │                          │  │
│  │ Time Range       │  │ Click to expand:         │  │
│  │ [Today|7d|30d]   │  │ ┌──────────────────────┐│  │
│  │                  │  │ │ Sabrina Carpenter     ││  │
│  │ Platform         │  │ │ Composite: 87.3       ││  │
│  │ □ Spotify        │  │ │ Spotify:  91.2 ██████ ││  │
│  │ □ TikTok         │  │ │ TikTok:   85.6 █████░││  │
│  │ □ Shazam         │  │ │ Shazam:   78.4 ████░░││  │
│  │ □ Apple Music    │  │ │ Apple:    82.0 █████░ ││  │
│  │                  │  │ │                       ││  │
│  │ Genre            │  │ │ Predictions:          ││  │
│  │ ▸ Pop            │  │ │ 7d: ↑12% (conf 82%)  ││  │
│  │ ▸ Electronic     │  │ │ 30d: ↑25% (conf 64%) ││  │
│  │   ▸ House        │  │ └──────────────────────┘│  │
│  │     ▸ Deep House │  │                          │  │
│  │     ▸ Tech House │  │                          │  │
│  │ ▸ Hip-Hop        │  │                          │  │
│  │ ...              │  │                          │  │
│  └──────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

Key behaviors:
- Search bar with debounced autocomplete (300ms)
- Genre tree is expandable/collapsible, clicking a genre filters results
- Platform filter checkboxes control `min_platforms` param
- Entity detail expands inline with per-platform score bars
- Predictions for selected entity shown in expanded view

### API Playground (`/api-tester`)

Layout:
```
┌─────────────────────────────────────────────────────┐
│  API PLAYGROUND                                      │
│                                                      │
│  Endpoint: [GET ▼] [/trending            ▼]  [Send] │
│                                                      │
│  ┌──── PARAMETERS ──┐  ┌──── RESPONSE ──────────┐  │
│  │                   │  │                         │  │
│  │ entity_type       │  │ Status: 200 OK          │  │
│  │ [track      ▼]   │  │ Time: 42ms              │  │
│  │                   │  │                         │  │
│  │ time_range        │  │ {                       │  │
│  │ [today     ▼]    │  │   "data": [             │  │
│  │                   │  │     {                   │  │
│  │ genre             │  │       "entity": {       │  │
│  │ [____________]    │  │         "name": "..."   │  │
│  │                   │  │       },                │  │
│  │ limit             │  │       "scores": { ... } │  │
│  │ [50___________]   │  │     }                   │  │
│  │                   │  │   ],                    │  │
│  │ min_platforms      │  │   "meta": { ... }      │  │
│  │ [1____________]   │  │ }                       │  │
│  │                   │  │                         │  │
│  └───────────────────┘  │ [Copy JSON] [Copy cURL] │  │
│                         └─────────────────────────┘  │
│                                                      │
│  ┌──── HISTORY ─────────────────────────────────┐   │
│  │ GET /trending?entity_type=track       42ms ✅ │   │
│  │ GET /search?q=drake                   28ms ✅ │   │
│  │ GET /predictions?horizon=7d           65ms ✅ │   │
│  │ GET /genres                          120ms ✅ │   │
│  └───────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

Key behaviors:
- Endpoint dropdown auto-populates parameter form based on endpoint schema
- Parameter form auto-generates: dropdowns for enum fields, number inputs for ints, text for strings
- Send button fires request and shows response with syntax highlighting
- Response shows: status code (color-coded), response time, formatted JSON
- Copy JSON and Copy cURL buttons
- History panel shows last 20 requests with status and timing
- Clicking a history item re-populates the request builder

---

## ENDPOINT DEFINITIONS (for API tester)

```javascript
// utils/endpoints.js
export const ENDPOINTS = [
  {
    method: 'GET',
    path: '/trending',
    description: 'Get currently trending artists or tracks',
    params: [
      { name: 'entity_type', type: 'enum', options: ['track', 'artist'], required: true },
      { name: 'time_range', type: 'enum', options: ['today', '7d', '30d'], default: 'today' },
      { name: 'genre', type: 'string', placeholder: 'e.g. electronic.house' },
      { name: 'platform', type: 'enum', options: ['spotify', 'apple_music', 'tiktok', 'shazam', 'radio', 'chartmetric'] },
      { name: 'limit', type: 'number', default: 50, min: 10, max: 100 },
      { name: 'offset', type: 'number', default: 0 },
      { name: 'sort', type: 'enum', options: ['composite_score', 'velocity', 'platform_rank'], default: 'composite_score' },
      { name: 'min_platforms', type: 'number', default: 1, min: 1, max: 6 },
    ],
  },
  {
    method: 'GET',
    path: '/search',
    description: 'Search artists and tracks',
    params: [
      { name: 'q', type: 'string', required: true, placeholder: 'Search query' },
      { name: 'type', type: 'enum', options: ['all', 'artist', 'track'], default: 'all' },
      { name: 'limit', type: 'number', default: 20, min: 1, max: 50 },
    ],
  },
  {
    method: 'GET',
    path: '/predictions',
    description: 'Get breakout predictions',
    params: [
      { name: 'entity_type', type: 'enum', options: ['all', 'artist', 'track', 'genre'], default: 'all' },
      { name: 'horizon', type: 'enum', options: ['7d', '30d', '90d'], default: '7d' },
      { name: 'genre', type: 'string', placeholder: 'e.g. hip-hop.trap' },
      { name: 'min_confidence', type: 'number', default: 0, min: 0, max: 1, step: 0.1 },
      { name: 'limit', type: 'number', default: 50, min: 10, max: 200 },
      { name: 'sort', type: 'enum', options: ['predicted_change', 'confidence', 'predicted_score'], default: 'predicted_change' },
    ],
  },
  {
    method: 'GET',
    path: '/genres',
    description: 'Get genre taxonomy',
    params: [
      { name: 'root', type: 'string', placeholder: 'e.g. electronic' },
      { name: 'depth', type: 'number', min: 0, max: 4 },
      { name: 'status', type: 'enum', options: ['active', 'deprecated', 'proposed', 'all'], default: 'active' },
      { name: 'flat', type: 'boolean', default: false },
    ],
  },
  {
    method: 'GET',
    path: '/genres/{genre_id}',
    description: 'Get single genre detail',
    params: [
      { name: 'genre_id', type: 'path', required: true, placeholder: 'e.g. electronic.house.tech-house' },
    ],
  },
];
```

---

## DESIGN DIRECTION

- **Dark mode default** — `bg-zinc-950` base, `zinc-900` cards, `zinc-800` borders
- **Accent**: electric violet `#8B5CF6` for primary actions + highlights
- **Secondary accent**: emerald `#10B981` for positive trends, rose `#F43F5E` for negative
- **Typography**: Monospace for data/numbers (`JetBrains Mono` via Google Fonts), sans-serif for labels (`Space Grotesk` or `DM Sans`)
- **Sparklines**: Thin, smooth SVG paths — green for uptrend, red for downtrend
- **Confidence bars**: Gradient fill from zinc to accent color
- **Cards**: Subtle border, no shadows, slight hover glow on interactive elements
- **Transitions**: 150ms ease-out on hovers, 200ms on state changes
- **Skeleton screens**: Pulsing zinc-800 blocks while loading (no spinners)

This should feel like a Bloomberg terminal for music — dense with data, professionally serious, but with enough color to be inviting.
