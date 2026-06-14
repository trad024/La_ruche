import Keycloak from 'keycloak-js'

const _kc = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL ?? 'http://localhost:8180',
  realm: import.meta.env.VITE_KEYCLOAK_REALM ?? 'wealth',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? 'wealth-web',
})

export default _kc
