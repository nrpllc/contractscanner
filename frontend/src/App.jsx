import React, { useState, useEffect, useCallback } from 'react'

const API_BASE = '/api'

function usePolling(url, intervalMs = 10000) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(url)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
      setError(null)
    } catch (e) {
      setError(e.message)
    }
  }, [url])

  useEffect(() => {
    fetchData()
    const id = setInterval(fetchData, intervalMs)
    return () => clearInterval(id)
  }, [fetchData, intervalMs])

  return { data, error, refresh: fetchData }
}

function StatusBar({ status }) {
  if (!status) return null
  const running = status.running
  const lastScan = status.last_scan ? new Date(status.last_scan).toLocaleString() : 'Never'
  const nextScan = status.next_scan ? new Date(status.next_scan).toLocaleString() : '--'

  return (
    <div style={styles.statusBar}>
      <div style={styles.statusIndicator}>
        <span style={{
          ...styles.dot,
          background: running ? '#00ff88' : '#666',
          boxShadow: running ? '0 0 10px #00ff88' : 'none',
          animation: running ? 'pulse 1.5s infinite' : 'none',
        }} />
        <span>{running ? 'Scanning...' : 'Idle'}</span>
      </div>
      <div style={styles.statusMeta}>
        <span>Last scan: {lastScan}</span>
        <span style={{ marginLeft: 20 }}>Next: {nextScan}</span>
        {status.new_count_last_scan > 0 && (
          <span style={{ marginLeft: 20, color: '#ff6b6b', fontWeight: 'bold' }}>
            {status.new_count_last_scan} new found last scan
          </span>
        )}
        {status.last_error && (
          <span style={{ marginLeft: 20, color: '#ff4444' }}>Error: {status.last_error}</span>
        )}
      </div>
    </div>
  )
}

const COLUMNS = [
  { key: 'title', label: 'Title' },
  { key: 'source', label: 'Source' },
  { key: 'agency', label: 'Agency' },
  { key: 'contract_type', label: 'Type' },
  { key: 'posted_date', label: 'Posted' },
  { key: 'amount', label: 'Amount' },
  { key: 'vendor', label: 'Vendor' },
  { key: 'found_at', label: 'Found' },
]

