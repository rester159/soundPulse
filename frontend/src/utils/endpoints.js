export const ENDPOINTS = [
  {
    method: 'GET',
    path: '/trending',
    description: 'Get currently trending artists or tracks',
    params: [
      { name: 'entity_type', type: 'enum', options: ['track', 'artist'], required: true },
      { name: 'time_range', type: 'enum', options: ['today', '7d', '30d'], default: 'today' },
      { name: 'genre', type: 'string', placeholder: 'e.g. electronic.house' },
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
      { name: 'entity_type', type: 'enum', options: ['all', 'artist', 'track'], default: 'all' },
      { name: 'horizon', type: 'enum', options: ['7d', '30d', '90d'], default: '7d' },
      { name: 'genre', type: 'string', placeholder: 'e.g. hip-hop.trap' },
      { name: 'min_confidence', type: 'number', default: 0, min: 0, max: 1, step: 0.1 },
      { name: 'limit', type: 'number', default: 50, min: 10, max: 200 },
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
      { name: 'genre_id', type: 'path', required: true, placeholder: 'e.g. electronic.house' },
    ],
  },
  {
    method: 'POST',
    path: '/trending',
    description: 'Ingest trending data (admin)',
    params: [
      { name: 'platform', type: 'enum', options: ['spotify', 'shazam', 'apple_music', 'tiktok', 'radio', 'chartmetric'], required: true },
      { name: 'entity_type', type: 'enum', options: ['track', 'artist'], required: true },
    ],
    body: true,
  },
]
