import { useState, useEffect, useRef } from 'react'
import {
  Disc3, Loader2, ChevronDown, ChevronUp, CheckCircle2, Music2,
  Clock, FileAudio, AlertCircle, PlayCircle, Layers, Mic2,
  Crosshair, Save, Play, Pause, Square,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import {
  useSongs, useSong, useMarkQaPassed, useSongStems, getBaseUrl,
  useInstrumentalAnalysis, useNudgeVocalEntry, useUpdateInstrumentalMarkers,
} from '../hooks/useSoundPulse'

// Reuse the backend-relative → absolute URL helper
function resolveAudioUrl(url) {
  if (!url) return url
  if (/^https?:\/\//i.test(url)) return url
  if (url.startsWith('/api/v1/')) {
    const base = getBaseUrl().replace(/\/api\/v1\/?$/, '')
    return base + url
  }
  return url
}

const STATUS_COLORS = {
  draft:               'bg-zinc-700/30 text-zinc-300 border-zinc-600/40',
  qa_pending:          'bg-amber-500/15 text-amber-300 border-amber-500/30',
  qa_failed:           'bg-rose-500/15 text-rose-300 border-rose-500/30',
  qa_passed:           'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  assigned_to_release: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  submitted:           'bg-sky-500/15 text-sky-300 border-sky-500/30',
  live:                'bg-emerald-500/25 text-emerald-200 border-emerald-500/40',
  archived:            'bg-zinc-800 text-zinc-500 border-zinc-700',
  taken_down:          'bg-rose-500/10 text-rose-400 border-rose-500/30',
}

function StatusPill({ status }) {
  const cls = STATUS_COLORS[status] || 'bg-zinc-800 text-zinc-400 border-zinc-700'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded border text-[10px] font-semibold uppercase tracking-wider ${cls}`}>
      {status?.replace(/_/g, ' ')}
    </span>
  )
}

// Stem-aware audio player. Default-plays final_mixed (the vocal-on-
// original-instrumental mix) if available, otherwise falls back to
// the master audio asset. Shows a toggle strip so the CEO can A/B
// between mixed / vocals-only / suno-original / drums / bass / other.
function StemAwareAudioPlayer({ song, masterUrl, masterMeta }) {
  const { data: stemsData, isLoading: stemsLoading } = useSongStems(song.song_id)
  const stems = stemsData?.data?.stems || []
  const job = stemsData?.data?.job
  const [selectedStem, setSelectedStem] = useState(null)

  // Pick the default playback source: final_mixed > master
  const hasFinalMixed = stems.find(s => s.stem_type === 'final_mixed')
  const activeStem = selectedStem || (hasFinalMixed ? hasFinalMixed.stem_type : null)
  const playbackUrl = activeStem
    ? resolveAudioUrl(stems.find(s => s.stem_type === activeStem)?.stream_url || masterUrl)
    : resolveAudioUrl(masterUrl)

  const STEM_META = {
    final_mixed:   { label: 'Mixed',   desc: 'vocals over original instrumental', Icon: Layers },
    vocals_only:   { label: 'Vocals',  desc: 'isolated vocal stem',               Icon: Mic2 },
    suno_original: { label: 'Suno',    desc: 'full Suno output (no mix)',         Icon: Music2 },
    drums:         { label: 'Drums',   desc: 'drum stem',                         Icon: Music2 },
    bass:          { label: 'Bass',    desc: 'bass stem',                         Icon: Music2 },
    other:         { label: 'Other',   desc: 'other instruments',                 Icon: Music2 },
  }

  const currentLabel = activeStem ? STEM_META[activeStem]?.label : 'Master'
  const currentDesc = activeStem
    ? STEM_META[activeStem]?.desc
    : `${masterMeta.provider} · ${masterMeta.format} · ${masterMeta.duration_seconds?.toFixed(1)}s`

  return (
    <div className="space-y-2">
      <div className="text-[10px] uppercase tracking-wider text-zinc-500 flex items-center gap-1">
        <PlayCircle size={10} /> Playing: <span className="text-violet-300">{currentLabel}</span> — {currentDesc}
      </div>
      <audio
        key={playbackUrl}
        controls
        src={playbackUrl}
        className="w-full"
        style={{ filter: 'invert(0.9) hue-rotate(180deg)' }}
      />

      {/* Stem toggle strip — only visible if we have at least one stem */}
      {stems.length > 0 && (
        <div className="flex items-center gap-1.5 flex-wrap pt-1">
          <div className="text-[10px] text-zinc-500 uppercase tracking-wider mr-1">
            <Layers size={10} className="inline mr-0.5" /> Stems:
          </div>
          {stems.map(s => {
            const meta = STEM_META[s.stem_type] || { label: s.stem_type, Icon: FileAudio }
            const isActive = activeStem === s.stem_type
            const Icon = meta.Icon
            return (
              <button
                key={s.id}
                onClick={() => setSelectedStem(s.stem_type)}
                className={`px-2 py-0.5 text-[10px] rounded border flex items-center gap-1 transition-colors ${
                  isActive
                    ? 'bg-violet-500/20 border-violet-500 text-violet-200'
                    : 'bg-zinc-900 border-zinc-800 text-zinc-400 hover:border-zinc-700 hover:text-zinc-200'
                }`}
                title={meta.desc}
              >
                <Icon size={10} />
                {meta.label}
                {s.size_bytes && (
                  <span className="text-[9px] opacity-60">
                    {Math.round(s.size_bytes / 1024)} KB
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}

      {/* Job status — shown while stems are being processed */}
      {job && job.status === 'pending' && (
        <div className="flex items-center gap-1.5 text-[10px] text-amber-400">
          <Clock size={10} /> Stem extraction queued — waiting for stem-extractor microservice
        </div>
      )}
      {job && job.status === 'in_progress' && (
        <div className="flex items-center gap-1.5 text-[10px] text-violet-300">
          <Loader2 size={10} className="animate-spin" /> {job.job_type === 'remix_only'
            ? 'Remixing vocals onto instrumental…'
            : 'Demucs separating vocals + mixing onto original instrumental…'}
        </div>
      )}
      {job && job.status === 'failed' && job.error_message && (
        <div className="text-[10px] text-rose-400 flex items-center gap-1">
          <AlertCircle size={10} /> Stem extraction failed: {job.error_message.slice(0, 100)}
        </div>
      )}
      {stemsLoading && !job && (
        <div className="text-[10px] text-zinc-600 flex items-center gap-1">
          <Loader2 size={10} className="animate-spin" /> Checking for stems…
        </div>
      )}

      {/* Vocal entry studio — two-track alignment UI. Only shown once
          the first full stem extraction has completed, because the
          vocals_only stem is what we preview against the instrumental
          and the remix_only path requires it to be cached. */}
      {job?.source_instrumental_id && stems.find(s => s.stem_type === 'vocals_only') && (
        <VocalEntryStudio
          instrumentalId={job.source_instrumental_id}
          songId={song.song_id}
          vocalsStem={stems.find(s => s.stem_type === 'vocals_only')}
          jobStatus={job.status}
        />
      )}
    </div>
  )
}


// ---- Waveform helpers (shared by both lanes) ---------------------
//
// computePeaks: fetch the audio, decode via the Web Audio API, and
// downsample channel[0] to `numPeaks` max-amplitude buckets.
// drawWaveform: paint the peaks as vertical bars on a <canvas>,
// centered vertically, DPR-aware so it stays sharp on retina.
// Both are pure utilities — no React, no component state.

async function computeAudioPeaks(url, numPeaks = 1500) {
  const resp = await fetch(url)
  if (!resp.ok) throw new Error(`fetch ${url} → ${resp.status}`)
  const buffer = await resp.arrayBuffer()
  const AudioContextClass = window.AudioContext || window.webkitAudioContext
  if (!AudioContextClass) throw new Error('no AudioContext')
  const ctx = new AudioContextClass()
  try {
    const audio = await ctx.decodeAudioData(buffer)
    const channel = audio.getChannelData(0)
    const stride = Math.max(1, Math.floor(channel.length / numPeaks))
    const peaks = new Float32Array(numPeaks)
    for (let i = 0; i < numPeaks; i++) {
      let maxAbs = 0
      const base = i * stride
      const end = Math.min(channel.length, base + stride)
      // Sub-sample inside the bucket for speed; 64-sample stride is
      // enough for visual peak detection.
      for (let j = base; j < end; j += 64) {
        const v = Math.abs(channel[j])
        if (v > maxAbs) maxAbs = v
      }
      peaks[i] = maxAbs
    }
    return peaks
  } finally {
    // Closing the context releases the decoded buffer; we only need
    // the peaks float array after this.
    if (ctx.close) ctx.close()
  }
}

function drawWaveform(canvas, peaks, color) {
  if (!canvas || !peaks) return
  const rect = canvas.getBoundingClientRect()
  if (rect.width === 0 || rect.height === 0) return
  const dpr = window.devicePixelRatio || 1
  canvas.width = Math.max(1, Math.floor(rect.width * dpr))
  canvas.height = Math.max(1, Math.floor(rect.height * dpr))
  const c = canvas.getContext('2d')
  if (!c) return
  c.setTransform(1, 0, 0, 1, 0, 0)
  c.scale(dpr, dpr)
  c.clearRect(0, 0, rect.width, rect.height)
  c.fillStyle = color
  const W = rect.width
  const H = rect.height
  const midY = H / 2
  const barW = W / peaks.length
  for (let i = 0; i < peaks.length; i++) {
    const h = Math.max(1, peaks[i] * H * 0.85)
    const x = i * barW
    c.fillRect(x, midY - h / 2, Math.max(1, barW * 0.9), h)
  }
}


// Two-track vocal-entry studio. The CEO gets an instrumental lane with
// start+end pins (to scope an audition region), a voice lane with a
// single draggable entry pin (mouse drag OR arrow-key ±0.1s), and
// three playback modes: instrumental region only, voice alone, and
// "play together" which overlays both at the current alignment so
// the CEO can hear the mix before committing. Save writes the new
// value to instrumentals.vocal_entry_seconds and enqueues a
// remix_only stem job that reuses the cached vocals_only stem.
//
// Positions are stored in seconds; pin px positions are derived from
// the instrumental duration and the live lane width on each render.
// Keyboard nudging is only active while the green voice block is
// focused (tabIndex=0) — click the block to capture the keyboard.
function VocalEntryStudio({ instrumentalId, songId, vocalsStem, jobStatus }) {
  const { data: analysisData } = useInstrumentalAnalysis(instrumentalId)
  const analysis = analysisData?.data
  const nudge = useNudgeVocalEntry()
  const markerMut = useUpdateInstrumentalMarkers()

  const instrUrl = resolveAudioUrl(analysis?.public_url_path)
  const instrDur = Number(analysis?.duration_seconds) || 0
  const voiceUrl = resolveAudioUrl(vocalsStem?.stream_url)
  const voiceDur = Number(vocalsStem?.duration_seconds) || 0
  const serverVoiceEntry = Number(analysis?.vocal_entry_seconds) || 0

  const [instrStart, setInstrStart] = useState(0)
  const [instrEnd, setInstrEnd] = useState(0)
  const [voiceEntry, setVoiceEntry] = useState(0)
  // Session-only scratch pin on the voice lane. `null` means no pin;
  // number = OFFSET in seconds from voiceEntry (NOT absolute
  // instrumental-axis seconds). Storing as an offset means the pin
  // is "attached" to the voice block — when the CEO drags the green
  // block from 10s to 20s, the orange pin slides with it instead of
  // staying at its old absolute position. Absolute render position
  // is always voiceEntry + orangePin.
  const [orangePin, setOrangePin] = useState(null)
  // Horizontal zoom level for the timeline lanes. 1x = the whole
  // duration fits in the visible width; 3x / 5x widen the inner
  // content and scroll horizontally so pins are easier to click and
  // waveform peaks are actually legible.
  const [zoomLevel, setZoomLevel] = useState(3)
  // Decoded waveform peak arrays — one per track. Null while loading.
  const [instrPeaks, setInstrPeaks] = useState(null)
  const [voicePeaks, setVoicePeaks] = useState(null)
  // What's currently playing. Drives the lane-level play/pause icons.
  const [playing, setPlaying] = useState('none')  // 'none' | 'instr' | 'voice' | 'together'

  // Visual marker pins — derived directly from the analysis response
  // so reload survives. Adds/removes go through useUpdateInstrumentalMarkers,
  // which optimistically updates the react-query cache so the UI
  // never flickers between click and server confirm.
  const visualPins = Array.isArray(analysis?.analysis_json?.markers)
    ? analysis.analysis_json.markers
        .map((m) => Number(m))
        .filter((m) => Number.isFinite(m))
    : []
  // Bump this counter any time the user ENDS an interaction
  // (pointerup on a drag, or key press). The useEffect watches it
  // and (re)starts the preview playback — we don't auto-play on
  // every render, only on user-intent boundaries.
  const [playKey, setPlayKey] = useState(0)

  // Seed state when the analysis first arrives / the instrumental changes
  useEffect(() => {
    if (analysis?.duration_seconds) {
      setInstrStart(0)
      setInstrEnd(Number(analysis.duration_seconds))
      setVoiceEntry(Number(analysis.vocal_entry_seconds) || 0)
    }
  }, [analysis?.instrumental_id, analysis?.duration_seconds])

  const instrRef = useRef(null)
  const voiceRef = useRef(null)
  const laneRef = useRef(null)               // inner instrumental content div
  const voiceLaneRef = useRef(null)           // inner voice content div
  const instrCanvasRef = useRef(null)         // waveform canvas (instrumental)
  const voiceCanvasRef = useRef(null)         // waveform canvas (voice)
  const playCtlRef = useRef({ voiceStartTimer: null, stopTimer: null })
  // Playhead DOM refs — bars + labels that slide across each lane
  // while that audio is playing. Direct-manipulated via rAF so we
  // don't trigger React re-renders 60 times a second.
  const instrPlayheadRef = useRef(null)
  const instrPlayheadLabelRef = useRef(null)
  const voicePlayheadRef = useRef(null)
  const voicePlayheadLabelRef = useRef(null)
  const rafRef = useRef(null)

  const busy = nudge.isPending || jobStatus === 'in_progress' || jobStatus === 'pending'
  const dirty = Math.abs(voiceEntry - serverVoiceEntry) > 0.0005

  function stopAll() {
    const p = playCtlRef.current
    if (p.voiceStartTimer) { clearTimeout(p.voiceStartTimer); p.voiceStartTimer = null }
    if (p.stopTimer) { clearTimeout(p.stopTimer); p.stopTimer = null }
    if (instrRef.current) { instrRef.current.pause() }
    if (voiceRef.current) { voiceRef.current.pause() }
    stopPlayheadLoop()
    setPlaying('none')
  }

  // rAF-driven playhead: reads instr/voice currentTime every frame
  // and positions the yellow bars inside each lane. Text label shows
  // the instrumental-time-axis position (so the voice label reads the
  // same coordinate system as the green block the user dragged).
  function startPlayheadLoop() {
    if (rafRef.current != null) return  // already running
    const tick = () => {
      const instrEl = instrRef.current
      const voiceEl = voiceRef.current
      const instrBar = instrPlayheadRef.current
      const instrLabel = instrPlayheadLabelRef.current
      const voiceBar = voicePlayheadRef.current
      const voiceLabel = voicePlayheadLabelRef.current

      // Instrumental playhead
      if (instrBar) {
        if (instrEl && !instrEl.paused && instrDur > 0) {
          const t = instrEl.currentTime
          const pctVal = (Math.max(0, Math.min(instrDur, t)) / instrDur) * 100
          instrBar.style.left = `${pctVal}%`
          instrBar.style.display = 'block'
          if (instrLabel) instrLabel.textContent = `${t.toFixed(2)}s`
        } else {
          instrBar.style.display = 'none'
        }
      }

      // Voice playhead — mapped into the shared instrumental time
      // axis. The voice file's own t=0 corresponds to the left edge
      // of the green block at `voiceEntry`.
      if (voiceBar) {
        if (voiceEl && !voiceEl.paused && instrDur > 0) {
          const vt = voiceEl.currentTime
          const mapped = voiceEntry + vt
          const pctVal = (Math.max(0, Math.min(instrDur, mapped)) / instrDur) * 100
          voiceBar.style.left = `${pctVal}%`
          voiceBar.style.display = 'block'
          if (voiceLabel) voiceLabel.textContent = `${mapped.toFixed(2)}s`
        } else {
          voiceBar.style.display = 'none'
        }
      }

      // Keep ticking as long as something is still playing
      const stillPlaying =
        (instrEl && !instrEl.paused) || (voiceEl && !voiceEl.paused)
      if (stillPlaying) {
        rafRef.current = requestAnimationFrame(tick)
      } else {
        rafRef.current = null
      }
    }
    rafRef.current = requestAnimationFrame(tick)
  }

  function stopPlayheadLoop() {
    if (rafRef.current != null) {
      cancelAnimationFrame(rafRef.current)
      rafRef.current = null
    }
    if (instrPlayheadRef.current) instrPlayheadRef.current.style.display = 'none'
    if (voicePlayheadRef.current) voicePlayheadRef.current.style.display = 'none'
  }

  // Pause → seek → wait for 'seeked' (or metadata ready) → play.
  // The naive `ia.currentTime = X; ia.play()` sequence loses the seek
  // on browsers that haven't buffered far enough yet — you get audio
  // from t=0 instead of t=X. The 'seeked' event fires only once the
  // browser has committed the new playhead position; waiting for it
  // means play() always starts at the requested time.
  async function seekAndPlay(audioEl, targetTime) {
    if (!audioEl) return
    audioEl.pause()

    // Metadata needs to be loaded before currentTime can be written.
    if (audioEl.readyState < 1 /* HAVE_METADATA */) {
      await new Promise((resolve) => {
        let done = false
        const finish = () => {
          if (done) return
          done = true
          audioEl.removeEventListener('loadedmetadata', finish)
          resolve()
        }
        audioEl.addEventListener('loadedmetadata', finish)
        // Kick the load in case preload was deferred by the browser
        try { audioEl.load() } catch {}
        setTimeout(finish, 3000)  // hard fallback
      })
    }

    const clamped = Math.max(0, Math.min(audioEl.duration || targetTime, targetTime))
    if (Math.abs(audioEl.currentTime - clamped) > 0.01) {
      await new Promise((resolve) => {
        let done = false
        const finish = () => {
          if (done) return
          done = true
          audioEl.removeEventListener('seeked', finish)
          resolve()
        }
        audioEl.addEventListener('seeked', finish)
        try { audioEl.currentTime = clamped } catch {}
        setTimeout(finish, 500)  // fallback if 'seeked' never fires
      })
    }

    try { await audioEl.play() } catch {}
  }

  async function playInstrRegion() {
    stopAll()
    const ia = instrRef.current
    if (!ia || !instrUrl) return
    setPlaying('instr')
    await seekAndPlay(ia, Math.max(0, Math.min(instrDur, instrStart)))
    startPlayheadLoop()
    const durationMs = Math.max(0, (instrEnd - instrStart) * 1000)
    if (durationMs > 0) {
      playCtlRef.current.stopTimer = setTimeout(() => {
        if (instrRef.current) instrRef.current.pause()
        stopPlayheadLoop()
        setPlaying('none')
      }, durationMs)
    }
  }

  async function playVoiceAlone() {
    stopAll()
    const va = voiceRef.current
    if (!va || !voiceUrl) return
    setPlaying('voice')
    await seekAndPlay(va, 0)
    startPlayheadLoop()
  }

  async function playTogether() {
    stopAll()
    const ia = instrRef.current
    const va = voiceRef.current
    if (!ia || !va || !instrUrl || !voiceUrl) return
    setPlaying('together')

    // Start the instrumental at instrStart. When the playhead reaches
    // voiceEntry, start the voice from its own t=0. If voiceEntry <
    // instrStart we clamp the delay to 0 and seek the voice forward
    // to cover the missing head — that way the two stay aligned even
    // when the user has zoomed the instrumental region past the
    // intended vocal entry.
    const delaySec = voiceEntry - instrStart
    if (delaySec < 0) {
      // Voice needs to start ahead — seek forward in the voice stem
      await seekAndPlay(va, -delaySec)
    }
    // Now line up the instrumental. seekAndPlay awaits the seeked
    // event so when it returns, the playhead is at instrStart.
    await seekAndPlay(ia, Math.max(0, Math.min(instrDur, instrStart)))

    if (delaySec >= 0) {
      // Voice joins after `delaySec` of instrumental. Schedule its
      // play from t=0. seekAndPlay handles the seek robustness.
      playCtlRef.current.voiceStartTimer = setTimeout(() => {
        seekAndPlay(voiceRef.current, 0)
      }, delaySec * 1000)
    }

    startPlayheadLoop()

    const durationMs = Math.max(0, (instrEnd - instrStart) * 1000)
    if (durationMs > 0) {
      playCtlRef.current.stopTimer = setTimeout(() => {
        if (instrRef.current) instrRef.current.pause()
        if (voiceRef.current) voiceRef.current.pause()
        stopPlayheadLoop()
        setPlaying('none')
      }, durationMs)
    }
  }

  // Lane-level play/pause toggle handlers. The button on each lane
  // either starts that lane's preview or stops everything if it's
  // already the thing that's playing.
  function toggleInstr() {
    if (playing === 'instr') stopAll()
    else playInstrRegion()
  }
  function toggleVoice() {
    if (playing === 'voice') stopAll()
    else playVoiceAlone()
  }
  function toggleTogether() {
    if (playing === 'together') stopAll()
    else playTogether()
  }

  // Auto-preview the instrumental region whenever the user has just
  // finished a drag/key action. Skip the initial seed render.
  const initRef = useRef(false)
  useEffect(() => {
    if (!initRef.current) { initRef.current = true; return }
    playInstrRegion()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playKey])

  // Clean up audio + playhead rAF on unmount
  useEffect(() => () => { stopAll(); stopPlayheadLoop() }, [])

  // Decode the instrumental into peaks once the URL is known.
  // Debounced with a cancelled flag so unmount during fetch doesn't
  // leak a setState onto an unmounted component.
  useEffect(() => {
    if (!instrUrl) return
    let cancelled = false
    setInstrPeaks(null)
    computeAudioPeaks(instrUrl, 1500)
      .then((p) => { if (!cancelled) setInstrPeaks(p) })
      .catch((e) => console.warn('instr peaks failed:', e))
    return () => { cancelled = true }
  }, [instrUrl])

  // Same for the vocals stem.
  useEffect(() => {
    if (!voiceUrl) return
    let cancelled = false
    setVoicePeaks(null)
    computeAudioPeaks(voiceUrl, 1500)
      .then((p) => { if (!cancelled) setVoicePeaks(p) })
      .catch((e) => console.warn('voice peaks failed:', e))
    return () => { cancelled = true }
  }, [voiceUrl])

  // (Re)draw each canvas whenever its peaks change OR the zoom level
  // changes (the canvas resizes to match the new inner content width).
  useEffect(() => {
    if (instrPeaks && instrCanvasRef.current) {
      drawWaveform(instrCanvasRef.current, instrPeaks, 'rgba(167, 139, 250, 0.35)')
    }
  }, [instrPeaks, zoomLevel])

  useEffect(() => {
    if (voicePeaks && voiceCanvasRef.current) {
      drawWaveform(voiceCanvasRef.current, voicePeaks, 'rgba(52, 211, 153, 0.4)')
    }
    // voiceEntry / voiceDur are in the dep list because the voice
    // canvas lives inside the green block, whose CSS width clips at
    // instrDur when the block would overflow. Any change to either
    // can resize the canvas and needs a fresh draw.
  }, [voicePeaks, zoomLevel, voiceEntry, voiceDur])

  // --- Drag handling -------------------------------------------------
  // We use window-level pointermove/pointerup so the drag continues
  // even when the cursor leaves the lane rect. On pointerup we bump
  // playKey which triggers the preview auto-play effect above. The
  // voice pins use the voice lane's inner rect (which has its own
  // horizontal scroll) so the drag math is consistent regardless of
  // how the user has scrolled each lane.
  function startDrag(pinKind, startEvent) {
    if (busy) return
    startEvent.preventDefault()
    startEvent.stopPropagation()
    // `preventDefault` on pointerdown suppresses the browser's default
    // "focus on click" behavior — which means tabIndex never activates
    // and our onKeyDown handlers never fire. Put focus back manually
    // so clicking a pin lights it up AND arms the keyboard nudges.
    const pinEl = startEvent.currentTarget
    if (pinEl && typeof pinEl.focus === 'function') {
      pinEl.focus()
    }
    const isVoiceSide = pinKind === 'voice' || pinKind === 'orangePin'
    const laneEl = isVoiceSide ? voiceLaneRef.current : laneRef.current
    if (!laneEl || instrDur <= 0) return
    const rect = laneEl.getBoundingClientRect()

    function onMove(e) {
      const x = Math.max(0, Math.min(rect.width, e.clientX - rect.left))
      const t = (x / rect.width) * instrDur
      if (pinKind === 'start') {
        setInstrStart(prev => Math.min(Math.max(0, t), Math.max(0, instrEnd - 0.5)))
      } else if (pinKind === 'end') {
        setInstrEnd(prev => Math.max(Math.min(instrDur, t), instrStart + 0.5))
      } else if (pinKind === 'voice') {
        setVoiceEntry(Math.max(0, Math.min(instrDur, Number(t.toFixed(3)))))
      } else if (pinKind === 'orangePin') {
        // Stored as a voice-relative offset in [0, voiceDur]. The pin
        // is rendered as a child of the green voice block so dragging
        // the block carries the pin with it automatically.
        const offset = t - voiceEntry
        setOrangePin(Math.max(0, Math.min(voiceDur, Number(offset.toFixed(3)))))
      }
    }
    function onUp() {
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      setPlayKey(k => k + 1)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
  }

  // Visual marker pins — dropped by double-click on either lane.
  // Persisted to instrumentals.analysis_json.markers via
  // useUpdateInstrumentalMarkers. The `visualPins` array above is
  // the canonical source; addVisualPin / removeVisualPin compute
  // the new array and fire the optimistic mutation.
  function addVisualPin(event) {
    // Use the lane node the event bubbled from (currentTarget), not
    // always the instrumental lane, so double-clicks on the voice
    // lane drop markers at the correct X coordinate when its
    // independent scroll has been nudged.
    const laneEl = event.currentTarget
    if (!laneEl || instrDur <= 0) return
    const rect = laneEl.getBoundingClientRect()
    const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left))
    const t = Number(((x / rect.width) * instrDur).toFixed(3))
    if (t < 0 || t > instrDur) return
    // Dedupe: if within 0.2s of an existing pin, no-op
    if (visualPins.some((p) => Math.abs(p - t) < 0.2)) return
    const next = [...visualPins, t].sort((a, b) => a - b)
    markerMut.mutate({ instrumentalId, markers: next })
  }
  function removeVisualPin(t) {
    const next = visualPins.filter((p) => Math.abs(p - t) > 0.0001)
    markerMut.mutate({ instrumentalId, markers: next })
  }

  // Click-to-focus + arrow-key nudge on the violet instrumental pins.
  // Matches the voice-block behavior: click the pin to focus it, then
  // ←/→ ±0.1 s, ↓/↑ ±1.0 s. After any nudge we bump playKey so the
  // preview region auto-replays, same as a mouse drag would.
  function onInstrPinKey(which, e) {
    if (busy) return
    let step = 0
    if (e.key === 'ArrowLeft')  step = -0.1
    else if (e.key === 'ArrowRight') step = +0.1
    else if (e.key === 'ArrowDown')  step = -1.0
    else if (e.key === 'ArrowUp')    step = +1.0
    else return
    e.preventDefault()
    if (which === 'start') {
      setInstrStart((v) => Math.max(0, Math.min(instrEnd - 0.5, Number((v + step).toFixed(3)))))
    } else {
      setInstrEnd((v) => Math.max(instrStart + 0.5, Math.min(instrDur, Number((v + step).toFixed(3)))))
    }
    setPlayKey((k) => k + 1)
  }

  function onVoiceKey(e) {
    if (busy) return
    let step = 0
    if (e.key === 'ArrowLeft')  step = -0.1
    else if (e.key === 'ArrowRight') step = +0.1
    else if (e.key === 'ArrowDown')  step = -1.0
    else if (e.key === 'ArrowUp')    step = +1.0
    else return
    e.preventDefault()
    setVoiceEntry(v => {
      const next = Math.max(0, Math.min(instrDur, Number((v + step).toFixed(3))))
      return next
    })
    setPlayKey(k => k + 1)
  }

  function onOrangePinKey(e) {
    if (orangePin == null) return
    // Delete / Backspace removes the pin.
    if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault()
      setOrangePin(null)
      return
    }
    let step = 0
    if (e.key === 'ArrowLeft')  step = -0.1
    else if (e.key === 'ArrowRight') step = +0.1
    else if (e.key === 'ArrowDown')  step = -1.0
    else if (e.key === 'ArrowUp')    step = +1.0
    else return
    e.preventDefault()
    setOrangePin(v => {
      if (v == null) return v
      const next = Number((v + step).toFixed(3))
      return Math.max(0, Math.min(voiceDur, next))
    })
  }

  function toggleOrangePin() {
    if (orangePin == null) {
      // Spawn the pin in the MIDDLE of the voice duration so it's
      // clearly visible and doesn't overlap the green block's left
      // edge (which would make it hard to click). The CEO then drags
      // or nudges the offset from there.
      const midOffset = voiceDur > 0 ? voiceDur / 2 : 1.0
      setOrangePin(Number(midOffset.toFixed(3)))
    } else {
      setOrangePin(null)
    }
  }

  function save() {
    if (!dirty) return
    nudge.mutate({ instrumentalId, vocalEntrySeconds: voiceEntry, songId })
  }

  // --- Rendering -----------------------------------------------------
  if (!analysis) {
    return (
      <div className="mt-2 p-2 text-[10px] text-zinc-600">
        <Loader2 size={10} className="inline animate-spin mr-1" /> loading vocal-entry analysis…
      </div>
    )
  }
  if (!instrDur) {
    return (
      <div className="mt-2 p-2 text-[10px] text-amber-400 border border-amber-500/30 rounded">
        This instrumental has no duration recorded yet — run the stem extractor once
        to populate it. (Or upload a fresh copy and re-link.)
      </div>
    )
  }

  // Helper: seconds → percentage of full lane width
  const pct = (s) => `${(Math.max(0, Math.min(instrDur, s)) / instrDur) * 100}%`
  const regionLeftPct = pct(instrStart)
  const regionWidthPct = `${((Math.max(0, instrEnd - instrStart)) / instrDur) * 100}%`
  const voiceLeftPct = pct(voiceEntry)
  const voiceRightPct = pct(Math.min(instrDur, voiceEntry + voiceDur))
  const voiceWidthPct = `${Math.max(0.5, ((Math.min(instrDur, voiceEntry + voiceDur) - voiceEntry)) / instrDur * 100)}%`

  return (
    <div className="mt-2 p-3 rounded border border-zinc-800 bg-zinc-950/60 text-[10px]">
      <div className="flex items-center gap-1.5 text-zinc-400 mb-2">
        <Crosshair size={10} className="text-violet-300" />
        <span className="uppercase tracking-wider">Vocal entry studio</span>
        {analysis.title && (
          <span className="text-zinc-600 truncate">· {analysis.title}</span>
        )}
        {analysis.vocal_entry_source && (
          <span className={`ml-auto px-1.5 py-0.5 rounded text-[9px] ${
            analysis.vocal_entry_source === 'manual'
              ? 'bg-violet-500/20 text-violet-300'
              : 'bg-zinc-800 text-zinc-500'
          }`}>
            {analysis.vocal_entry_source === 'manual' ? 'CEO-set' : 'auto'}
          </span>
        )}
      </div>

      {/* Instrumental lane header */}
      <div className="flex items-center gap-2 mb-1">
        <button
          onClick={toggleInstr}
          disabled={!instrUrl || busy}
          className={`w-6 h-6 flex items-center justify-center rounded border transition-colors ${
            playing === 'instr'
              ? 'bg-violet-500/30 border-violet-400 text-violet-100'
              : 'border-zinc-700 hover:border-zinc-500 text-zinc-300'
          } disabled:opacity-40`}
          title={playing === 'instr' ? 'Stop' : 'Play region'}
        >
          {playing === 'instr' ? <Pause size={12} /> : <Play size={12} />}
        </button>
        <span className="text-zinc-500">Instrumental · {instrDur.toFixed(2)}s</span>
        <span className="ml-auto text-zinc-600 font-mono">
          region {instrStart.toFixed(2)}→{instrEnd.toFixed(2)}s
        </span>
        <button
          onClick={() => setZoomLevel(z => z === 1 ? 3 : z === 3 ? 5 : 1)}
          className="px-1.5 py-0.5 rounded border border-zinc-700 hover:border-zinc-500 text-zinc-400 font-mono text-[9px]"
          title="Cycle timeline zoom (1x / 3x / 5x)"
        >
          {zoomLevel}x
        </button>
      </div>
      <div className="overflow-x-auto overflow-y-hidden mb-3 rounded border border-zinc-800 bg-zinc-900">
      <div
        ref={laneRef}
        onDoubleClick={addVisualPin}
        className="relative h-14 select-none"
        style={{ width: `${zoomLevel * 100}%`, minWidth: '100%' }}
        title="Double-click to drop a marker pin"
      >
        <canvas
          ref={instrCanvasRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
        />
        {/* Region highlight (between pins) */}
        <div
          className="absolute top-0 bottom-0 bg-violet-500/15 border-x border-violet-500/30"
          style={{ left: regionLeftPct, width: regionWidthPct }}
        />
        {/* Visual marker pins — double-click to add, click dot to remove */}
        {visualPins.map((t) => (
          <div
            key={`ip-${t}`}
            className="absolute top-0 bottom-0"
            style={{ left: pct(t), transform: 'translateX(-50%)' }}
          >
            <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-[1px] bg-amber-400/80 pointer-events-none" />
            <div
              onClick={(e) => { e.stopPropagation(); removeVisualPin(t) }}
              className="absolute top-0.5 left-1/2 -translate-x-1/2 w-2 h-2 bg-amber-400 rounded-full cursor-pointer hover:bg-rose-400 hover:scale-125 transition-all"
              title={`marker ${t.toFixed(2)}s — click to remove`}
            />
            <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-[8px] text-amber-300 font-mono whitespace-nowrap pointer-events-none">
              {t.toFixed(1)}
            </div>
          </div>
        ))}
        {/* Playhead — hidden until playback starts; updated by rAF */}
        <div
          ref={instrPlayheadRef}
          className="absolute top-0 bottom-0 pointer-events-none"
          style={{ left: '0%', display: 'none', transform: 'translateX(-50%)' }}
        >
          <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-[2px] bg-yellow-300 shadow-[0_0_6px_rgba(253,224,71,0.7)]" />
          <div
            ref={instrPlayheadLabelRef}
            className="absolute -top-3 left-1/2 -translate-x-1/2 text-[9px] text-yellow-300 font-mono whitespace-nowrap"
          >
            0.00s
          </div>
        </div>
        {/* Start pin — click to focus, arrow keys ±0.1/±1 */}
        <div
          tabIndex={0}
          onPointerDown={(e) => startDrag('start', e)}
          onKeyDown={(e) => onInstrPinKey('start', e)}
          className="absolute top-0 bottom-0 flex items-start cursor-ew-resize touch-none focus:outline-none group"
          style={{ left: regionLeftPct, transform: 'translateX(-50%)', width: '14px' }}
          title={`start ${instrStart.toFixed(3)}s (click to focus, ←→ ±0.1s, ↑↓ ±1s)`}
        >
          <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-0.5 bg-violet-400 group-focus:bg-violet-200 group-focus:w-[3px] transition-all" />
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3 h-3 bg-violet-400 rounded-sm group-focus:bg-violet-200 group-focus:scale-125 group-focus:ring-2 group-focus:ring-violet-300/60 transition-all" />
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-[9px] text-violet-300 font-mono whitespace-nowrap">
            {instrStart.toFixed(2)}
          </div>
        </div>
        {/* End pin — click to focus, arrow keys ±0.1/±1 */}
        <div
          tabIndex={0}
          onPointerDown={(e) => startDrag('end', e)}
          onKeyDown={(e) => onInstrPinKey('end', e)}
          className="absolute top-0 bottom-0 flex items-start cursor-ew-resize touch-none focus:outline-none group"
          style={{ left: pct(instrEnd), transform: 'translateX(-50%)', width: '14px' }}
          title={`end ${instrEnd.toFixed(3)}s (click to focus, ←→ ±0.1s, ↑↓ ±1s)`}
        >
          <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-0.5 bg-violet-400 group-focus:bg-violet-200 group-focus:w-[3px] transition-all" />
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3 h-3 bg-violet-400 rounded-sm group-focus:bg-violet-200 group-focus:scale-125 group-focus:ring-2 group-focus:ring-violet-300/60 transition-all" />
          <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-[9px] text-violet-300 font-mono whitespace-nowrap">
            {instrEnd.toFixed(2)}
          </div>
        </div>
      </div>
      </div>

      {/* Voice lane */}
      <div className="flex items-center gap-2 mb-1">
        <button
          onClick={toggleVoice}
          disabled={!voiceUrl || busy}
          className={`w-6 h-6 flex items-center justify-center rounded border transition-colors ${
            playing === 'voice'
              ? 'bg-emerald-500/30 border-emerald-400 text-emerald-100'
              : 'border-zinc-700 hover:border-zinc-500 text-zinc-300'
          } disabled:opacity-40`}
          title={playing === 'voice' ? 'Stop' : 'Play voice alone'}
        >
          {playing === 'voice' ? <Pause size={12} /> : <Play size={12} />}
        </button>
        <span className="text-zinc-500">
          Voice · entry at <span className="font-mono text-emerald-300">{voiceEntry.toFixed(3)}s</span>
        </span>
        <span className="ml-auto text-zinc-600 text-[9px]">click block · drag · ←→ ±0.1s · ↑↓ ±1s</span>
      </div>
      <div className="overflow-x-auto overflow-y-hidden mb-3 rounded border border-zinc-800 bg-zinc-900">
      <div
        ref={voiceLaneRef}
        onDoubleClick={addVisualPin}
        className="relative h-14 select-none"
        style={{ width: `${zoomLevel * 100}%`, minWidth: '100%' }}
        title="Double-click to drop a marker pin"
      >
        {/* Visual marker pins — shared with the instrumental lane so
            the markers form a full vertical line across both tracks. */}
        {visualPins.map((t) => (
          <div
            key={`vp-${t}`}
            className="absolute top-0 bottom-0"
            style={{ left: pct(t), transform: 'translateX(-50%)' }}
          >
            <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-[1px] bg-amber-400/80 pointer-events-none" />
            <div
              onClick={(e) => { e.stopPropagation(); removeVisualPin(t) }}
              className="absolute top-0.5 left-1/2 -translate-x-1/2 w-2 h-2 bg-amber-400 rounded-full cursor-pointer hover:bg-rose-400 hover:scale-125 transition-all z-10"
              title={`marker ${t.toFixed(2)}s — click to remove`}
            />
          </div>
        ))}
        {/* Voice block positioned at voiceEntry, width = voiceDur.
            Click to focus, arrow keys ±0.1s / ±1s. This is the one
            that drives the persisted vocal_entry_seconds. The voice
            waveform canvas sits INSIDE the block so dragging the
            block also drags the waveform — when you move the start
            to 10s, the voice audio actually begins at 10s and the
            soundwave visually begins there too. */}
        <div
          tabIndex={0}
          onPointerDown={(e) => startDrag('voice', e)}
          onKeyDown={onVoiceKey}
          className="absolute top-0 bottom-0 bg-emerald-500/25 border border-emerald-400 rounded-sm cursor-ew-resize touch-none focus:outline-none focus:ring-2 focus:ring-emerald-300"
          style={{ left: voiceLeftPct, width: voiceWidthPct }}
          title={`voice ${voiceEntry.toFixed(3)}s → ${Math.min(instrDur, voiceEntry + voiceDur).toFixed(3)}s`}
        >
          <canvas
            ref={voiceCanvasRef}
            className="absolute inset-0 w-full h-full pointer-events-none"
          />
          <div className="absolute top-0 left-0 w-0.5 h-full bg-emerald-300" />
          <div className="absolute top-0 left-0 w-2 h-2 bg-emerald-300 rounded-sm" />
          <div className="absolute bottom-0 left-1 text-[9px] text-emerald-200 font-mono pointer-events-none">
            {voiceEntry.toFixed(2)}
          </div>
          {/* Orange scratch pin — nested inside the green block so it
              naturally follows the block when it's dragged, paints
              on top (later DOM child = higher paint order within the
              same stacking context), and its click/focus/key handlers
              are reachable even though the block also has a
              pointerdown handler — we stopPropagation in startDrag.
              Position is a voice-relative offset in [0, voiceDur],
              rendered as a percentage of the block's width. */}
          {orangePin !== null && (
            <div
              tabIndex={0}
              onPointerDown={(e) => startDrag('orangePin', e)}
              onKeyDown={onOrangePinKey}
              className="absolute -top-1 -bottom-1 cursor-ew-resize touch-none focus:outline-none group"
              style={{
                left: `${(Math.max(0, Math.min(voiceDur, orangePin)) / Math.max(0.001, voiceDur)) * 100}%`,
                transform: 'translateX(-50%)',
                width: '28px',
                zIndex: 40,
              }}
              title={`scratch pin +${orangePin.toFixed(3)}s from voice entry (click to focus, ←→ ±0.1s, ↑↓ ±1s, Del to remove)`}
            >
              <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-[2px] bg-orange-400 group-focus:bg-orange-300 group-focus:w-[3px] transition-all shadow-[0_0_6px_rgba(251,146,60,0.9)]" />
              <div className="absolute top-0 left-1/2 -translate-x-1/2 w-4 h-4 bg-orange-400 rounded-sm border-2 border-orange-50 group-focus:bg-orange-300 group-focus:scale-125 group-focus:ring-2 group-focus:ring-orange-300/60 transition-all shadow-lg" />
              <div className="absolute bottom-0 left-1/2 -translate-x-1/2 text-[9px] text-orange-100 font-mono whitespace-nowrap pointer-events-none bg-zinc-950/90 px-1 rounded">
                +{orangePin.toFixed(2)}
              </div>
            </div>
          )}
        </div>
        {/* Voice playhead — same visual as the instrumental one. The
            position is in the shared instrumental time axis (so when
            voice is playing, the bar slides through the green block). */}
        <div
          ref={voicePlayheadRef}
          className="absolute top-0 bottom-0 pointer-events-none"
          style={{ left: '0%', display: 'none', transform: 'translateX(-50%)' }}
        >
          <div className="absolute top-0 bottom-0 left-1/2 -translate-x-1/2 w-[2px] bg-yellow-300 shadow-[0_0_6px_rgba(253,224,71,0.7)]" />
          <div
            ref={voicePlayheadLabelRef}
            className="absolute -top-3 left-1/2 -translate-x-1/2 text-[9px] text-yellow-300 font-mono whitespace-nowrap"
          >
            0.00s
          </div>
        </div>
      </div>
      </div>

      {/* Playback + save controls. Per-lane play buttons are above;
          down here we only need "together" (which needs both tracks
          synced) and a global stop. */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={toggleTogether}
          disabled={!instrUrl || !voiceUrl || busy}
          className={`px-2 py-1 rounded border flex items-center gap-1 disabled:opacity-40 ${
            playing === 'together'
              ? 'bg-violet-500/30 border-violet-400 text-violet-100'
              : 'border-violet-500/60 bg-violet-500/10 hover:bg-violet-500/25 text-violet-100'
          }`}
          title="Play instrumental region + voice aligned at the current entry point"
        >
          {playing === 'together' ? <Pause size={10} /> : <Play size={10} />}
          together
        </button>
        <button
          onClick={stopAll}
          disabled={playing === 'none'}
          className="px-2 py-1 rounded border border-zinc-700 hover:border-zinc-500 text-zinc-400 flex items-center gap-1 disabled:opacity-40"
          title="Stop all playback"
        >
          <Square size={10} /> stop
        </button>
        <button
          onClick={toggleOrangePin}
          className={`px-2 py-1 rounded border flex items-center gap-1 transition-colors ${
            orangePin !== null
              ? 'bg-orange-500/20 border-orange-400 text-orange-200 hover:bg-orange-500/30'
              : 'border-zinc-700 hover:border-orange-500 text-zinc-300'
          }`}
          title={
            orangePin !== null
              ? 'Remove the orange scratch pin'
              : 'Add an orange scratch pin at the current voice entry'
          }
        >
          {orangePin !== null ? '− orange pin' : '+ orange pin'}
        </button>
        <button
          onClick={save}
          disabled={!dirty || busy}
          className={`ml-auto px-2 py-1 rounded border flex items-center gap-1 ${
            dirty && !busy
              ? 'bg-violet-500/20 border-violet-500 text-violet-200 hover:bg-violet-500/30'
              : 'border-zinc-800 text-zinc-600 cursor-not-allowed'
          }`}
        >
          {nudge.isPending ? <Loader2 size={10} className="animate-spin" /> : <Save size={10} />}
          Save &amp; Remix
        </button>
      </div>
      <div className="mt-1.5 text-[9px] text-zinc-500 leading-relaxed">
        Drag the violet instrumental pins to scope an audition region. Click the green
        voice block to focus it, then drag or use arrow keys (±0.1s / ±1s) to set
        the vocal entry point. Double-click either lane to drop an amber marker pin
        (click the dot to remove — markers persist per instrumental). Use "+ orange
        pin" to drop a session-only scratch pin on the voice lane — drag it or focus
        it (click) and nudge with ←→ ±0.1s / ↑↓ ±1s / Del to remove. Yellow playhead
        shows the current playback position. Save &amp; Remix re-mixes in ~10 s using
        the cached vocals stem — the value is persisted on the instrumental so every
        song using this beat inherits the correction.
      </div>

      <audio
        ref={instrRef}
        src={instrUrl || undefined}
        preload="auto"
        onEnded={() => { if (playing === 'instr') setPlaying('none') }}
      />
      <audio
        ref={voiceRef}
        src={voiceUrl || undefined}
        preload="auto"
        onEnded={() => { if (playing === 'voice') setPlaying('none') }}
      />
    </div>
  )
}


function SongDetailPanel({ songId, onQaPassed }) {
  const { data, isLoading } = useSong(songId)
  const song = data?.data

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-zinc-500 text-xs py-4">
        <Loader2 size={14} className="animate-spin" /> Loading song detail...
      </div>
    )
  }
  if (!song) return null

  const master = song.audio_assets?.find(a => a.is_master_candidate) || song.audio_assets?.[0]
  const coverUrl = song.primary_artwork_asset_id
    ? resolveAudioUrl(`/api/v1/admin/visual/${song.primary_artwork_asset_id}.png`)
    : null

  return (
    <div className="space-y-4 bg-zinc-950/40 p-4 border-t border-zinc-800">
      {/* Cover art */}
      {coverUrl && (
        <div className="flex justify-center">
          <img
            src={coverUrl}
            alt={song.title}
            className="w-64 h-64 rounded-lg object-cover border border-zinc-700 shadow-lg"
          />
        </div>
      )}
      {/* Audio player with stem toggle */}
      {master && master.storage_url && (
        <StemAwareAudioPlayer song={song} masterUrl={master.storage_url} masterMeta={master} />
      )}
      {(!master || !master.storage_url) && song.status !== 'draft' && (
        <div className="flex items-start gap-2 bg-amber-500/10 border border-amber-500/30 rounded p-2.5 text-[11px] text-amber-300">
          <AlertCircle size={14} className="flex-shrink-0 mt-0.5" />
          No playable audio asset — the generation may still be in flight or the bytes expired before self-hosting.
        </div>
      )}

      {/* Grid of key metadata */}
      <div className="grid grid-cols-4 gap-2 text-[10px]">
        <MetaBox label="Tempo"    value={song.tempo_bpm ? `${song.tempo_bpm} BPM` : '—'} />
        <MetaBox label="Key"      value={song.key_camelot || '—'} />
        <MetaBox label="Duration" value={song.duration_seconds ? `${song.duration_seconds}s` : '—'} />
        <MetaBox label="Language" value={song.language || 'en'} />
        <MetaBox label="Provider" value={song.generation_provider || '—'} />
        <MetaBox label="Cost"     value={song.generation_cost_usd ? `$${song.generation_cost_usd.toFixed(3)}` : '—'} />
        <MetaBox label="ISRC"     value={song.isrc || '—'} />
        <MetaBox label="Release"  value={song.release_title || (song.release_id ? song.release_id.slice(0, 8) : '—')} />
      </div>

      {/* Prompt */}
      {song.generation_prompt && (
        <div className="space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-zinc-500">Generation Prompt</div>
          <pre className="bg-zinc-950 border border-zinc-800 rounded p-3 text-[10px] text-zinc-300 whitespace-pre-wrap max-h-48 overflow-y-auto font-mono leading-relaxed">
            {song.generation_prompt}
          </pre>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2 border-t border-zinc-800">
        {(song.status === 'draft' || song.status === 'qa_pending') && (
          <button
            onClick={() => onQaPassed(song.song_id)}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium rounded-lg transition-colors"
          >
            <CheckCircle2 size={12} /> Mark QA passed (bypass)
          </button>
        )}
        {song.audio_assets?.length > 1 && (
          <span className="text-[10px] text-zinc-500">
            {song.audio_assets.length} audio assets
          </span>
        )}
      </div>
    </div>
  )
}

function MetaBox({ label, value }) {
  return (
    <div className="bg-zinc-950 border border-zinc-800 rounded px-2 py-1.5">
      <div className="text-zinc-200 font-semibold tabular-nums truncate">{value}</div>
      <div className="text-zinc-600 text-[9px] uppercase tracking-wider">{label}</div>
    </div>
  )
}

function SongRow({ song, expanded, onToggle, onQaPassed }) {
  const coverUrl = song.primary_artwork_asset_id
    ? resolveAudioUrl(`/api/v1/admin/visual/${song.primary_artwork_asset_id}.png`)
    : null
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-3 hover:bg-zinc-900/60 transition-colors text-left"
      >
        {coverUrl ? (
          <img src={coverUrl} alt="" className="w-10 h-10 rounded object-cover border border-zinc-700 flex-shrink-0" />
        ) : (
          <FileAudio size={14} className="text-zinc-600 flex-shrink-0" />
        )}
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-zinc-100 truncate">{song.title}</div>
          <div className="text-[10px] text-zinc-500 truncate">
            {song.primary_genre} · {song.song_id.slice(0, 8)}
          </div>
        </div>
        <StatusPill status={song.status} />
        <div className="text-[10px] text-zinc-600 tabular-nums w-20 text-right flex-shrink-0">
          {song.created_at ? new Date(song.created_at).toLocaleDateString() : ''}
        </div>
        {expanded ? <ChevronUp size={14} className="text-zinc-500" /> : <ChevronDown size={14} className="text-zinc-500" />}
      </button>
      {expanded && <SongDetailPanel songId={song.song_id} onQaPassed={onQaPassed} />}
    </div>
  )
}

export default function Songs() {
  const [statusFilter, setStatusFilter] = useState(null)
  const [expandedId, setExpandedId] = useState(null)
  const { data, isLoading, isError, error } = useSongs({ status: statusFilter })
  const markQa = useMarkQaPassed()
  const qc = useQueryClient()

  const songs = data?.data?.songs || []

  const handleQaPass = async (songId) => {
    await markQa.mutateAsync({ songId })
    qc.invalidateQueries({ queryKey: ['admin', 'songs'] })
  }

  const statusCounts = songs.reduce((acc, s) => {
    acc[s.status] = (acc[s.status] || 0) + 1
    return acc
  }, {})

  const filters = [
    { id: null,                   label: 'All' },
    { id: 'draft',                label: 'Draft' },
    { id: 'qa_pending',           label: 'QA Pending' },
    { id: 'qa_passed',            label: 'QA Passed' },
    { id: 'assigned_to_release',  label: 'Assigned' },
    { id: 'live',                 label: 'Live' },
  ]

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Disc3 size={24} className="text-violet-400" />
            <h1 className="text-2xl font-bold text-zinc-100">Songs</h1>
          </div>
          <p className="text-sm text-zinc-500">
            Every song the system has produced. Click a row to play it and see its generation provenance.
          </p>
        </div>
      </div>

      {/* Filter bar */}
      <div className="flex gap-1 bg-zinc-900 border border-zinc-800 rounded-lg p-1 mb-4 w-fit">
        {filters.map(f => (
          <button
            key={f.id || 'all'}
            onClick={() => setStatusFilter(f.id)}
            className={`px-3 py-1 text-xs rounded font-medium transition-colors ${
              statusFilter === f.id
                ? 'bg-violet-600/30 text-violet-200 border border-violet-500/50'
                : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {f.label}
            {f.id && statusCounts[f.id] ? (
              <span className="ml-1.5 text-[10px] text-zinc-600">({statusCounts[f.id]})</span>
            ) : null}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-20 text-zinc-500 gap-2">
          <Loader2 size={18} className="animate-spin" /> Loading songs...
        </div>
      )}

      {isError && (
        <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 text-rose-300 text-sm">
          Failed to load songs: {error?.message}
        </div>
      )}

      {!isLoading && songs.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Music2 size={40} className="text-zinc-700 mb-3" />
          <div className="text-sm text-zinc-400 mb-1">No songs yet</div>
          <div className="text-xs text-zinc-600 max-w-sm">
            Use Song Lab to generate a song, or POST /admin/blueprints/{`{id}`}/generate-song directly against an approved blueprint.
          </div>
        </div>
      )}

      <div className="space-y-2">
        {songs.map(song => (
          <SongRow
            key={song.song_id}
            song={song}
            expanded={expandedId === song.song_id}
            onToggle={() => setExpandedId(expandedId === song.song_id ? null : song.song_id)}
            onQaPassed={handleQaPass}
          />
        ))}
      </div>

      {songs.length > 0 && (
        <div className="mt-6 flex items-center gap-3 text-[10px] text-zinc-600">
          <Clock size={10} /> Auto-refreshes every 15 seconds
        </div>
      )}
    </div>
  )
}
