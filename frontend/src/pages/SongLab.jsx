import { useState } from 'react'
import { Music, Sparkles, Copy, Check, Zap, TrendingUp, BarChart3 } from 'lucide-react'
import { useGenreOpportunities, useGenerateBlueprint } from '../hooks/useSoundPulse'

const MODELS = [
  { id: 'suno', name: 'Suno', desc: 'Full songs with vocals + lyrics' },
  { id: 'udio', name: 'Udio', desc: 'Audio conditioning + style transfer' },
  { id: 'soundraw', name: 'SOUNDRAW', desc: 'Structured params, royalty-free' },
  { id: 'musicgen', name: 'MusicGen', desc: 'Open source, instrumental only' },
]

function OpportunityBar({ score }) {
  const width = Math.min(100, score * 100)
  const color = score > 0.6 ? 'bg-emerald-500' : score > 0.3 ? 'bg-yellow-500' : 'bg-zinc-600'
  return (
    <div className="w-20 h-2 bg-zinc-800 rounded-full overflow-hidden">
      <div className={`h-full ${color} rounded-full`} style={{ width: `${width}%` }} />
    </div>
  )
}

export default function SongLab() {
  const [selectedGenre, setSelectedGenre] = useState(null)
  const [selectedModel, setSelectedModel] = useState('suno')
  const [copied, setCopied] = useState(false)

  const { data: genreData, isLoading: genresLoading } = useGenreOpportunities()
  const generateBlueprint = useGenerateBlueprint()

  const genres = genreData?.data?.data || []
  const blueprint = generateBlueprint.data?.data?.data?.blueprint
  const prompt = generateBlueprint.data?.data?.data?.prompt

  const handleGenreSelect = (genre) => {
    setSelectedGenre(genre)
    setCopied(false)
    generateBlueprint.mutate({ body: { genre: genre.genre, model: selectedModel } })
  }

  const handleModelChange = (modelId) => {
    setSelectedModel(modelId)
    setCopied(false)
    if (selectedGenre) {
      generateBlueprint.mutate({ body: { genre: selectedGenre.genre, model: modelId } })
    }
  }

  const handleCopy = () => {
    const text = typeof prompt === 'string' ? prompt : JSON.stringify(prompt, null, 2)
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Music size={28} className="text-violet-400" />
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">Song Lab</h1>
          <p className="text-sm text-zinc-500">Select a genre, get a blueprint, generate a song</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Genre Opportunities */}
        <div className="lg:col-span-1 space-y-3">
          <h2 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
            Genre Opportunities
          </h2>

          {genresLoading && (
            <div className="text-zinc-500 text-sm py-8 text-center">Loading genres...</div>
          )}

          <div className="space-y-1 max-h-[calc(100vh-200px)] overflow-y-auto pr-1">
            {genres.map((g) => (
              <button
                key={g.genre}
                onClick={() => handleGenreSelect(g)}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors ${
                  selectedGenre?.genre === g.genre
                    ? 'bg-violet-600/20 border border-violet-500/50'
                    : 'bg-zinc-900 border border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-zinc-200 truncate">{g.genre_name}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    g.momentum === 'rising' ? 'bg-emerald-900/50 text-emerald-400' :
                    g.momentum === 'declining' ? 'bg-rose-900/50 text-rose-400' :
                    'bg-zinc-800 text-zinc-400'
                  }`}>
                    {g.momentum}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <OpportunityBar score={g.opportunity_score} />
                  <span className="text-xs text-zinc-500">{g.track_count} tracks</span>
                </div>
              </button>
            ))}

            {!genresLoading && genres.length === 0 && (
              <div className="text-center py-8 text-zinc-500 text-sm">
                No genre data yet. Run the scrapers to collect trending data.
              </div>
            )}
          </div>
        </div>

        {/* Right: Blueprint + Prompt */}
        <div className="lg:col-span-2 space-y-4">
          {!selectedGenre ? (
            <div className="flex flex-col items-center justify-center py-20 border border-zinc-800 rounded-lg bg-zinc-900">
              <Sparkles size={48} className="text-zinc-600 mb-4" />
              <h3 className="text-lg font-medium text-zinc-300">Select a genre to start</h3>
              <p className="text-sm text-zinc-500 mt-1">
                Pick a genre from the list to see what's working and generate a prompt
              </p>
            </div>
          ) : (
            <>
              {/* Blueprint Card */}
              {blueprint && (
                <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
                  <div className="flex items-center gap-2 mb-4">
                    <Zap size={18} className="text-violet-400" />
                    <h3 className="text-lg font-semibold text-zinc-200">
                      Blueprint: {blueprint.genre_name}
                    </h3>
                    <span className="text-xs text-zinc-500 ml-auto">
                      Based on {blueprint.sample_size} trending tracks
                    </span>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    {blueprint.sonic_profile.tempo && (
                      <div className="bg-zinc-800/50 rounded-lg p-3">
                        <div className="text-xs text-zinc-500">Tempo</div>
                        <div className="text-lg font-bold text-zinc-100">{blueprint.sonic_profile.tempo} BPM</div>
                        {blueprint.sonic_profile.tempo_range && (
                          <div className="text-xs text-zinc-500">Range: {blueprint.sonic_profile.tempo_range}</div>
                        )}
                      </div>
                    )}
                    {blueprint.sonic_profile.key_display && (
                      <div className="bg-zinc-800/50 rounded-lg p-3">
                        <div className="text-xs text-zinc-500">Key</div>
                        <div className="text-lg font-bold text-zinc-100">{blueprint.sonic_profile.key_display}</div>
                      </div>
                    )}
                    {blueprint.sonic_profile.energy != null && (
                      <div className="bg-zinc-800/50 rounded-lg p-3">
                        <div className="text-xs text-zinc-500">Energy</div>
                        <div className="text-lg font-bold text-zinc-100">{(blueprint.sonic_profile.energy * 100).toFixed(0)}%</div>
                        <div className="text-xs text-zinc-500">{blueprint.sonic_profile.energy_description}</div>
                      </div>
                    )}
                    {blueprint.sonic_profile.valence != null && (
                      <div className="bg-zinc-800/50 rounded-lg p-3">
                        <div className="text-xs text-zinc-500">Mood</div>
                        <div className="text-lg font-bold text-zinc-100">{(blueprint.sonic_profile.valence * 100).toFixed(0)}%</div>
                        <div className="text-xs text-zinc-500">{blueprint.sonic_profile.mood}</div>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-2">
                    {blueprint.lyrical_profile.top_themes.map(theme => (
                      <span key={theme} className="px-2 py-1 bg-violet-600/20 text-violet-300 rounded text-xs">
                        {theme}
                      </span>
                    ))}
                    {blueprint.genre_tags?.map(tag => (
                      <span key={tag} className="px-2 py-1 bg-zinc-800 text-zinc-400 rounded text-xs">
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Model Selector */}
              <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4">
                <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
                  Generation Model
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                  {MODELS.map(m => (
                    <button
                      key={m.id}
                      onClick={() => handleModelChange(m.id)}
                      className={`p-3 rounded-lg text-left transition-colors ${
                        selectedModel === m.id
                          ? 'bg-violet-600/20 border border-violet-500/50'
                          : 'bg-zinc-800/50 border border-zinc-800 hover:border-zinc-700'
                      }`}
                    >
                      <div className="text-sm font-medium text-zinc-200">{m.name}</div>
                      <div className="text-xs text-zinc-500 mt-0.5">{m.desc}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Generated Prompt */}
              {prompt && (
                <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider">
                      Generated Prompt — {selectedModel}
                    </h3>
                    <button
                      onClick={handleCopy}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 rounded text-xs text-zinc-300 transition-colors"
                    >
                      {copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                      {copied ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <pre className="bg-zinc-950 rounded-lg p-4 text-sm text-zinc-300 whitespace-pre-wrap overflow-auto max-h-96 font-mono leading-relaxed">
                    {typeof prompt === 'string' ? prompt : JSON.stringify(prompt, null, 2)}
                  </pre>
                </div>
              )}

              {generateBlueprint.isPending && (
                <div className="text-center py-8 text-zinc-500">
                  Generating blueprint...
                </div>
              )}

              {generateBlueprint.isError && (
                <div className="text-center py-4 text-rose-400 text-sm">
                  Error generating blueprint. Make sure there's trending data for this genre.
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
