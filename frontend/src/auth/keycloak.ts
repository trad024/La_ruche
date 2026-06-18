import Keycloak from 'keycloak-js'

const _kc = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL ?? 'http://localhost:8180',
  realm: import.meta.env.VITE_KEYCLOAK_REALM ?? 'wealth',
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? 'web',
})

let initialization: Promise<boolean> | null = null

export function initializeKeycloak() {
  if (!initialization) {
    initialization = _kc.init({
      onLoad: 'check-sso',
      pkceMethod: 'S256',
      checkLoginIframe: false,
    })
  }
  return initialization
}

export default _kc
