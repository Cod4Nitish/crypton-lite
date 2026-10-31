// Dictation wrapper: same browser engine as before, but failures are surfaced instead of silent.
// Chrome/Edge speech recognition is a cloud service, so it needs internet. Typing always works.
import { WebSpeechDictationAdapter, type DictationAdapter } from "@assistant-ui/react"
import { toast } from "sonner"

const inner = new WebSpeechDictationAdapter()
const ENDED: DictationAdapter.Session = {
  status: { type: "ended", reason: "error" },
  stop: async () => {}, cancel: () => {},
  onSpeechStart: () => () => {}, onSpeechEnd: () => () => {}, onSpeech: () => () => {},
}
const TYPE_INSTEAD = "Type your command instead, the text box works offline."

export const voice: DictationAdapter = {
  listen() {
    if (!navigator.onLine) toast.warning(`You appear to be offline. Browser voice needs internet. ${TYPE_INSTEAD}`)
    let session: DictationAdapter.Session
    try {
      session = inner.listen()
    } catch {
      toast.error(`Voice input is not supported in this browser. ${TYPE_INSTEAD}`)
      return ENDED
    }
    let heard = false
    session.onSpeech((r) => { if (r.transcript.trim()) heard = true })
    const poll = setInterval(() => {
      const st = session.status
      if (st.type !== "ended") return
      clearInterval(poll)
      if (st.reason === "error") toast.error(`Voice transcription failed (no internet or microphone blocked). ${TYPE_INSTEAD}`)
      else if (!heard) toast("No speech detected. Try again or type.")
    }, 300)
    return session
  },
}
