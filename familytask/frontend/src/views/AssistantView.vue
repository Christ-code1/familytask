<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { apiFetch } from '../api'
import ChatAssistant from '../components/ChatAssistant.vue'
import MemberAvatar from '../components/MemberAvatar.vue'

const currentMember = ref(null)

// Nécessaire pour savoir si le lien « Famille » doit apparaître dans le menu, comme sur les autres pages.
async function fetchCurrentMember() {
  const response = await apiFetch('/api/me')
  if (response.ok) currentMember.value = await response.json()
}

onMounted(fetchCurrentMember)
</script>

<template>
  <header class="topbar">
    <details class="section-menu">
      <summary>☰ Menu</summary>
      <nav aria-label="Sections de l'application"><RouterLink to="/tasks">Tâches</RouterLink><RouterLink to="/assistant">Assistant IA</RouterLink><RouterLink v-if="currentMember?.is_admin" to="/family">Famille</RouterLink></nav>
    </details>
    <div class="brand-lockup"><span class="brand-mark">✦</span><div><p class="eyebrow">FAMILY HQ / ASSISTANT</p><h1>FamilyTask</h1></div></div>
    <div class="topbar-actions"><span v-if="currentMember" class="member-greeting"><MemberAvatar :name="currentMember.name" size="small" />Bonjour {{ currentMember.name }}</span></div>
  </header>

  <main class="page-shell">
    <section class="hero-copy"><p class="kicker">FAMILY ASSISTANT</p><h2>Une tâche en langage naturel.</h2><p class="subtitle">Écris ou dicte 🎤 une phrase, l’assistant ajoute la tâche pour le bon membre de la famille.</p></section>
    <section class="card task-board">
      <ChatAssistant />
    </section>
  </main>
</template>
