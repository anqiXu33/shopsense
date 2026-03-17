import { useState, useRef, useCallback, useEffect } from 'react'

/** Returns the platform-appropriate shortcut label, e.g. "⌥V" on Mac, "Alt+V" elsewhere */
export function voiceShortcutLabel() {
  return /Mac|iPhone|iPad|iPod/.test(navigator.platform ?? navigator.userAgent)
    ? '⌥V'
    : 'Alt+V'
}

/**
 * useVoiceInput — Web Speech API speech-to-text hook
 *
 * @param {object} opts
 * @param {string}   opts.lang        BCP-47 language tag (default: browser UI language)
 * @param {function} opts.onResult    Called with final transcript string
 * @param {function} opts.onStart     Called when mic opens
 * @param {function} opts.onEnd       Called when mic closes (after result or error)
 * @param {boolean}  opts.globalShortcut  If true, registers a global Alt/Option+V listener
 * @returns {{ listening: boolean, start: function, stop: function, supported: boolean }}
 */
export function useVoiceInput({ lang, onResult, onStart, onEnd, globalShortcut = false } = {}) {
  const [listening, setListening] = useState(false)
  const recRef = useRef(null)

  const supported =
    typeof window !== 'undefined' &&
    !!(window.SpeechRecognition || window.webkitSpeechRecognition)

  const stop = useCallback(() => {
    recRef.current?.stop()
  }, [])

  const start = useCallback(() => {
    if (!supported) return

    // Toggle off if already listening
    if (recRef.current) {
      recRef.current.stop()
      return
    }

    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const rec = new SR()
    if (lang) rec.lang = lang
    rec.interimResults = false
    rec.maxAlternatives = 1
    recRef.current = rec

    rec.onstart = () => {
      setListening(true)
      onStart?.()
    }

    rec.onresult = e => {
      const transcript = e.results[0][0].transcript.trim()
      onResult?.(transcript)
    }

    rec.onend = () => {
      setListening(false)
      recRef.current = null
      onEnd?.()
    }

    rec.onerror = e => {
      setListening(false)
      recRef.current = null
      if (e.error !== 'aborted') onEnd?.()
    }

    rec.start()
  }, [supported, lang, onResult, onStart, onEnd])

  // Global Alt/Option+V shortcut — use e.code so it works regardless of
  // what character the key combo produces (e.g. Mac Option+V → '√')
  useEffect(() => {
    if (!globalShortcut || !supported) return
    function onKeyDown(e) {
      if (e.altKey && e.code === 'KeyV') {
        e.preventDefault()
        start()
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [globalShortcut, supported, start])

  return { listening, start, stop, supported }
}
