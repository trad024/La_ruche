import { ShieldCheck } from 'lucide-react'
import { useAuth } from '../auth/useAuth'

export default function Login() {
  const { login } = useAuth()

  return (
    <div className="login-screen">
      <section className="login-visual">
        <div className="login-mesh" />
        <div className="login-copy">
          <p className="eyebrow">Private banking, reimagined</p>
          <h1>Intelligence for every wealth decision.</h1>
          <p>
            One secure workspace for portfolio analytics, market context, document intelligence,
            conversational advice, and natural voice interaction.
          </p>
        </div>
      </section>

      <section className="login-form-wrap">
        <div className="glass-panel login-card">
          <div className="login-brand-lockup">
            <img src="/brand/laruche-animated.gif" alt="LaRuche" />
            <p>Private intelligence</p>
          </div>
          <h2>Welcome back</h2>
          <p>Sign in to enter your secure advisory workspace.</p>
          <button onClick={login} className="primary-button login-button">
            Sign in with SSO
          </button>
          <div className="login-security">
            <ShieldCheck className="h-3.5 w-3.5" />
            Secured with Keycloak PKCE
          </div>
        </div>
      </section>
    </div>
  )
}
