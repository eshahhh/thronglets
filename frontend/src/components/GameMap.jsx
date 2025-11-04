import { useState, useEffect, useRef } from 'react'

const LOCATION_ICONS = {
  forest: '🌲',
  river: '🌊',
  mountain: '🏔️',
  plains: '🌾',
  settlement: '🏘️',
  cave: '🕳️',
  coast: '🏖️',
  lake: '🌀',
  market: '🏪',
  meadow: '🌻',
  default: '📍',
}

const AGENT_TYPE_COLORS = {
  farmer: '#4a7c4a',
  trader: '#c9a227',
  crafter: '#a0522d',
  gatherer: '#2e8b57',
  leader: '#4169e1',
  specialist: '#8a2be2',
  cooperator: '#20b2aa',
  opportunist: '#cd5c5c',
  generalist: '#708090',
}

const AGENT_TYPE_ICONS = {
  farmer: '🧑‍🌾',
  trader: '🧑‍💼',
  crafter: '🧑‍🔧',
  gatherer: '🧑‍🎤',
  leader: '👑',
  specialist: '🔬',
  cooperator: '🤝',
  opportunist: '🎭',
  generalist: '🧑',
}

function GameMap({ agents, locations, selectedAgent, onAgentSelect }) {
  const [agentPositions, setAgentPositions] = useState({})
  const prevPositionsRef = useRef({})
  
  useEffect(() => {
    const newPositions = {}
    agents.forEach(agent => {
      newPositions[agent.id] = { x: agent.x, y: agent.y, location: agent.location }
    })
    
    const prevPositions = prevPositionsRef.current
    const hasChanges = agents.some(agent => {
      const prev = prevPositions[agent.id]
      return !prev || prev.location !== agent.location
    })
    
    if (hasChanges) {
      prevPositionsRef.current = newPositions
    }
    
    setAgentPositions(newPositions)
  }, [agents])
  
  return (
    <div className="map-container">
      <div className="map-canvas">
        <div className="grass-pattern" />
        
        {locations.map((location) => (
          <div
            key={location.id}
            className="location"
            style={{
              left: location.x,
              top: location.y,
            }}
          >
            <div className="location-node">
              {LOCATION_ICONS[location.type] || LOCATION_ICONS.default}
            </div>
            <div className="location-label">{location.name}</div>
          </div>
        ))}
        
        {agents.map((agent) => {
          const isSelected = selectedAgent?.id === agent.id
          const typeColor = AGENT_TYPE_COLORS[agent.type] || AGENT_TYPE_COLORS.generalist
          const typeIcon = AGENT_TYPE_ICONS[agent.type] || AGENT_TYPE_ICONS.generalist
          const shortName = agent.rawName || agent.name.split(' ')[0]
          const isMoving = agent.lastAction?.action_type === 'MOVE'
          
          return (
            <div
              key={agent.id}
              className={`agent ${isSelected ? 'agent-selected' : ''} ${isMoving ? 'agent-moving' : ''}`}
              style={{
                left: agent.x,
                top: agent.y,
                transition: 'left 0.8s ease-in-out, top 0.8s ease-in-out',
              }}
              onClick={() => onAgentSelect(agent)}
            >
              <div
                className="agent-sprite"
                style={{ 
                  borderColor: typeColor,
                  backgroundColor: `${typeColor}22`,
                }}
              >
                {typeIcon}
              </div>
              {agent.lastAction?.action_type && (
                <div className="agent-action-indicator">
                  {agent.lastAction.action_type === 'MOVE' ? '👟' :
                   agent.lastAction.action_type === 'HARVEST' ? '⛏️' :
                   agent.lastAction.action_type === 'CRAFT' ? '🔧' :
                   agent.lastAction.action_type === 'MESSAGE' ? '💬' :
                   agent.lastAction.action_type === 'TRADE_PROPOSAL' ? '💱' :
                   agent.lastAction.action_type === 'CONSUME' ? '🍽️' : '💤'}
                </div>
              )}
              <div className="agent-label">{shortName}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default GameMap
