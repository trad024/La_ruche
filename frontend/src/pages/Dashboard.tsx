import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ArrowUpRight, Globe2, Sparkles } from 'lucide-react'
import { getAllocation, getPortfolioSummary } from '../api/client'

const SECTOR_COLORS = ['#F5A623', '#34B3A8', '#2C8C8C', '#5E7977']
const DONUT_R = 54
const DONUT_C = 2 * Math.PI * DONUT_R

type RangeKey = '1M' | '3M' | 'YTD' | '1Y' | 'ALL'

const RANGES: Record<RangeKey, {
  label: string
  portfolio: number[]
  benchmark: number[]
  axis: string[]
  twrFactor: number
  annualizedFactor: number
  volatilityFactor: number
}> = {
  '1M': {
    label: 'Last 30 days',
    portfolio: [202, 196, 188, 193, 176, 168, 154, 148],
    benchmark: [205, 202, 198, 201, 193, 188, 180, 176],
    axis: ['W1', 'W2', 'W3', 'W4'],
    twrFactor: 0.012,
    annualizedFactor: 0.1,
    volatilityFactor: 0.45,
  },
  '3M': {
    label: 'Last 3 months',
    portfolio: [204, 190, 198, 174, 158, 142, 120, 112],
    benchmark: [207, 200, 194, 186, 176, 168, 156, 150],
    axis: ['Apr', 'May', 'Jun'],
    twrFactor: 0.036,
    annualizedFactor: 0.25,
    volatilityFactor: 0.65,
  },
  YTD: {
    label: 'Year to date',
    portfolio: [200, 182, 188, 150, 118, 132, 78, 92],
    benchmark: [206, 200, 197, 182, 170, 172, 150, 156],
    axis: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
    twrFactor: 0.11,
    annualizedFactor: 0.52,
    volatilityFactor: 0.78,
  },
  '1Y': {
    label: 'Trailing 12 months',
    portfolio: [210, 205, 178, 162, 170, 138, 116, 96],
    benchmark: [211, 204, 198, 188, 182, 174, 164, 150],
    axis: ['Q3', 'Q4', 'Q1', 'Q2'],
    twrFactor: 0.22,
    annualizedFactor: 0.95,
    volatilityFactor: 1,
  },
  ALL: {
    label: 'Since inception',
    portfolio: [214, 198, 184, 152, 126, 96, 68, 44],
    benchmark: [210, 202, 190, 176, 160, 150, 140, 132],
    axis: ['2019', '2020', '2021', '2022', '2023', '2024', '2025', "'26"],
    twrFactor: 1,
    annualizedFactor: 1,
    volatilityFactor: 1.08,
  },
}

const RANGE_KEYS = Object.keys(RANGES) as RangeKey[]

function pathFromPoints(points: number[]) {
  const startX = 40
  const endX = 940
  const step = (endX - startX) / (points.length - 1)
  return points.map((y, index) => `${index === 0 ? 'M' : 'L'}${startX + step * index} ${y}`).join(' ')
}

function areaFromPath(path: string) {
  return `${path} L940 230 L40 230 Z`
}

function fmtPct(value: number) {
  return value.toFixed(2)
}