function ContractTable({ contracts, sortCol, sortDir, onSort }) {
  if (!contracts || contracts.length === 0) {
    return <div style={styles.empty}>No NYPD contracts found yet. Waiting for scan results...</div>
  }

  return (
    <div style={styles.tableWrap}>
      <table style={styles.table}>
        <thead>
          <tr>
            {COLUMNS.map(col => (
              <th
                key={col.key}
                style={{ ...styles.th, cursor: 'pointer', userSelect: 'none' }}
                onClick={() => onSort(col.key)}
              >
                {col.label}
                {sortCol === col.key && (
                  <span style={{ marginLeft: 4, fontSize: 10 }}>
                    {sortDir === 'asc' ? '\u25B2' : '\u25BC'}
                  </span>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {contracts.map((c, i) => (
            <tr key={i} style={i % 2 === 0 ? styles.rowEven : styles.rowOdd}>
              <td style={styles.td}>
                <a href={c.url} target="_blank" rel="noopener noreferrer" style={styles.link}>
                  {c.title}
                </a>
              </td>
              <td style={styles.td}>
                <span style={{ ...styles.badge, background: sourceColor(c.source) }}>
                  {c.source}
                </span>
              </td>
              <td style={styles.td}>{c.agency}</td>
              <td style={styles.td}>{c.contract_type}</td>
              <td style={styles.td}>{c.posted_date}</td>
              <td style={styles.td}>{c.amount}</td>
              <td style={styles.td}>{c.vendor}</td>
              <td style={styles.td}>{c.found_at ? new Date(c.found_at).toLocaleString() : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function ScanHistory({ scans }) {
  if (!scans || scans.length === 0) return null

  return (
    <div style={styles.section}>
      <h2 style={styles.h2}>Recent Scans</h2>
      <div style={styles.scanGrid}>
        {scans.slice(0, 20).map((s, i) => (
          <div key={i} style={styles.scanCard}>
            <div style={styles.scanSource}>{s.source}</div>
            <div>Found: {s.total_found} | New: <span style={{ color: s.new_found > 0 ? '#00ff88' : '#888' }}>{s.new_found}</span></div>
            <div style={styles.scanTime}>{new Date(s.timestamp).toLocaleString()}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function sourceColor(source) {
  const colors = {
    CityRecord: '#2196F3',
    PASSPort: '#9C27B0',
    CheckbookNYC: '#FF9800',
    NYCOpenData: '#4CAF50',
    'SAM.gov': '#f44336',
  }
  return colors[source] || '#607D8B'
}

function sortContracts(contracts, col, dir) {
  if (!col) return contracts
  return [...contracts].sort((a, b) => {
    let va = a[col] ?? ''
    let vb = b[col] ?? ''
    // Try numeric sort for amount
    if (col === 'amount') {
      const na = parseFloat(String(va).replace(/[^0-9.-]/g, '')) || 0
      const nb = parseFloat(String(vb).replace(/[^0-9.-]/g, '')) || 0
      return dir === 'asc' ? na - nb : nb - na
    }
    // String sort for everything else
    va = String(va).toLowerCase()
    vb = String(vb).toLowerCase()
    if (va < vb) return dir === 'asc' ? -1 : 1
    if (va > vb) return dir === 'asc' ? 1 : -1
    return 0
  })
}

export default function App() {
  const { data: statusData } = usePolling(`${API_BASE}/status`, 5000)
  const { data: contractsData, refresh: refreshContracts } = usePolling(`${API_BASE}/contracts`, 15000)
  const { data: scansData } = usePolling(`${API_BASE}/scans`, 15000)
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState(null)
  const [sortDir, setSortDir] = useState('asc')

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(col)
      setSortDir('asc')
    }
  }

  const triggerScan = async () => {
    await fetch(`${API_BASE}/scan`, { method: 'POST' })
    setTimeout(refreshContracts, 3000)
  }

  const contracts = contractsData?.contracts || []
  const searched = search
    ? contracts.filter(c =>
        JSON.stringify(c).toLowerCase().includes(search.toLowerCase())
      )
    : contracts
  const sorted = sortContracts(searched, sortCol, sortDir)

  return (
    <div style={styles.app}>
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
      `}</style>

      <header style={styles.header}>
        <div>
          <h1 style={styles.h1}>NYPD Contract Monitor</h1>
          <p style={styles.subtitle}>
            Monitoring PASSPort, City Record, Checkbook NYC, NYC Open Data, SAM.gov
          </p>
        </div>
        <button onClick={triggerScan} style={styles.scanBtn}>
          Scan Now
        </button>
      </header>

      <StatusBar status={statusData} />

      <div style={styles.main}>
        <div style={styles.section}>
          <div style={styles.sectionHeader}>
            <h2 style={styles.h2}>Contracts ({sorted.length})</h2>
            <input
              type="text"
              placeholder="Search contracts..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              style={styles.filterInput}
            />
          </div>
          <ContractTable
            contracts={sorted}
            sortCol={sortCol}
            sortDir={sortDir}
            onSort={handleSort}
          />
        </div>

        <ScanHistory scans={scansData?.scans} />
      </div>
    </div>
  )
}

const styles = {
  app: {
    minHeight: '100vh',
    background: '#0a0e1a',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '20px 30px',
    background: 'linear-gradient(135deg, #0d1b3e 0%, #1a1a2e 100%)',
    borderBottom: '1px solid #1e3a5f',
  },
  h1: {
    fontSize: 24,
    fontWeight: 700,
    color: '#fff',
    letterSpacing: 1,
  },
  subtitle: {
    fontSize: 13,
    color: '#6b7b9e',
    marginTop: 4,
  },
  scanBtn: {
    padding: '10px 24px',
    background: '#1e88e5',
    color: '#fff',
    border: 'none',
    borderRadius: 6,
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: 600,
  },
  statusBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 20,
    padding: '12px 30px',
    background: '#0d1220',
    borderBottom: '1px solid #1a2744',
    fontSize: 13,
  },
  statusIndicator: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontWeight: 600,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: '50%',
    display: 'inline-block',
  },
  statusMeta: {
    color: '#8899aa',
  },
  main: {
    padding: '20px 30px',
  },
  section: {
    marginBottom: 30,
  },
  sectionHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  h2: {
    fontSize: 18,
    fontWeight: 600,
    color: '#c0c8d8',
  },
  filterInput: {
    padding: '8px 14px',
    background: '#111827',
    border: '1px solid #2a3a5e',
    borderRadius: 6,
    color: '#e0e0e0',
    fontSize: 13,
    width: 250,
    outline: 'none',
  },
  tableWrap: {
    overflowX: 'auto',
    borderRadius: 8,
    border: '1px solid #1e2d4a',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 13,
  },
  th: {
    padding: '10px 12px',
    textAlign: 'left',
    background: '#111827',
    color: '#8899bb',
    fontWeight: 600,
    borderBottom: '2px solid #1e3050',
    whiteSpace: 'nowrap',
  },
  td: {
    padding: '10px 12px',
    borderBottom: '1px solid #1a2540',
    maxWidth: 300,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  rowEven: {
    background: '#0d1220',
  },
  rowOdd: {
    background: '#0f1628',
  },
  link: {
    color: '#4da6ff',
    textDecoration: 'none',
  },
  badge: {
    padding: '3px 8px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 600,
    color: '#fff',
  },
  empty: {
    padding: 40,
    textAlign: 'center',
    color: '#556',
    fontSize: 15,
  },
  scanGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
    gap: 10,
  },
  scanCard: {
    padding: '10px 14px',
    background: '#111827',
    borderRadius: 6,
    border: '1px solid #1e2d4a',
    fontSize: 12,
  },
  scanSource: {
    fontWeight: 600,
    color: '#a0b0cc',
    marginBottom: 4,
  },
  scanTime: {
    color: '#556',
    marginTop: 4,
    fontSize: 11,
  },
}
