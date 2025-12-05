import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { BarChart3, BookOpen } from 'lucide-react'
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

function SetupScreen({ onStart, onStartDemo }) {
  const [config, setConfig] = useState(loadCachedConfig)
  const [loading, setLoading] = useState(false)
  const [loadingDemo, setLoadingDemo] = useState(false)
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
  
  const handleStartDemo = async () => {
    setError('')
    setLoadingDemo(true)
    try {
      await onStartDemo()
    } catch (err) {
      setError(err.message || 'Failed to start demo')
      setLoadingDemo(false)
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
              disabled={loading || loadingDemo}
            >
              {loading ? 'Starting...' : 'Start Simulation'}
            </button>
          </div>
          
          <div className="setup-divider">
            <span>or</span>
          </div>
          
          <div className="demo-section">
            <button 
              className="btn btn-demo btn-large" 
              onClick={handleStartDemo}
              disabled={loading || loadingDemo}
            >
              {loadingDemo ? 'Starting Demo...' : 'View Demo'}
            </button>
            <p className="demo-hint">
              <strong>Demo Mode:</strong> Simulates 100 agents for 100 ticks with realistic fake events. 
              No LLM calls will be made.
            </p>
          </div>
          
          <div className="docs-link">
            <Link to="/docs" className="btn btn-link">
              <BookOpen size={16} />
              Read Documentation
            </Link>
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

function SimulationView({ state, metrics, events, connected, demoMode }) {
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [showStats, setShowStats] = useState(false)
  
  const handleAgentSelect = useCallback((agent) => {
    setSelectedAgent(agent)
  }, [])
  
  return (
    <div className="app">
      <header className="header">
        <h1>Thronglets</h1>
        {demoMode && (
          <div className="demo-badge">
            <span>DEMO MODE</span>
            <small>Simulated data - No LLM calls</small>
          </div>
        )}
        
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
          
          <Link to="/docs" className="btn btn-icon" title="Documentation">
            <BookOpen size={16} />
          </Link>
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
  const [demoMode, setDemoMode] = useState(false)
  const [state, setState] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [events, setEvents] = useState([])
  
  const { connected, lastMessage } = useWebSocket('wss://thronglets-server.eshahhh.hackclub.app/ws')
  const api = useApi('https://thronglets-server.eshahhh.hackclub.app')
  
  useEffect(() => {
    if (!lastMessage) return
    
    const handleTickMessage = (data) => {
      const { state: newState, metrics: newMetrics, events: newEvents, demoMode: isDemoMode } = data

      if (newState) {
        setState(newState)
      }

      if (newMetrics) setMetrics(newMetrics)
      if (newEvents) setEvents(newEvents)
      if (isDemoMode !== undefined) setDemoMode(isDemoMode)

      if (newState?.running) {
        setSimulationStarted(true)
      }
    }
    
    const handleStateMessage = (newState) => {
      if (newState) {
        setState(newState)
        if (newState.running) {
          setSimulationStarted(true)
        }
      }
    }
    
    if (lastMessage.type === 'tick') {
      handleTickMessage(lastMessage.data)
    } else if (lastMessage.type === 'state') {
      handleStateMessage(lastMessage.data)
    }
  }, [lastMessage])
  
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
    
    setDemoMode(false)
    setSimulationStarted(true)
  }
  
  const handleStartDemo = async () => {
    await api.post('/api/simulation/demo?agent_count=100&max_ticks=100')
    
    await api.post('/api/simulation/start')
    
    const stateData = await api.get('/api/state')
    setState(stateData)
    const metricsData = await api.get('/api/metrics')
    setMetrics(metricsData)
    
    setDemoMode(true)
    setSimulationStarted(true)
  }
  
  if (!simulationStarted) {
    return (
      <SetupScreen onStart={handleStartSimulation} onStartDemo={handleStartDemo} />
    )
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
      demoMode={demoMode}
    />
  )
}

export default App
