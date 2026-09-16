<script setup>
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { apiFetch } from '../api'

const router = useRouter()
const email = ref('')
const password = ref('')
const errorMessage = ref('')
const isSubmitting = ref(false)

// Envoie les identifiants à l'API puis conserve le token de session.
async function submitLogin() {
  errorMessage.value = ''
  isSubmitting.value = true

  try {
    const params = new URLSearchParams({ email: email.value, password: password.value })
    const response = await apiFetch(`/api/login?${params}`, { method: 'POST' })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || 'Email ou mot de passe incorrect.')

    localStorage.setItem('token', data.token)
    await router.push('/tasks')
  } catch (error) {
    errorMessage.value = error.message || 'La connexion a échoué.'
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-card card">
      <p class="kicker">FAMILY HQ / ACCESS</p>
      <h1>Se connecter</h1>
      <p class="auth-intro">Retrouvez les missions de votre famille.</p>
      <form class="auth-form" @submit.prevent="submitLogin">
        <label>Email <input v-model="email" type="email" autocomplete="email" required /></label>
        <label>Mot de passe <input v-model="password" type="password" autocomplete="current-password" required /></label>
        <p v-if="errorMessage" class="form-error" role="alert">{{ errorMessage }}</p>
        <button type="submit" :disabled="isSubmitting">{{ isSubmitting ? 'Connexion...' : 'Se connecter' }}</button>
      </form>
      <RouterLink class="auth-link" to="/signup">Pas encore de compte ?</RouterLink>
    </section>
  </main>
</template>