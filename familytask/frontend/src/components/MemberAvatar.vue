<script setup>
import { computed } from 'vue'

// Avatar généré automatiquement pour n'importe quel membre : buste gris/noir façon
// portrait stylisé, avec l'initiale du prénom en accent rouge ou jaune (couleurs de l'appli).
// Pas de vraie photo : ça évite de dépendre d'une image par personne et ça marche
// tout de suite pour un nouveau membre ajouté dans la famille.
const props = defineProps({
  name: { type: String, default: '' },
  size: { type: String, default: 'normal' }, // 'normal' ou 'small'
})

const accentColors = ['#e52b32', '#f4c542']
const initial = computed(() => props.name?.trim().charAt(0).toUpperCase() || '?')
const accent = computed(() => {
  const code = props.name?.trim().toUpperCase().charCodeAt(0) || 0
  return accentColors[code % accentColors.length]
})
</script>

<template>
  <span class="avatar" :class="{ 'avatar--small': size === 'small' }" role="img" :aria-label="`Avatar de ${name}`">
    <svg viewBox="0 0 64 64" width="100%" height="100%" aria-hidden="true">
      <rect width="64" height="64" fill="#8a8a8a" />
      <circle cx="32" cy="25" r="14" fill="#181818" />
      <path d="M6 63 C6 43 17 35 32 35 C47 35 58 43 58 63 Z" fill="#181818" />
    </svg>
    <span class="avatar-initial" :style="{ color: accent }">{{ initial }}</span>
  </span>
</template>