export default function Dashboard() {
  const [range, setRange] = useState<RangeKey>('YTD')
  const summary = useQuery({ queryKey: ['summary'], queryFn: getPortfolioSummary })
  const alloc = useQuery({ queryKey: ['allocation'], queryFn: getAllocation })

  if (summary.isLoading || alloc.isLoading) {
    return <div className="loading-state">Loading portfolio intelligence...</div>
  }
  if (summary.isError || alloc.isError || !summary.data || !alloc.data) {
    return <div className="error-state">Could not load portfolio data.</div>
  }

  const s = summary.data
  const rangeData = RANGES[range]
  const perfLine = pathFromPoints(rangeData.portfolio)
  const perfBench = pathFromPoints(rangeData.benchmark)
  const rangeTwr = s.twr_pct * rangeData.twrFactor
  const rangeAnnualized = s.annualized_pct * rangeData.annualizedFactor
  const rangeVolatility = s.volatility_pct * rangeData.volatilityFactor
  const geoEntries = Object.entries(alloc.data.geography)
  const geoMax = Math.max(...geoEntries.map(([, v]) => v))
  const sectorEntries = Object.entries(alloc.data.sector)

  let cursor = 0
  const segments = sectorEntries.map(([name, pct], i) => {
    const dash = (pct / 100) * DONUT_C
    const seg = { name, pct, color: SECTOR_COLORS[i % SECTOR_COLORS.length], dash, offset: -cursor }
    cursor += dash
    return seg
  })

  return (
    <div className="page">
      <header className="page-intro" style={{ justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 15 }}>
          <div className="page-icon"><Globe2 className="h-5 w-5" /></div>
          <div>
            <p className="eyebrow">Live portfolio</p>
            <h1>Portfolio Overview</h1>
            <p>As of June 14, 2026 · Reported in USD</p>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="range-toggle" role="group" aria-label="Performance range">
            {RANGE_KEYS.map(item => (
              <button
                key={item}
                type="button"
                className={range === item ? 'range-active' : ''}
                aria-pressed={range === item}
                onClick={() => setRange(item)}
              >
                {item}
              </button>
            ))}
          </div>
          <button className="primary-button"><Sparkles className="h-4 w-4" />Ask LaRuche</button>
        </div>
      </header>

      <div className="kpi-band">
        <div className="kpi-hero">
          <div className="kpi-hero-label">Total Assets Under Management</div>
          <div className="kpi-hero-value">{s.aum_fmt}</div>
          <div className="kpi-hero-delta">
            <ArrowUpRight className="h-4 w-4" />
            <span className="num">+{fmtPct(rangeAnnualized)}%</span>
            <span className="muted">{rangeData.label}</span>
          </div>
        </div>
        <div className="kpi-cells">
          <div className="kpi-cell">
            <div className="kpi-cell-label">TWR · {range}</div>
            <div className="kpi-cell-value" style={{ color: 'var(--teal)' }}>{fmtPct(rangeTwr)}%</div>
            <div className="kpi-cell-note">Time-weighted</div>
          </div>
          <div className="kpi-cell">
            <div className="kpi-cell-label">Annualized · {range}</div>
            <div className="kpi-cell-value">{fmtPct(rangeAnnualized)}%</div>
            <div className="kpi-cell-note">IRR {s.irr_pct.toFixed(2)}%</div>
          </div>
          <div className="kpi-cell">
            <div className="kpi-cell-label">Net Profit</div>
            <div className="kpi-cell-value">{s.profit_fmt}</div>
            <div className="kpi-cell-note" style={{ color: 'var(--green)' }}>{s.num_active} of {s.num_deals} deals active</div>
          </div>
        </div>
      </div>

      <div className="dash-grid">
        <section className="surface-card chart-card">
          <div className="chart-head">
            <h3>Portfolio Performance</h3>
            <div className="chart-legend">
              <span><span className="legend-swatch" style={{ background: 'var(--accent)' }} />Portfolio</span>
              <span><span className="legend-swatch" style={{ background: '#3a5b59' }} />Benchmark</span>
            </div>
          </div>
          <svg className="perf-chart" viewBox="0 0 980 240" preserveAspectRatio="none">
            <defs>
              <linearGradient id="perfgrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#F5A623" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#F5A623" stopOpacity="0" />
              </linearGradient>
            </defs>
            <line x1="40" y1="60" x2="940" y2="60" stroke="#143130" strokeWidth="1" />
            <line x1="40" y1="130" x2="940" y2="130" stroke="#143130" strokeWidth="1" />
            <line x1="40" y1="200" x2="940" y2="200" stroke="#143130" strokeWidth="1" />
            <path d={areaFromPath(perfLine)} fill="url(#perfgrad)" />
            <path d={perfBench} fill="none" stroke="#3a5b59" strokeWidth="2" strokeLinejoin="round" />
            <path d={perfLine} fill="none" stroke="#F5A623" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
          </svg>
          <div className="chart-axis">
            {rangeData.axis.map(y => <span key={y}>{y}</span>)}
          </div>
          <div className="risk-footer">
            <div><small>Sharpe</small><strong>{s.sharpe.toFixed(2)}</strong></div>
            <div><small>Volatility</small><strong>{fmtPct(rangeVolatility)}%</strong></div>
            <div><small>Annualized</small><strong>{fmtPct(rangeAnnualized)}%</strong></div>
            <div style={{ marginLeft: 'auto', textAlign: 'right' }}><small>IRR</small><strong style={{ color: 'var(--green)' }}>{s.irr_pct.toFixed(2)}%</strong></div>
          </div>
        </section>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <section className="surface-card data-panel">
            <div className="data-panel-header"><h2>Geographic Allocation</h2><span>Exposure by region</span></div>
            {geoEntries.map(([name, pct]) => (
              <div className="bar-row" key={name}>
                <span className="bar-label">{name}</span>
                <div className="bar-track"><div className="bar-fill" style={{ width: `${(pct / geoMax) * 100}%` }} /></div>
                <span className="bar-value">{pct}%</span>
              </div>
            ))}
          </section>

          <section className="surface-card data-panel">
            <div className="data-panel-header"><h2>Sector Mix</h2><span>Capital by strategy</span></div>
            <div className="donut-row">
              <svg className="donut-svg" viewBox="0 0 130 130">
                <circle cx="65" cy="65" r={DONUT_R} fill="none" stroke="#102524" strokeWidth="14" />
                {segments.map(seg => (
                  <circle
                    key={seg.name}
                    cx="65" cy="65" r={DONUT_R} fill="none"
                    stroke={seg.color} strokeWidth="14"
                    strokeDasharray={`${seg.dash} ${DONUT_C - seg.dash}`}
                    strokeDashoffset={seg.offset}
                  />
                ))}
              </svg>
              <div className="donut-legend">
                {segments.map(seg => (
                  <div key={seg.name}>
                    <span className="swatch" style={{ background: seg.color }} />
                    <span className="name">{seg.name}</span>
                    <span className="pct">{seg.pct}%</span>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
