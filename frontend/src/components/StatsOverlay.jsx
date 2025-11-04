import { X } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, PieChart, Pie, Cell } from 'recharts'

const AGENT_TYPE_COLORS = {
  farmer: '#6b8e23',
  FARMER: '#6b8e23',
  trader: '#b8860b',
  TRADER: '#b8860b',
  crafter: '#8b4513',
  CRAFTER: '#8b4513',
  gatherer: '#228b22',
  GATHERER: '#228b22',
  leader: '#4169e1',
  LEADER: '#4169e1',
  specialist: '#9932cc',
  SPECIALIST: '#9932cc',
  cooperator: '#20b2aa',
  COOPERATOR: '#20b2aa',
  opportunist: '#dc143c',
  OPPORTUNIST: '#dc143c',
  generalist: '#708090',
  GENERALIST: '#708090',
  IDLE: '#d3d3d3',
}

function StatsOverlay({ metrics, events, onClose }) {
  if (!metrics) {
    return null
  }
  
  const agentTypesData = Object.entries(metrics.agentTypes || {}).map(([name, value]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1).toLowerCase(),
    value,
    color: AGENT_TYPE_COLORS[name] || '#708090',
  }))
  
  const tradeVolumeData = (metrics.tradeVolume || []).map(([tick, volume]) => ({
    tick,
    volume,
  }))
  
  const giniData = (metrics.giniHistory || []).map(([tick, gini]) => ({
    tick,
    gini,
  }))
  
  const actionCounts = {}
  for (const event of events.slice(-200)) {
    actionCounts[event.type] = (actionCounts[event.type] || 0) + 1
  }
  const actionData = Object.entries(actionCounts).map(([name, value]) => ({
    name,
    value,
  }))
  
  return (
    <div className="stats-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="stats-modal">
        <div className="stats-modal-header">
          <h2>Statistics Dashboard</h2>
          <button className="stats-modal-close" onClick={onClose}>
            <X size={24} />
          </button>
        </div>
        
        <div className="stats-modal-content">
          <div className="stats-grid">
            <div className="stats-card">
              <h3>Agent Types Distribution</h3>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={agentTypesData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      outerRadius={70}
                      label={({ name, value }) => `${name}: ${value}`}
                    >
                      {agentTypesData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="agent-types-grid" style={{ marginTop: '12px' }}>
                {agentTypesData.map((type) => (
                  <div key={type.name} className="agent-type-item">
                    <div className="agent-type-label">
                      <div className="agent-type-dot" style={{ backgroundColor: type.color }} />
                      <span>{type.name}</span>
                    </div>
                    <span className="agent-type-count">{type.value}</span>
                  </div>
                ))}
              </div>
            </div>
            
            <div className="stats-card">
              <h3>Trade Volume Over Time</h3>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={tradeVolumeData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e8f0e8" />
                    <XAxis dataKey="tick" stroke="#7a9a7a" fontSize={10} />
                    <YAxis stroke="#7a9a7a" fontSize={10} />
                    <Tooltip
                      contentStyle={{
                        background: '#fff',
                        border: '1px solid #c8d8c8',
                        borderRadius: '6px',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="volume"
                      stroke="#5a8a5a"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div className="stats-card">
              <h3>Wealth Inequality (Gini)</h3>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={giniData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e8f0e8" />
                    <XAxis dataKey="tick" stroke="#7a9a7a" fontSize={10} />
                    <YAxis stroke="#7a9a7a" fontSize={10} domain={[0, 1]} />
                    <Tooltip
                      contentStyle={{
                        background: '#fff',
                        border: '1px solid #c8d8c8',
                        borderRadius: '6px',
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="gini"
                      stroke="#b8860b"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div className="stats-card">
              <h3>Action Distribution (Last 200)</h3>
              <div className="chart-container">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={actionData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e8f0e8" />
                    <XAxis dataKey="name" stroke="#7a9a7a" fontSize={9} angle={-45} textAnchor="end" height={60} />
                    <YAxis stroke="#7a9a7a" fontSize={10} />
                    <Tooltip
                      contentStyle={{
                        background: '#fff',
                        border: '1px solid #c8d8c8',
                        borderRadius: '6px',
                      }}
                    />
                    <Bar dataKey="value" fill="#5a8a5a" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div className="stats-card">
              <h3>Economy Overview</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Total Wealth</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {metrics.wealth?.total_wealth?.toFixed(0) || 0}
                  </div>
                </div>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Mean Wealth</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {metrics.wealth?.mean_wealth?.toFixed(1) || 0}
                  </div>
                </div>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Gini Coefficient</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {metrics.wealth?.gini_coefficient?.toFixed(3) || 0}
                  </div>
                </div>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Top 10% Share</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {((metrics.wealth?.top_10_percent_share || 0) * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            </div>
            
            <div className="stats-card">
              <h3>Trade Network</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Nodes</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {metrics.trade?.num_nodes || 0}
                  </div>
                </div>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Connections</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {metrics.trade?.num_edges || 0}
                  </div>
                </div>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Communities</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {metrics.trade?.num_communities || 0}
                  </div>
                </div>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Avg Clustering</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {(metrics.trade?.avg_clustering || 0).toFixed(3)}
                  </div>
                </div>
              </div>
            </div>
            
            {metrics.groups && metrics.groups.length > 0 && (
              <div className="stats-card">
                <h3>Active Groups</h3>
                <div className="groups-list">
                  {metrics.groups.map((group) => (
                    <div key={group.id} className="group-item">
                      <div>
                        <div className="group-name">{group.name}</div>
                        <div className="group-members">{group.type}</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontWeight: '600', color: '#3a5a3a' }}>{group.memberCount}</div>
                        <div style={{ fontSize: '0.7rem', color: '#7a9a7a' }}>members</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
            
            <div className="stats-card">
              <h3>Specialization</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Avg Specialization</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {(metrics.specialization?.avg_specialization || 0).toFixed(2)}
                  </div>
                </div>
                <div style={{ background: '#fff', padding: '12px', borderRadius: '6px', textAlign: 'center' }}>
                  <div style={{ fontSize: '0.75rem', color: '#7a9a7a', marginBottom: '4px' }}>Diversity Index</div>
                  <div style={{ fontSize: '1.5rem', fontWeight: '600', color: '#3a5a3a' }}>
                    {(metrics.specialization?.diversity_index || 0).toFixed(2)}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default StatsOverlay
