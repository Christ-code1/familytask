<script setup>
import { nextTick, ref } from 'vue'
import { apiFetch } from '../api'

const emit = defineEmits(['tasks-updated'])  // Prévient le parent (ex. la liste des tâches) qu'il doit se rafraîchir.

const messages = ref([])  // Historique de la conversation : { role: 'user' | 'assistant', text }.
const draft = ref('')  // Contenu du champ de saisie, tapé ou dicté.
const isSending = ref(false)
const chatLogEl = ref(null)

// Fait défiler la zone de messages vers le bas dès qu'un message est ajouté.
async function scrollToBottom() {
  await nextTick()
  if (chatLogEl.value) chatLogEl.value.scrollTop = chatLogEl.value.scrollHeight
}

async function sendMessage() {
  const text = draft.value.trim()
  if (!text || isSending.value) return

  messages.value.push({ role: 'user', text })
  draft.value = ''
  isSending.value = true
  scrollToBottom()

  try {
    const response = await apiFetch(`/api/assistant?message=${encodeURIComponent(text)}`, {
      method: 'POST',
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || "L'assistant est indisponible.")
    messages.value.push({ role: 'assistant', text: data.reply || "L'assistant n'a pas répondu." })
    emit('tasks-updated')  // Une tâche a peut-être été ajoutée : le parent peut recharger sa liste.
  } catch (error) {
    messages.value.push({ role: 'assistant', text: error.message || "L'assistant IA n'a pas pu répondre." })
  } finally {
    isSending.value = false
    scrollToBottom()
  }
}

// --- Dictée vocale : reconnaissance vocale du navigateur, en français. ---
const SpeechRecognitionApi = window.SpeechRecognition || window.webkitSpeechRecognition  // Chrome préfixe encore l'API.
const isVoiceSupported = !!SpeechRecognitionApi
const isListening = ref(false)
let recognition = null

function toggleVoiceInput() {
  if (!isVoiceSupported) return
  if (isListening.value) {
    recognition?.stop()  // Un second clic arrête l'écoute avant la fin naturelle.
    return
  }

  recognition = new SpeechRecognitionApi()
  recognition.lang = 'fr-FR'  // Reconnaissance en français, comme demandé.
  recognition.interimResults = true  // Affiche le texte au fur et à mesure de la dictée.
  recognition.continuous = false

  recognition.onresult = (event) => {
    draft.value = Array.from(event.results).map((result) => result[0].transcript).join('')
  }
  recognition.onerror = () => { isListening.value = false }
  recognition.onend = () => {
    isListening.value = false
    if (draft.value.trim()) sendMessage()  // Envoie automatiquement la phrase dictée, une fois terminée.
  }

  isListening.value = true
  recognition.start()
}
</script>

<template>
  <div class="chat-assistant">
    <div v-if="messages.length" ref="chatLogEl" class="chat-log" role="log" aria-live="polite">
      <p v-for="(entry, index) in messages" :key="index" class="chat-message" :class="entry.role">{{ entry.text }}</p>
      <p v-if="isSending" class="chat-message assistant is-typing" aria-hidden="true">…</p>
    </div>

    <form class="task-form chat-form" @submit.prevent="sendMessage">
      <input
        v-model="draft"
        type="text"
        placeholder="Ajoute la vaisselle pour Léa"
        aria-label="Message à l'assistant"
      />
      <button
        v-if="isVoiceSupported"
        type="button"
        class="mic-button"
        :class="{ 'is-listening': isListening }"
        :aria-label="isListening ? 'Arrêter la dictée' : 'Dicter le message'"
        :title="isListening ? 'Arrêter la dictée' : 'Dicter le message'"
        @click="toggleVoiceInput"
      >{{ isListening ? '🔴' : '🎤' }}</button>
      <button type="submit" :disabled="isSending">{{ isSending ? 'Envoi…' : 'Envoyer' }}</button>
    </form>
    <p v-if="!isVoiceSupported" class="voice-hint">🎤 La dictée vocale fonctionne sur Chrome et Edge.</p>
  </div>
</template>
