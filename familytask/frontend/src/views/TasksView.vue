<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { apiFetch } from '../api'

const tasks = ref([])
const currentMember = ref(null)
const familyMembers = ref([])
const selectedMemberId = ref('')
const newTask = ref('')
const newTaskDeadline = ref('')
const now = ref(Date.now())
const taskToDelete = ref(null)
const dismissedWarningTaskId = ref(null)
const showWelcomeGif = ref(true)
const isWelcomeGifFading = ref(false)
const errorMessage = ref('')
let clockTimer

async function fetchCurrentMember() {
  const response = await apiFetch('/api/me')
  if (response.ok) currentMember.value = await response.json()
}

async function fetchTasks() {
  const response = await apiFetch('/api/tasks')
  if (!response.ok) throw new Error('Impossible de charger les tâches depuis l’API.')
  tasks.value = await response.json()
}

async function fetchFamilyMembers() {
  const response = await apiFetch('/api/members')
  if (!response.ok) throw new Error('Impossible de charger les membres de la famille.')
  familyMembers.value = await response.json()
}

// Efface toujours la session locale, même si l'API est inaccessible.
async function logout() {
  try {
    await apiFetch('/api/logout', { method: 'POST' })
  } catch (error) {
    console.warn('Serveur inaccessible, déconnexion locale appliquée.', error)
  } finally {
    localStorage.removeItem('token')
    window.location.href = '/login'
  }
}

onMounted(async () => {
  try {
    await Promise.all([fetchCurrentMember(), fetchTasks()])
    if (currentMember.value?.is_admin) await fetchFamilyMembers()
  } catch (error) {
    errorMessage.value = error.message
  }

  window.setTimeout(() => {
    isWelcomeGifFading.value = true
    window.setTimeout(() => { showWelcomeGif.value = false }, 700)
  }, 2000)
  clockTimer = window.setInterval(() => { now.value = Date.now() }, 30000)
})

onUnmounted(() => window.clearInterval(clockTimer))

// Convertit une échéance HH:MM en date du jour pour l'avertissement.
function getDeadlineDate(task) {
  if (!task.deadline) return null
  const deadline = new Date()
  const [hours, minutes] = task.deadline.split(':').map(Number)
  deadline.setHours(hours, minutes, 0, 0)
  return deadline
}

const warningTask = computed(() => tasks.value.find((task) => {
  if (task.done || !task.deadline || task.id === dismissedWarningTaskId.value) return false
  const remaining = getDeadlineDate(task).getTime() - now.value
  return remaining > 0 && remaining <= 60 * 60 * 1000
}))

const otherMembers = computed(() => familyMembers.value.filter((member) => member.id !== currentMember.value?.id))

function dismissWarning() {
  if (warningTask.value) dismissedWarningTaskId.value = warningTask.value.id
}

async function addTask() {
  const title = newTask.value.trim()
  if (!title) return
  const deadline = newTaskDeadline.value
  const deadlineQuery = deadline ? `&deadline=${encodeURIComponent(deadline)}` : ''
  const assigneeQuery = selectedMemberId.value ? `&member_id=${selectedMemberId.value}` : ''
  const response = await apiFetch(`/api/tasks?title=${encodeURIComponent(title)}${deadlineQuery}${assigneeQuery}`, {
    method: 'POST',
  })
  if (!response.ok) throw new Error('Impossible d’ajouter la tâche.')
  newTask.value = ''
  newTaskDeadline.value = ''
  selectedMemberId.value = ''
  await fetchTasks()
}

async function toggleTaskDone(taskId) {
  const response = await apiFetch(`/api/tasks/${taskId}`, { method: 'PATCH' })
  if (!response.ok) throw new Error('Impossible de cocher la tâche.')
  await fetchTasks()
}

function requestDelete(taskId) {
  taskToDelete.value = tasks.value.find((task) => task.id === taskId) || null
}

async function confirmDelete() {
  if (!taskToDelete.value) return
  const response = await apiFetch(`/api/tasks/${taskToDelete.value.id}`, { method: 'DELETE' })
  if (!response.ok) throw new Error('Impossible de supprimer la tâche.')
  taskToDelete.value = null
  await fetchTasks()
}

function cancelDelete() {
  taskToDelete.value = null
}
</script>

