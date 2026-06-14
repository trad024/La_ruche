import { TrendingUp, DollarSign, BarChart3, Globe } from 'lucide-react'

const METRICS = [
  { label: 'Total AUM', value: '$20.4M', sub: '+7.14% annualized', icon: DollarSign, color: 'text-emerald-400' },
  { label: 'TWR', value: '178.65%', sub: 'Since inception', icon: TrendingUp, color: 'text-blue-400' },
  { label: 'IRR', value: '8.23%', sub: 'Internal Rate of Return', icon: BarChart3, color: 'text-purple-400' },
  { label: 'Sharpe Ratio', value: '0.58', sub: 'Vol: 12.27%', icon: Globe, color: 'text-amber-400' },
]

const GEO = [
  { label: 'Asia', pct: 37, color: 'bg-blue-500' },
  { label: 'North America', pct: 35, color: 'bg-emerald-500' },
  { label: 'Global', pct: 16, color: 'bg-purple-500' },
  { label: 'Europe', pct: 4, color: 'bg-amber-500' },
  { label: 'Other', pct: 8, color: 'bg-slate-500' },
]

const SECTORS = [
  { label: 'Real Estate', pct: 45, color: 'bg-blue-500' },
  { label: 'Private Equity', pct: 35, color: 'bg-emerald-500' },
  { label: 'Equities', pct: 15, color: 'bg-purple-500' },
  { label: 'Credit', pct: 5, color: 'bg-amber-500' },
]

export default function Dashboard() {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold text-white">Portfolio Overview</h1>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {METRICS.map(m => (
          <div key={m.label} className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex items-center gap-2 mb-2">
              <m.icon className={`w-4 h-4 ${m.color}`} />
              <span className="text-xs text-slate-400">{m.label}</span>
            </div>
            <p className={`text-2xl font-bold ${m.color}`}>{m.value}</p>
            <p className="text-xs text-slate-400 mt-1">{m.sub}</p>
          </div>
        ))}
      </div>

      {/* Breakdowns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <BreakdownCard title="Geographic Allocation" data={GEO} />
        <BreakdownCard title="Sector Allocation" data={SECTORS} />
      </div>

      {/* Summary */}
      <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">Portfolio Summary</h2>
        <div className="grid grid-cols-3 gap-4 text-center">
          <Stat label="Active Deals" value="42" />
          <Stat label="Total Profit" value="$7.85M" />
          <Stat label="Volatility" value="12.27%" />
        </div>
      </div>
    </div>
  )
}

function BreakdownCard({ title, data }: { title: string; data: typeof GEO }) {
  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
      <h2 className="text-sm font-semibold text-slate-300 mb-3">{title}</h2>
      <div className="space-y-2">
        {data.map(d => (
          <div key={d.label} className="flex items-center gap-3">
            <span className="text-xs text-slate-400 w-28 shrink-0">{d.label}</span>
            <div className="flex-1 bg-slate-700 rounded-full h-2">
              <div className={`${d.color} h-2 rounded-full`} style={{ width: `${d.pct}%` }} />
            </div>
            <span className="text-xs text-slate-300 w-8 text-right">{d.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-lg font-bold text-white">{value}</p>
      <p className="text-xs text-slate-400">{label}</p>
    </div>
  )
}
