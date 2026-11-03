import { useState, useEffect, useRef, useCallback } from 'react'

const PREFERRED = ['Premium', 'Enhanced', 'Natural', 'Neural', 'Siri', 'Tingting', 'Meijia', 'Samantha']

function pickVoice(voices, speechLang) {
  const prefix = speechLang.slice(0, 2)
  const candidates = voices.filter(v => v.lang.replace('_', '-').startsWith(prefix))
  for (const p of PREFERRED) {
    const v = candidates.find(c => c.name.includes(p))
    if (v) return v
  }
  return candidates.find(c => c.lang.replace('_', '-') === speechLang) || candidates[0] || null
}

/**
 * useSpeech — browser text-to-speech in the selected answer language.
 *
 * Only one utterance plays at a time; `speak` interrupts whatever is playing.
 * Escape stops speech anywhere on the page.
 *
 * @param {string} speechLang  BCP-47 tag, e.g. 'zh-CN' or 'en-US'
 * @returns {{ speak: (text: string, id?: string) => void, stop: () => void, speakingId: string|null }}
 */
export function useSpeech(speechLang) {
  const [speakingId, setSpeakingId] = useState(null)
  const voicesRef = useRef([])

  useEffect(() => {
    const load = () => { voicesRef.current = speechSynthesis.getVoices() }
    load()
    speechSynthesis.addEventListener('voiceschanged', load)
    return () => {
      speechSynthesis.removeEventListener('voiceschanged', load)
      speechSynthesis.cancel()
    }
  }, [])

  const stop = useCallback(() => {
    speechSynthesis.cancel()
    setSpeakingId(null)
  }, [])

  const speak = useCallback((text, id = 'default') => {
    speechSynthesis.cancel()
    const utt = new SpeechSynthesisUtterance(text)
    utt.lang = speechLang
    const voice = pickVoice(voicesRef.current, speechLang)
    if (voice) utt.voice = voice
    utt.rate = 1.0
    utt.onend = () => setSpeakingId(cur => (cur === id ? null : cur))
    setSpeakingId(id)
    speechSynthesis.speak(utt)
  }, [speechLang])

  useEffect(() => {
    function onKeyDown(e) {
      if (e.key === 'Escape') stop()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [stop])

  return { speak, stop, speakingId }
}
