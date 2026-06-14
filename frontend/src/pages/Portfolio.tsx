import { TrendingUp, TrendingDown } from 'lucide-react'

const DEALS = [
  { name: 'Wella Beauty Holdings', sector: 'Consumer', geo: 'Global', status: 'Active', aum: 3.2, twr: 42.1 },
  { name: 'Project Taka', sector: 'Real Estate', geo: 'Asia', status: 'Active', aum: 2.8, twr: 28.5 },
  { name: 'NA Tech Fund IV', sector: 'Private Equity', geo: 'NA', status: 'Active', aum: 2.1, twr: 65.3 },
  { name: 'APAC Logistics Hub', sector: 'Real Estate', geo: 'Asia', status: 'Active', aum: 1.9, twr: 19.2 },
  { name: 'EU Green Bond', sector: 'Credit', geo: 'Europe', status: 'Active', aum: 1.5, twr: 11.0 },
  { name: 'SEA Growth Fund', sector: 'Equities', geo: 'Asia', status: 'Active', aum: 1.4, twr: 33.7 },
]

export default function Portfolio() {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold text-white">Portfolio Deals</h1>

      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700 text-slate-400 text-xs uppercase">
              <th className="text-left px-4 py-3">Deal</th>
              <th className="text-left px-4 py-3">Sector</th>
              <th className="text-left px-4 py-3">Geo</th>
              <th className="text-right px-4 py-3">AUM ($M)</th>
              <th className="text-right px-4 py-3">TWR (%)</th>
              <th className="text-left px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            {DEALS.map(d => (
              <tr key={d.name} className="border-b border-slate-700/50 hover:bg-slate-700/30 transition-colors">
                <td className="px-4 py-3 text-white font-medium">{d.name}</td>
                <td className="px-4 py-3 text-slate-300">{d.sector}</td>
                <td className="px-4 py-3 text-slate-300">{d.geo}</td>
                <td className="px-4 py-3 text-right text-white">{d.aum.toFixed(1)}</td>
                <td className="px-4 py-3 text-right">
                  <span className={`flex items-center justify-end gap-1 ${d.twr >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {d.twr >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                    {d.twr.toFixed(1)}%
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="bg-emerald-900/40 text-emerald-400 text-xs px-2 py-0.5 rounded-full">
                    {d.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
