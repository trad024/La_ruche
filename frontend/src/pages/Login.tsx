import { useAuth } from '../auth/AuthContext'

export default function Login() {
  const { login } = useAuth()

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4">
      <div className="bg-slate-800 rounded-2xl p-8 border border-slate-700 w-full max-w-sm text-center">
        <div className="w-16 h-16 bg-purple-600 rounded-2xl flex items-center justify-center mx-auto mb-4">
          <span className="text-2xl font-bold text-white">W</span>
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">WealthMesh</h1>
        <p className="text-slate-400 text-sm mb-8">Private Banking AI Platform</p>
        <button
          onClick={login}
          className="w-full bg-purple-600 hover:bg-purple-700 text-white font-medium py-3 px-4 rounded-xl transition-colors"
        >
          Sign in with SSO
        </button>
        <p className="text-xs text-slate-500 mt-4">Secured by Keycloak PKCE</p>
      </div>
    </div>
  )
}
