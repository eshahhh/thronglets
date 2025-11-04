import { useState, useEffect, useCallback } from 'react'
import { BarChart3 } from 'lucide-react'
import GameMap from './components/GameMap'
import Sidebar from './components/Sidebar'
import StatsOverlay from './components/StatsOverlay'
import { useWebSocket } from './hooks/useWebSocket'
import { useApi } from './hooks/useApi'

const DEFAULT_CONFIG = {
  apiKey: '',
  baseUrl: 'https://ai.hackclub.com/proxy/v1',
  modelName: 'openai/gpt-oss-120b',
  agentCount: 12,
}

const STORAGE_KEY = 'thronglets_config'

function loadCachedConfig() {
  try {
    const cached = localStorage.getItem(STORAGE_KEY)
    if (cached) {
      const parsed = JSON.parse(cached)
      return { ...DEFAULT_CONFIG, ...parsed }
    }
  } catch (e) {
    console.error('Failed to load cached config:', e)
  }
  return DEFAULT_CONFIG
}

function saveCachedConfig(config) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config))
  } catch (e) {
    console.error('Failed to save config:', e)
  }
}

function SetupScreen({ onStart }) {
  const [config, setConfig] = useState(loadCachedConfig)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  
  const handleUseDefaults = () => {
    setConfig({
      ...DEFAULT_CONFIG,
      apiKey: config.apiKey,
    })
  }
  
  const handleStart = async () => {
    if (!config.apiKey.trim()) {
      setError('API Key is required to run the simulation')
      return
    }
    setError('')
    setLoading(true)
    saveCachedConfig(config)
    try {
      await onStart(config)
    } catch (err) {
      setError(err.message || 'Failed to start simulation')
      setLoading(false)
    }
  }
  
  return (
    <div className="setup-screen">
      <div className="setup-container">
        <div className="setup-header">
          <h1>Thronglets</h1>
          <p>Emergent Economics Simulation</p>
        </div>
        
        <div className="setup-form">
          <div className="form-group">
            <label>API Key *</label>
            <input
              type="password"
              value={config.apiKey}
              onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
              placeholder="Enter your API key"
              autoFocus
            />
            <span className="form-hint">Required to run LLM-powered agents</span>
          </div>
          
          <div className="form-group">
            <label>Base URL</label>
            <input
              type="text"
              value={config.baseUrl}
              onChange={(e) => setConfig({ ...config, baseUrl: e.target.value })}
              placeholder="https://ai.hackclub.com/proxy/v1"
            />
          </div>
          
          <div className="form-group">
            <label>Model Name</label>
            <input
              type="text"
              value={config.modelName}
              onChange={(e) => setConfig({ ...config, modelName: e.target.value })}
              placeholder="openai/gpt-oss-120b"
            />
          </div>
          
          <div className="form-group">
            <label>Number of Agents</label>
            <input
              type="number"
              value={config.agentCount}
              onChange={(e) => setConfig({ ...config, agentCount: parseInt(e.target.value) || 12 })}
              min={2}
              max={24}
            />
          </div>
          
          {error && <div className="setup-error">{error}</div>}
          
          <div className="setup-actions">
            <button className="btn btn-secondary" onClick={handleUseDefaults}>
              Use Defaults
            </button>
            <button 
              className="btn btn-primary btn-large" 
              onClick={handleStart}
              disabled={loading}
            >
              {loading ? 'Starting...' : 'Start Simulation'}
            </button>
          </div>
        </div>
        
        <div className="setup-info">
          <h3>About This Experiment</h3>
          <p>
            LLM-powered agents are placed in a resource-limited environment to observe 
            emergent economic behaviors: market formation, currency adoption, specialization, 
            and institutional development through natural language negotiation.
          </p>
        </div>
      </div>
    </div>
  )
}

function SimulationView({ state, metrics, events, connected }) {
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [showStats, setShowStats] = useState(false)
  
  const handleAgentSelect = useCallback((agent) => {
    setSelectedAgent(agent)
  }, [])
  
  return (
    <div className="app">
      <header className="header">
        <h1>Thronglets</h1>
        
        <div className="header-controls">
          <div className="header-stats">
            <div className="header-stat">
              <span>Tick:</span>
              <strong>{state.tick}</strong>
            </div>
            <div className="header-stat">
              <span>Agents:</span>
              <strong>{state.agents?.length || 0}</strong>
            </div>
            <div className="header-stat">
              <span className={state.running ? 'status-running' : 'status-stopped'}>
                {state.running ? 'Running' : 'Stopped'}
              </span>
            </div>
            <div className="header-stat">
              <span className={connected ? 'status-connected' : 'status-disconnected'}>
                {connected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
          </div>
          
          <button className="btn btn-icon" onClick={() => setShowStats(true)} title="Statistics">
            <BarChart3 size={16} />
          </button>
        </div>
      </header>
      
      <main className="main-content">
        <GameMap
          agents={state.agents || []}
          locations={state.locations || []}
          selectedAgent={selectedAgent}
          onAgentSelect={handleAgentSelect}
        />
        
        <Sidebar
          selectedAgent={selectedAgent}
          events={events}
          metrics={metrics}
          onAgentDeselect={() => setSelectedAgent(null)}
        />
      </main>
      
      {showStats && (
        <StatsOverlay
          metrics={metrics}
          events={events}
          onClose={() => setShowStats(false)}
        />
      )}
    </div>
  )
}

function App() {
  const [simulationStarted, setSimulationStarted] = useState(false)
  const [state, setState] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [events, setEvents] = useState([])
  
  const { connected, lastMessage } = useWebSocket('ws://localhost:8000/ws')
  const api = useApi('http://localhost:8000')
  
  useEffect(() => {
    if (!lastMessage) return
    
    if (lastMessage.type === 'tick') {
      const { state: newState, metrics: newMetrics, events: newEvents } = lastMessage.data
      setState(newState)
      if (newMetrics) setMetrics(newMetrics)
      if (newEvents) setEvents(newEvents)
      if (!simulationStarted && newState?.running) {
        setSimulationStarted(true)
      }
    } else if (lastMessage.type === 'state') {
      setState(lastMessage.data)
      if (!simulationStarted && lastMessage.data.running) {
        setSimulationStarted(true)
      }
    }
  }, [lastMessage, simulationStarted])
  
  const handleStartSimulation = async (config) => {
    const params = new URLSearchParams()
    params.append('api_key', config.apiKey)
    params.append('base_url', config.baseUrl)
    params.append('model_name', config.modelName)
    await api.post(`/api/config?${params.toString()}`)
    
    await api.post(`/api/simulation/initialize?agent_count=${config.agentCount}`)
    
    await api.post('/api/simulation/start')
    
    const stateData = await api.get('/api/state')
    setState(stateData)
    const metricsData = await api.get('/api/metrics')
    setMetrics(metricsData)
    
    setSimulationStarted(true)
  }
  
  if (!simulationStarted) {
    return <SetupScreen onStart={handleStartSimulation} />
  }
  
  if (!state) {
    return (
      <div className="app">
        <div className="loading">Connecting to simulation...</div>
      </div>
    )
  }
  
  return (
    <SimulationView
      state={state}
      metrics={metrics}
      events={events}
      connected={connected}
    />
  )
}

export default App
