<script setup>
import { RouterLink } from 'vue-router'
import ChatAssistant from '../components/ChatAssistant.vue'
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
    <section class="hero-copy"><p class="kicker">FAMILY ASSISTANT</p><h2>Une tâche en langage naturel.</h2><p class="subtitle">Écris ou dicte 🎤 une phrase, l’assistant ajoute la tâche pour le bon membre de la famille.</p></section>
    <section class="card task-board">
      <ChatAssistant />
    </section>
  </main>
</template>
