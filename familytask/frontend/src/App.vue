<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

// La liste des tâches est récupérée depuis l'API, puis rendue réactive côté interface.
const tasks = ref([])

// Contient le texte saisi dans le champ.
const newTask = ref('')
const newTaskDeadline = ref('')
const now = ref(Date.now())

// Contient la tâche en attente de confirmation.
const taskToDelete = ref(null)
const dismissedWarningTaskId = ref(null)

// Contrôle l'écran plein écran affiché à l'arrivée sur le site.
const showWelcomeGif = ref(true)
const isWelcomeGifFading = ref(false)
let clockTimer

// Charge la liste des tâches depuis l'API au démarrage.
async function fetchTasks() {
  const response = await fetch('/api/tasks')

  if (!response.ok) {
    throw new Error('Impossible de charger les tâches depuis l’API.')
  }

  tasks.value = await response.json()
}

// L'écran d'accueil commence à disparaître en fondu après deux secondes.
onMounted(async () => {
  try {
    await fetchTasks()
  } catch (error) {
    console.error(error)
  }

  window.setTimeout(() => {
    isWelcomeGifFading.value = true

    // Retire l'overlay après la fin de la transition CSS.
    window.setTimeout(() => {
      showWelcomeGif.value = false
    }, 700)
  }, 2000)

  clockTimer = window.setInterval(() => {
    now.value = Date.now()
  }, 30000)
})

onUnmounted(() => window.clearInterval(clockTimer))

// Renvoie l'échéance de la tâche sous forme de date du jour.
function getDeadlineDate(task) {
  if (!task.deadline) return null

  const deadline = new Date()
  const [hours, minutes] = task.deadline.split(':').map(Number)
  deadline.setHours(hours, minutes, 0, 0)
  return deadline
}

// La tâche la plus urgente qui arrive dans l'heure.
const warningTask = computed(() => tasks.value.find((task) => {
  if (task.done || !task.deadline || task.id === dismissedWarningTaskId.value) return false

  const remaining = getDeadlineDate(task).getTime() - now.value
  return remaining > 0 && remaining <= 60 * 60 * 1000
}))

// Ferme l'avertissement pour la tâche actuellement affichée.
function dismissWarning() {
  if (warningTask.value) dismissedWarningTaskId.value = warningTask.value.id
}

// Ajoute une nouvelle tâche via l'API puis recharge la liste.
async function addTask() {
  const title = newTask.value.trim()

  // On ignore l'ajout si le champ est vide.
  if (!title) return

  const deadline = newTaskDeadline.value
  const deadlineQuery = deadline ? `&deadline=${encodeURIComponent(deadline)}` : ''
  const response = await fetch(`/api/tasks?title=${encodeURIComponent(title)}${deadlineQuery}`, {
    method: 'POST'
  })

  if (!response.ok) {
    throw new Error('Impossible d’ajouter la tâche.')
  }

  // On vide le champ après l'ajout.
  newTask.value = ''
  newTaskDeadline.value = ''
  await fetchTasks()
}

// Bascule le statut done d'une tâche côté API puis recharge la liste.
async function toggleTaskDone(taskId) {
  const response = await fetch(`/api/tasks/${taskId}`, {
    method: 'PATCH'
  })

  if (!response.ok) {
    throw new Error('Impossible de cocher la tâche.')
  }

  await fetchTasks()
}

// Ouvre la confirmation pour la tâche sélectionnée.
function requestDelete(taskId) {
  const task = tasks.value.find((task) => task.id === taskId)
  if (task) taskToDelete.value = task
}

// Supprime la tâche après la confirmation dans la modale, puis recharge la liste.
async function confirmDelete() {
  if (!taskToDelete.value) return

  const response = await fetch(`/api/tasks/${taskToDelete.value.id}`, {
    method: 'DELETE'
  })

  if (!response.ok) {
    throw new Error('Impossible de supprimer la tâche.')
  }

  taskToDelete.value = null
  await fetchTasks()
}

// Ferme la modale sans supprimer la tâche.
function cancelDelete() {
  taskToDelete.value = null
}
</script>

