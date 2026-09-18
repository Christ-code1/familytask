<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { apiFetch } from '../api'
import MemberAvatar from '../components/MemberAvatar.vue'

const router = useRouter()
const currentMember = ref(null)
const members = ref([])
const liens = ref([])
const familyTasks = ref([])
const errorMessage = ref('')
const successMessage = ref('')
const isSubmitting = ref(false)
const newLien = ref('')
const memberToDelete = ref(null)
const newMember = ref({ name: '', lien: '', email: '', password: '', is_admin: false })

const memberNames = computed(() => new Map(members.value.map((member) => [member.id, member.name])))

// Lit une erreur JSON quand l'API en renvoie une, sans masquer une erreur 500 texte.
async function readApiResponse(response) {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) return response.json()
  return { detail: `Le serveur a répondu avec une erreur (${response.status}).` }
}

async function loadFamily() {
  // La route Famille est réservée aux administrateurs, même si le menu est masqué.
  const meResponse = await apiFetch('/api/me')
  if (!meResponse.ok) throw new Error('Impossible de vérifier le compte connecté.')
  currentMember.value = await meResponse.json()
  if (!currentMember.value.is_admin) {
    await router.replace('/tasks')
    return
  }

  // Les tâches contiennent un member_id : on charge les membres pour afficher leur prénom.
  const [membersResponse, liensResponse, tasksResponse] = await Promise.all([
    apiFetch('/api/members'),
    apiFetch('/api/liens'),
    apiFetch('/api/tasks/famille'),
  ])
  if (!membersResponse.ok || !liensResponse.ok || !tasksResponse.ok) {
    throw new Error('Impossible de charger les données de la famille.')
  }
  members.value = await membersResponse.json()
  liens.value = await liensResponse.json()
  familyTasks.value = await tasksResponse.json()
}

async function addMember() {
  errorMessage.value = ''
  successMessage.value = ''
  isSubmitting.value = true
  try {
    const params = new URLSearchParams({
      name: newMember.value.name,
      lien: newMember.value.lien,
      email: newMember.value.email,
      password: newMember.value.password,
      is_admin: String(newMember.value.is_admin),
    })
    const response = await apiFetch(`/api/members?${params}`, { method: 'POST' })
    const data = await readApiResponse(response)
    if (!response.ok) throw new Error(data.detail || 'Impossible de créer le compte.')
    members.value.push(data)
    successMessage.value = 'Membre ajouté.'
    newMember.value = { name: '', lien: '', email: '', password: '', is_admin: false }
  } catch (error) {
    errorMessage.value = error.message
  } finally {
    isSubmitting.value = false
  }
}

async function addLien() {
  const label = newLien.value.trim()
  if (!label) return
  errorMessage.value = ''
  successMessage.value = ''
  const params = new URLSearchParams({ label })
  const response = await apiFetch(`/api/liens?${params}`, { method: 'POST' })
  const data = await readApiResponse(response)
  if (!response.ok) {
    errorMessage.value = data.detail || 'Impossible d’ajouter ce lien.'
    return
  }
  liens.value = data
  newLien.value = ''
  successMessage.value = 'Lien ajouté.'
}

function requestDeleteMember(member) {
  // Ouvre la même confirmation graphique que pour la suppression d'une tâche.
  memberToDelete.value = member
}

async function confirmDeleteMember() {
  if (!memberToDelete.value) return
  errorMessage.value = ''
  const response = await apiFetch(`/api/members/${memberToDelete.value.id}`, { method: 'DELETE' })
  const data = await readApiResponse(response)
  if (!response.ok) {
    errorMessage.value = data.detail || 'Impossible de supprimer ce membre.'
    return
  }
  memberToDelete.value = null
  await loadFamily()
}

function cancelDeleteMember() {
  memberToDelete.value = null
}

onMounted(async () => {
  try {
    await loadFamily()
  } catch (error) {
    errorMessage.value = error.message
  }
})
</script>

