<script setup>
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { apiFetch } from '../api'

const message = ref('')
const reply = ref('')
const errorMessage = ref('')
const loading = ref(false)

async function askAssistant() {
  const text = message.value.trim()
  if (!text || loading.value) return

  loading.value = true
  reply.value = ''
  errorMessage.value = ''
  try {
    const response = await apiFetch(`/api/assistant?message=${encodeURIComponent(text)}`, {
      method: 'POST',
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || "L'assistant est indisponible.")
    reply.value = data.reply || "L'assistant n'a pas répondu."
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <header class="topbar">
    <div class="brand-lockup"><span class="brand-mark">✦</span><div><p class="eyebrow">FAMILY HQ / ASSISTANT</p><h1>FamilyTask</h1></div></div>
    <nav class="topbar-actions" aria-label="Navigation principale">
      <RouterLink to="/tasks">Tâches</RouterLink>
      <RouterLink to="/family">Famille</RouterLink>
    </nav>
  </header>

  <main class="page-shell">
    <section class="hero-copy"><p class="kicker">FAMILY ASSISTANT</p><h2>Une tâche en langage naturel.</h2><p class="subtitle">Demande à l’assistant d’ajouter une tâche pour un membre de ta famille.</p></section>
    <section class="card task-board">
      <form class="task-form" @submit.prevent="askAssistant">
        <input v-model="message" type="text" placeholder="Ajoute la vaisselle pour Léa" aria-label="Message à l'assistant" />
        <button type="submit" :disabled="loading">{{ loading ? 'Réponse…' : 'Envoyer' }}</button>
      </form>
      <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
      <p v-if="reply" class="confirmation-message" role="status">{{ reply }}</p>
    </section>
  </main>
</template>