<template>
  <header class="topbar">
    <div class="brand-lockup">
      <span class="brand-mark">✦</span>
      <div>
        <p class="eyebrow">FAMILY HQ / DAILY OPS</p>
        <h1>FamilyTask</h1>
      </div>
    </div>
    <span class="header-stamp">01 / TODO</span>
  </header>

  <main class="page-shell">
    <section class="hero-copy">
      <p class="kicker">MISSION BOARD</p>
      <h2>Get it done.</h2>
      <p class="subtitle">Les petites missions de la famille, au même endroit.</p>
    </section>

    <div class="task-layout">
      <section class="card task-board">
      <div class="board-heading">
        <div>
          <p class="section-label">ACTIVE TASKS</p>
          <h3>Today's lineup</h3>
        </div>
        <span class="task-count">{{ tasks.length }} TASKS</span>
      </div>

      <form class="task-form" @submit.prevent="addTask">
        <input v-model="newTask" type="text" placeholder="Nouvelle tâche" />
        <label class="deadline-field">
          <span>Limite</span>
          <input v-model="newTaskDeadline" type="time" aria-label="Heure limite facultative" />
        </label>
        <button type="submit">Ajouter</button>
      </form>

      <ul class="task-list">
        <li v-for="task in tasks" :key="task.id" class="task-row">
          <div>
            <span
              class="task-title"
              :class="{ done: task.done }"
              role="button"
              tabindex="0"
              :aria-label="`Marquer ${task.title} comme terminée`"
              @click="toggleTaskDone(task.id)"
              @keydown.enter="toggleTaskDone(task.id)"
              @keydown.space.prevent="toggleTaskDone(task.id)"
            >{{ task.title }}</span>
            <small v-if="task.deadline" class="task-deadline">pour {{ task.deadline }}</small>
          </div>
          <button
            type="button"
            class="delete-button"
            :aria-label="`Supprimer ${task.title}`"
            :title="`Supprimer ${task.title}`"
            @click="requestDelete(task.id)"
          >
            🗑️
          </button>
        </li>
      </ul>
      </section>

    </div>

    <div v-if="warningTask" class="confirmation-overlay" role="presentation">
      <section class="confirmation-dialog deadline-dialog" role="alertdialog" aria-modal="true" aria-labelledby="deadline-title">
        <img
          class="warning-image"
          src="https://media1.tenor.com/m/4NGmv1oM-dUAAAAC/p5-p5r.gif"
          alt="Animation Persona 5 Royal pour l'avertissement d'échéance"
        />
        <p class="confirmation-kicker">TIME IS RUNNING OUT</p>
        <h2 id="deadline-title">À faire bientôt</h2>
        <p class="confirmation-message">
          « <strong>{{ warningTask.title }}</strong> » doit être terminée avant {{ warningTask.deadline }}.
        </p>
        <div class="confirmation-actions">
          <button type="button" class="confirm-button" @click="dismissWarning">J'ai compris</button>
        </div>
      </section>
    </div>

    <div
      v-if="taskToDelete"
      class="confirmation-overlay"
      role="presentation"
      @click.self="cancelDelete"
    >
      <section
        class="confirmation-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirmation-title"
      >
        <img
          class="confirmation-gif"
          src="https://media1.tenor.com/m/QmGhkPRqFMwAAAAC/persona-5-persona.gif"
          alt="Animation de Morgana demandant une confirmation"
          loading="lazy"
        />
        <div class="confirmation-mark">!</div>
        <p class="confirmation-kicker">ARE YOU SURE?</p>
        <h2 id="confirmation-title">Delete mission?</h2>
        <p class="confirmation-message">
          Supprimer « <strong>{{ taskToDelete.title }}</strong> » de la liste ?
        </p>
        <div class="confirmation-actions">
          <button type="button" class="cancel-button" @click="cancelDelete">Annuler</button>
          <button type="button" class="confirm-button" @click="confirmDelete">Supprimer</button>
        </div>
      </section>
    </div>

    <div
      v-if="showWelcomeGif"
      class="welcome-gif-overlay"
      :class="{ 'is-fading': isWelcomeGifFading }"
      aria-hidden="true"
    >
      <img
        class="welcome-gif"
        src="https://media1.tenor.com/m/Vl-pwtuiQbgAAAAC/take-your-time-persona-five.gif"
        alt=""
      />
    </div>
  </main>
</template>




