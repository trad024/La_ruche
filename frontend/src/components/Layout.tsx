import { type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, MessageSquare, BarChart3, TrendingUp, LogOut } from 'lucide-react'
import { useAuth } from '../auth/AuthContext'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/portfolio', label: 'Portfolio', icon: BarChart3 },
  { to: '/market', label: 'Market', icon: TrendingUp },
  { to: '/chat', label: 'AI Chat', icon: MessageSquare },
]

export default function Layout({ children }: { children: ReactNode }) {
  const { username, logout } = useAuth()

  return (
    <div className="flex h-screen bg-slate-900">
      {/* Sidebar */}
      <nav className="w-56 bg-slate-800 border-r border-slate-700 flex flex-col">
        <div className="p-4 border-b border-slate-700">
          <h1 className="text-lg font-bold text-white">WealthMesh</h1>
          <p className="text-xs text-purple-400">Private Banking AI</p>
        </div>

        <div className="flex-1 p-3 space-y-1">
          {NAV.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-purple-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`
              }
            >
              <item.icon className="w-4 h-4" />
              {item.label}
            </NavLink>
          ))}
        </div>

        <div className="p-3 border-t border-slate-700">
          <div className="flex items-center gap-2 px-3 py-2 text-xs text-slate-400">
            <div className="w-6 h-6 rounded-full bg-purple-700 flex items-center justify-center text-white text-xs">
              {username?.[0]?.toUpperCase() ?? 'U'}
            </div>
            <span className="truncate">{username ?? 'Advisor'}</span>
          </div>
          <button
            onClick={logout}
            className="flex items-center gap-2 px-3 py-2 text-xs text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg w-full transition-colors"
          >
            <LogOut className="w-3 h-3" />
            Sign out
          </button>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}
