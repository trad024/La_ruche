import { TrendingUp, TrendingDown } from 'lucide-react'

const QUOTES = [
  { symbol: 'SPX', name: 'S&P 500', price: 5247.49, change: 0.42 },
  { symbol: 'AAPL', name: 'Apple Inc.', price: 189.30, change: -0.18 },
  { symbol: 'TSLA', name: 'Tesla Inc.', price: 175.22, change: 1.05 },
  { symbol: 'BTC', name: 'Bitcoin', price: 67450.0, change: 2.33 },
  { symbol: 'GLD', name: 'Gold (oz)', price: 2328.60, change: 0.15 },
  { symbol: 'USDEUR', name: 'USD/EUR', price: 0.9285, change: -0.05 },
]

const INDICATORS = [
  { label: 'US GDP Growth', value: '2.8%', date: '2024 Q4' },
  { label: 'US CPI Inflation', value: '3.1%', date: 'Dec 2024' },
  { label: 'Fed Funds Rate', value: '5.25%', date: 'Dec 2024' },
  { label: '10Y Treasury', value: '4.55%', date: 'Dec 2024' },
  { label: 'VIX', value: '14.8', date: 'Dec 2024' },
  { label: 'IMF Global Growth', value: '3.2%', date: '2025F' },
]

export default function Market() {
  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-semibold text-white">Market Data</h1>

      <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
        {QUOTES.map(q => (
          <div key={q.symbol} className="bg-slate-800 rounded-xl p-4 border border-slate-700">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-xs text-slate-400">{q.name}</p>
                <p className="text-lg font-bold text-white mt-1">
                  {q.price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
              </div>
              <span className={`flex items-center gap-1 text-sm font-medium ${q.change >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {q.change >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                {q.change >= 0 ? '+' : ''}{q.change.toFixed(2)}%
              </span>
            </div>
            <p className="text-xs text-slate-500 mt-2">{q.symbol}</p>
          </div>
        ))}
      </div>

      <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
        <h2 className="text-sm font-semibold text-slate-300 mb-3">Economic Indicators</h2>
        <div className="grid grid-cols-2 lg:grid-cols-3 gap-3">
          {INDICATORS.map(ind => (
            <div key={ind.label} className="bg-slate-700/50 rounded-lg p-3">
              <p className="text-xs text-slate-400">{ind.label}</p>
              <p className="text-lg font-bold text-white">{ind.value}</p>
              <p className="text-xs text-slate-500">{ind.date}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
