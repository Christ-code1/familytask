<script setup>
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

const router = useRouter()
const family = ref('')
const name = ref('')
const lien = ref('parent')
const email = ref('')
const password = ref('')
const errorMessage = ref('')
const isSubmitting = ref(false)

// Crée la famille avec les champs attendus par l'API FastAPI.
async function submitSignup() {
  errorMessage.value = ''
  isSubmitting.value = true

  try {
    const params = new URLSearchParams({ family: family.value, name: name.value, lien: lien.value, email: email.value, password: password.value })
    const response = await fetch(`/api/signup?${params}`, { method: 'POST' })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || 'La création de la famille a été refusée.')

    localStorage.setItem('token', data.token)
    await router.push('/tasks')
  } catch (error) {
    errorMessage.value = error.message || 'La création du compte a échoué.'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-card card">
      <p class="kicker">FAMILY HQ / NEW CREW</p>
      <h1>Créer sa famille</h1>
      <p class="auth-intro">Un espace partagé pour les petites missions du quotidien.</p>
      <form class="auth-form" @submit.prevent="submitSignup">
        <label>Nom de famille <input v-model="family" type="text" autocomplete="family-name" required /></label>
        <label>Prénom <input v-model="name" type="text" autocomplete="given-name" required /></label>
        <label>Lien de parenté
          <select v-model="lien">
            <option value="parent">Parent</option>
            <option value="enfant">Enfant</option>
            <option value="autre">Autre</option>
          </select>
        </label>
        <label>Email <input v-model="email" type="email" autocomplete="email" required /></label>
        <label>Mot de passe <input v-model="password" type="password" autocomplete="new-password" required /></label>
        <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
        <button type="submit" :disabled="isSubmitting">{{ isSubmitting ? 'Création...' : 'Créer ma famille' }}</button>
      </form>
      <RouterLink class="auth-link" to="/login">Déjà un compte ? Se connecter</RouterLink>
    </section>
  </main>
</template>