<template>
  <header class="topbar">
    <details v-if="currentMember?.is_admin" class="section-menu">
      <summary>☰ Menu</summary>
      <nav aria-label="Sections de l'application"><RouterLink to="/tasks">Tâches</RouterLink><RouterLink to="/assistant">Assistant IA</RouterLink><RouterLink to="/family">Famille</RouterLink></nav>
    </details>
    <div class="brand-lockup"><span class="brand-mark">✦</span><div><p class="eyebrow">FAMILY HQ / PEOPLE OPS</p><h1>FamilyTask</h1></div></div>
    <div class="topbar-actions"><span v-if="currentMember" class="member-greeting"><MemberAvatar :name="currentMember.name" size="small" />Bonjour {{ currentMember.name }}</span><RouterLink class="logout-button" to="/tasks">Tâches</RouterLink></div>
  </header>

  <main v-if="currentMember?.is_admin" class="page-shell family-shell">
    <section class="hero-copy"><p class="kicker">FAMILY ROSTER</p><h2>La famille.</h2><p class="subtitle">Les personnes, les liens et les missions du foyer.</p></section>
    <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
    <p v-if="successMessage" class="form-success" role="status">{{ successMessage }}</p>

    <section class="card family-card">
      <div class="board-heading"><div><p class="section-label">MEMBERS</p><h3>Qui fait partie de l’équipe ?</h3></div><span class="task-count">{{ members.length }} MEMBRES</span></div>
      <ul class="member-list">
        <li v-for="member in members" :key="member.id" class="member-row">
          <MemberAvatar :name="member.name" />
          <div><strong>{{ member.name }}</strong><span class="member-relation">{{ member.lien || 'Lien non renseigné' }}</span><span v-if="member.is_admin" class="admin-badge">admin</span></div>
          <button v-if="member.id !== currentMember.id" type="button" class="delete-button" :aria-label="`Supprimer ${member.name}`" :title="`Supprimer ${member.name}`" @click="requestDeleteMember(member)">🗑️</button>
        </li>
      </ul>
    </section>

    <section class="family-grid">
      <section class="card family-card">
        <p class="section-label">NEW MEMBER</p><h3>Ajouter quelqu’un</h3>
        <form class="family-form" @submit.prevent="addMember">
          <label>Prénom<input v-model="newMember.name" type="text" required /></label>
          <label>Lien<select v-model="newMember.lien" required><option disabled value="">Choisir un lien</option><option v-for="lien in liens" :key="lien" :value="lien">{{ lien }}</option></select></label>
          <label>Email<input v-model="newMember.email" type="email" required /></label>
          <label>Mot de passe<input v-model="newMember.password" type="password" required /></label>
          <label class="checkbox-line"><input v-model="newMember.is_admin" type="checkbox" /> Administrateur</label>
          <button type="submit" :disabled="isSubmitting">{{ isSubmitting ? 'Création...' : 'Créer le compte' }}</button>
        </form>
      </section>

      <section class="card family-card">
        <p class="section-label">RELATIONSHIPS</p><h3>Ajouter un lien</h3>
        <form class="family-form" @submit.prevent="addLien"><label>Nouveau lien<input v-model="newLien" type="text" placeholder="cousine" required /></label><button type="submit">Ajouter le lien</button></form>
        <ul class="link-list"><li v-for="lien in liens" :key="lien">{{ lien }}</li></ul>
      </section>
    </section>

    <section class="card family-card">
      <div class="board-heading"><div><p class="section-label">FAMILY TASKS</p><h3>Toutes les missions</h3></div><span class="task-count">{{ familyTasks.length }} TÂCHES</span></div>
      <ul class="task-list"><li v-for="task in familyTasks" :key="task.id" class="task-row"><div><span class="task-title" :class="{ done: task.done }">{{ task.title }}</span><small class="task-owner">{{ memberNames.get(task.member_id) || 'Membre inconnu' }}</small></div><small v-if="task.deadline" class="task-deadline">pour {{ task.deadline }}</small></li><li v-if="!familyTasks.length" class="empty-state">Aucune tâche dans la famille.</li></ul>
    </section>

    <div v-if="memberToDelete" class="confirmation-overlay" @click.self="cancelDeleteMember"><section class="confirmation-dialog deadline-dialog"><img class="warning-image" src="https://media1.tenor.com/m/QmGhkPRqFMwAAAAC/persona-5-persona.gif" alt="Confirmation de suppression" /><p class="confirmation-kicker">ARE YOU SURE?</p><h2>Delete member?</h2><p class="confirmation-message">Supprimer « <strong>{{ memberToDelete.name }}</strong> » et toutes ses tâches ?</p><div class="confirmation-actions"><button type="button" class="cancel-button" @click="cancelDeleteMember">Annuler</button><button type="button" class="confirm-button" @click="confirmDeleteMember">Supprimer</button></div></section></div>
  </main>

</template>
