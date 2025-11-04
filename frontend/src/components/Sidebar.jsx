import { useState } from 'react'
import { X } from 'lucide-react'

const RESOURCE_ICONS = {
  wood: '🪵',
  wheat: '🌾',
  fish: '🐟',
  stone: '🪨',
  ore: '⛏️',
  berries: '🫐',
  water: '💧',
  herbs: '🌿',
  clay: '🧱',
  gems: '💎',
  salt: '🧂',
  bread: '🍞',
  default: '📦',
}

function Sidebar({ selectedAgent, events, metrics, onAgentDeselect }) {
  const [activeTab, setActiveTab] = useState('overview')
  
  return (
    <div className="sidebar">
      <div className="sidebar-tabs">
        <button
          className={`sidebar-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          Metrics
        </button>
        <button
          className={`sidebar-tab ${activeTab === 'events' ? 'active' : ''}`}
          onClick={() => setActiveTab('events')}
        >
          Events
        </button>
        <button
          className={`sidebar-tab ${activeTab === 'agent' ? 'active' : ''}`}
          onClick={() => setActiveTab('agent')}
        >
          Agent
        </button>
      </div>
      
      <div className="sidebar-content">
        {activeTab === 'overview' && (
          <OverviewPanel metrics={metrics} />
        )}
        
        {activeTab === 'events' && (
          <EventsPanel events={events} />
        )}
        
        {activeTab === 'agent' && (
          <AgentPanel
            agent={selectedAgent}
            onDeselect={onAgentDeselect}
          />
        )}
      </div>
    </div>
  )
}

function AgentPanel({ agent, onDeselect }) {
  if (!agent) {
    return (
      <div className="panel">
        <p style={{ textAlign: 'center', color: '#7a9a7a' }}>
          Click on an agent to view details
        </p>
      </div>
    )
  }
  
  return (
    <>
      <div className="panel">
        <div className="sidebar-header" style={{ padding: 0, borderBottom: 'none', marginBottom: '8px' }}>
          <h2 style={{ fontSize: '1.1rem' }}>{agent.name}</h2>
          <button className="btn btn-icon" onClick={onDeselect}>
            <X size={14} />
          </button>
        </div>
        
        <div className="stat-row">
          <span className="stat-label">Type</span>
          <span className="stat-value" style={{ textTransform: 'capitalize' }}>
            {agent.type || 'Unknown'}
          </span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Location</span>
          <span className="stat-value">{agent.location}</span>
        </div>
      </div>
      
      <div className="panel">
        <div className="panel-header">Needs</div>
        {Object.entries(agent.needs || {}).map(([need, value]) => (
          <NeedBar key={need} name={need} value={value} />
        ))}
      </div>
      
      <div className="panel">
        <div className="panel-header">Inventory ({Object.values(agent.inventory || {}).reduce((a, b) => a + b, 0)}/{agent.capacity})</div>
        <div className="inventory-grid">
          {Object.entries(agent.inventory || {}).map(([item, count]) => (
            <div key={item} className="inventory-item">
              <div className="inventory-item-icon">
                {RESOURCE_ICONS[item] || RESOURCE_ICONS.default}
              </div>
              <div className="inventory-item-count">{count}</div>
            </div>
          ))}
          {Object.keys(agent.inventory || {}).length === 0 && (
            <div style={{ gridColumn: '1 / -1', textAlign: 'center', color: '#7a9a7a', fontSize: '0.8rem' }}>
              Empty
            </div>
          )}
        </div>
      </div>
      
      {agent.lastAction && (
        <div className="panel">
          <div className="panel-header">Last Action</div>
          <div className="stat-row">
            <span className="stat-label">Type</span>
            <span className={`event-action ${agent.lastAction.action_type}`}>
              {agent.lastAction.action_type}
            </span>
          </div>
          {agent.lastAction.message && (
            <div style={{ fontSize: '0.8rem', color: '#5a7a5a', marginTop: '4px' }}>
              {agent.lastAction.message}
            </div>
          )}
        </div>
      )}
      
      {agent.reasoning && (
        <div className="panel">
          <div className="panel-header">Reasoning</div>
          <div style={{ fontSize: '0.8rem', color: '#5a7a5a', fontStyle: 'italic' }}>
            {agent.reasoning}
          </div>
        </div>
      )}
    </>
  )
}

function NeedBar({ name, value }) {
  const getColor = (val) => {
    if (val > 70) return '#5a8a5a'
    if (val > 40) return '#b8a83a'
    return '#b85a5a'
  }
  
  return (
    <div className="need-bar-container">
      <div className="need-bar-label">
        <span style={{ textTransform: 'capitalize' }}>{name}</span>
        <span>{Math.round(value)}%</span>
      </div>
      <div className="need-bar">
        <div
          className="need-bar-fill"
          style={{
            width: `${value}%`,
            backgroundColor: getColor(value),
          }}
        />
      </div>
    </div>
  )
}

function EventsPanel({ events }) {
  const recentEvents = events.slice(-100).reverse()
  
  return (
    <div 
      className="event-list events-full-height"
    >
      {recentEvents.length === 0 ? (
        <div style={{ textAlign: 'center', color: '#7a9a7a', padding: '20px' }}>
          No events yet
        </div>
      ) : (
        recentEvents.map((event, idx) => (
          <div key={idx} className="event-item">
            <div className="event-header">
              <span className="event-agent">{event.agent_name || event.agent_id}</span>
              <span className="event-tick">T{event.tick}</span>
            </div>
            <div>
              <span className={`event-action ${event.type}`}>{event.type}</span>
              <span className="event-message">
                {event.success ? event.message : `Failed: ${event.message}`}
              </span>
            </div>
            {event.reasoning && (
              <div className="event-reasoning">
                {event.reasoning}
              </div>
            )}
          </div>
        ))
      )}
    </div>
  )
}

function OverviewPanel({ metrics }) {
  if (!metrics) {
    return (
      <div className="panel">
        <p style={{ textAlign: 'center', color: '#7a9a7a' }}>
          Waiting for simulation data...
        </p>
      </div>
    )
  }
  
  return (
    <>
      <div className="panel">
        <div className="panel-header">Simulation Status</div>
        <div className="stat-row">
          <span className="stat-label">Current Tick</span>
          <span className="stat-value">{metrics.tick || 0}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Active Agents</span>
          <span className="stat-value">{metrics.agentCount || 0}</span>
        </div>
      </div>
      
      <div className="panel">
        <div className="panel-header">Agent Distribution</div>
        {Object.entries(metrics.agentTypes || {}).map(([type, count]) => (
          <div key={type} className="stat-row">
            <span className="stat-label" style={{ textTransform: 'capitalize' }}>{type}</span>
            <span className="stat-value">{count}</span>
          </div>
        ))}
        {Object.keys(metrics.agentTypes || {}).length === 0 && (
          <div style={{ color: '#7a9a7a', fontSize: '0.8rem' }}>No data yet</div>
        )}
      </div>
      
      <div className="panel">
        <div className="panel-header">Economy</div>
        <div className="stat-row">
          <span className="stat-label">Total Wealth</span>
          <span className="stat-value">{metrics.wealth?.total_wealth?.toFixed(0) || 0}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Mean Wealth</span>
          <span className="stat-value">{metrics.wealth?.mean_wealth?.toFixed(1) || 0}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Gini Coefficient</span>
          <span className="stat-value">{metrics.wealth?.gini_coefficient?.toFixed(3) || '0.000'}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Top 10% Share</span>
          <span className="stat-value">{((metrics.wealth?.top_10_percent_share || 0) * 100).toFixed(1)}%</span>
        </div>
      </div>
      
      <div className="panel">
        <div className="panel-header">Trade Network</div>
        <div className="stat-row">
          <span className="stat-label">Active Traders</span>
          <span className="stat-value">{metrics.trade?.num_nodes || 0}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Trade Connections</span>
          <span className="stat-value">{metrics.trade?.num_edges || 0}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Trade Communities</span>
          <span className="stat-value">{metrics.trade?.num_communities || 0}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Clustering</span>
          <span className="stat-value">{(metrics.trade?.avg_clustering || 0).toFixed(3)}</span>
        </div>
      </div>
      
      <div className="panel">
        <div className="panel-header">Specialization</div>
        <div className="stat-row">
          <span className="stat-label">Avg Specialization</span>
          <span className="stat-value">{(metrics.specialization?.avg_specialization || 0).toFixed(2)}</span>
        </div>
        <div className="stat-row">
          <span className="stat-label">Diversity Index</span>
          <span className="stat-value">{(metrics.specialization?.diversity_index || 0).toFixed(2)}</span>
        </div>
      </div>
      
      {metrics.groups && metrics.groups.length > 0 && (
        <div className="panel">
          <div className="panel-header">Active Groups</div>
          {metrics.groups.map((group) => (
            <div key={group.id} className="stat-row">
              <span className="stat-label">{group.name}</span>
              <span className="stat-value">{group.memberCount} members</span>
            </div>
          ))}
        </div>
      )}
    </>
  )
}

export default Sidebar
