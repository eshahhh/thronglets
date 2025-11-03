# Thronglets

An experiment in emergent economics: LLM-powered agents in a resource-limited world with no hard-coded economic rules.

## Hypothesis

LLM agents placed in resource-limited environments will create markets, currencies, specialization, and institutions through natural language negotiation and planning as a show of emergent behavior.

## What We're Looking For

- Spontaneous adoption of informal currency
- Specialization into labor classes  
- Cooperative firms emerging
- Supply-demand stabilization
- Price convergence patterns
- Wealth inequality & economic cycles

## Quick Start

### Demo Mode (No LLM Required)

```bash
pip install -r requirements.txt
cd server
python demo_server.py
```

Open http://localhost:8000 or run the frontend separately.

### LLM Mode

```bash
cd server
python main.py --agents 12 --llm
```

Make sure to set your API key in `.env`:
```
API_KEY=your_api_key
BASE_URL=your_base_url  # optional
MODEL_NAME=gpt-4o-mini
```

### Frontend (Development)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 in your browser.

## Features

- Real-time 2D visualization with gamified map view
- Named agents
- Agent detail panel with inventory, needs, and reasoning for action
- Events log
- Statistics overlay with charts:
  - Agent type distribution
  - Trade volume over time
  - Wealth inequality (Gini coefficient)
  - Action distribution
  - Trade network metrics
- WebSocket live updates

## About

This project is inspired by the Black Mirror Thronglets episode!