import { createContext, useCallback, useContext, useEffect, useState } from 'react'

/**
 * Global visibility state for the right-side Assistant panel.
 *
 * Persisted to localStorage so the user's preference survives reloads
 * and page navigations. Keyboard shortcut Cmd/Ctrl + "." toggles it.
 *
 * PRD §21.1 spec — default is "visible" so the new UX is opt-in to
 * hiding, not opt-out.
 */

const STORAGE_KEY = 'soundpulse.assistant.visible'

const AssistantVisibilityContext = createContext({
  visible: true,
  show: () => {},
  hide: () => {},
  toggle: () => {},
})

function readInitial() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw === null) return true
    return raw === 'true'
  } catch {
    return true
  }
}

export function AssistantVisibilityProvider({ children }) {
  const [visible, setVisible] = useState(readInitial)

  const persist = useCallback((v) => {
    setVisible(v)
    try {
      localStorage.setItem(STORAGE_KEY, v ? 'true' : 'false')
    } catch {
      // localStorage may be unavailable in some iframes / privacy modes — ignore
    }
  }, [])

  const show = useCallback(() => persist(true), [persist])
  const hide = useCallback(() => persist(false), [persist])
  const toggle = useCallback(() => persist(!visible), [persist, visible])

  // Keyboard shortcut: Cmd/Ctrl + "." toggles the panel
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === '.') {
        e.preventDefault()
        toggle()
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [toggle])

  return (
    <AssistantVisibilityContext.Provider value={{ visible, show, hide, toggle }}>
      {children}
    </AssistantVisibilityContext.Provider>
  )
}

export function useAssistantVisibility() {
  return useContext(AssistantVisibilityContext)
}