<template>
  <header class="topbar">
    <details class="section-menu">
      <summary>☰ Menu</summary>
      <nav aria-label="Sections de l'application"><RouterLink to="/tasks">Tâches</RouterLink><RouterLink to="/assistant">Assistant IA</RouterLink><RouterLink v-if="currentMember?.is_admin" to="/family">Famille</RouterLink></nav>
    </details>
    <div class="brand-lockup"><span class="brand-mark">✦</span><div><p class="eyebrow">FAMILY HQ / DAILY OPS</p><h1>FamilyTask</h1></div></div>
    <div class="topbar-actions"><span v-if="currentMember" class="member-greeting">Bonjour {{ currentMember.name }}</span><button type="button" class="logout-button" @click="logout">Se déconnecter</button></div>
  </header>

  <main class="page-shell">
    <section class="hero-copy"><p class="kicker">MISSION BOARD</p><h2>Get it done.</h2><p class="subtitle">Les petites missions de la famille, au même endroit.</p></section>
    <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
    <section class="card task-board">
      <div class="board-heading"><div><p class="section-label">ACTIVE TASKS</p><h3>Today's lineup</h3></div><span class="task-count">{{ tasks.length }} TASKS</span></div>
      <form class="task-form" @submit.prevent="addTask">
        <input v-model="newTask" type="text" placeholder="Nouvelle tâche" />
        <label class="deadline-field"><span>Limite</span><input v-model="newTaskDeadline" type="time" aria-label="Heure limite facultative" /></label>
        <label v-if="currentMember?.is_admin" class="assignee-field"><span>Pour qui ?</span><select v-model="selectedMemberId"><option value="">Moi</option><option v-for="member in otherMembers" :key="member.id" :value="member.id">{{ member.name }}</option></select></label>
        <button type="submit">Ajouter</button>
      </form>
      <ul class="task-list">
        <li v-for="task in tasks" :key="task.id" class="task-row">
          <div><span class="task-title" :class="{ done: task.done }" role="button" tabindex="0" :aria-label="`Marquer ${task.title} comme terminée`" @click="toggleTaskDone(task.id)" @keydown.enter="toggleTaskDone(task.id)" @keydown.space.prevent="toggleTaskDone(task.id)">{{ task.title }}</span><small v-if="task.deadline" class="task-deadline">pour {{ task.deadline }}</small></div>
          <button type="button" class="delete-button" :aria-label="`Supprimer ${task.title}`" :title="`Supprimer ${task.title}`" @click="requestDelete(task.id)">🗑️</button>
        </li>
      </ul>
    </section>

    <div v-if="warningTask" class="confirmation-overlay"><section class="confirmation-dialog deadline-dialog"><img class="warning-image" src="https://media1.tenor.com/m/4NGmv1oM-dUAAAAC/p5-p5r.gif" alt="Avertissement d’échéance" /><p class="confirmation-kicker">TIME IS RUNNING OUT</p><h2>À faire bientôt</h2><p class="confirmation-message">« <strong>{{ warningTask.title }}</strong> » doit être terminée avant {{ warningTask.deadline }}.</p><button type="button" class="confirm-button" @click="dismissWarning">J'ai compris</button></section></div>
    <div v-if="taskToDelete" class="confirmation-overlay" @click.self="cancelDelete"><section class="confirmation-dialog deadline-dialog"><img class="warning-image" src="https://media1.tenor.com/m/QmGhkPRqFMwAAAAC/persona-5-persona.gif" alt="Confirmation de suppression" /><p class="confirmation-kicker">ARE YOU SURE?</p><h2>Delete mission?</h2><p class="confirmation-message">Supprimer « <strong>{{ taskToDelete.title }}</strong> » de la liste ?</p><div class="confirmation-actions"><button type="button" class="cancel-button" @click="cancelDelete">Annuler</button><button type="button" class="confirm-button" @click="confirmDelete">Supprimer</button></div></section></div>
    <div v-if="showWelcomeGif" class="welcome-gif-overlay" :class="{ 'is-fading': isWelcomeGifFading }" aria-hidden="true"><img class="welcome-gif" src="https://media1.tenor.com/m/Vl-pwtuiQbgAAAAC/take-your-time-persona-five.gif" alt="" /></div>
  </main>
</template>