// Adresse du serveur back-end, fournie par la variable d'environnement Vite.
// Chaîne vide par défaut : en local, les requêtes restent relatives (même origine),
// donc le mode local continue de fonctionner sans configuration supplémentaire.
const API_URL = import.meta.env.VITE_API_URL || ''

export function apiFetch(path, options = {}) {
  const headers = new Headers(options.headers || {})
  const token = localStorage.getItem('token')
  if (token) headers.set('Authorization', `Bearer ${token}`)

  // Préfixe le chemin avec l'adresse du back-end (vide en local, donc chemin relatif inchangé).
  return fetch(`${API_URL}${path}`, { ...options, headers })
}
