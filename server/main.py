#!/usr/bin/env python3
import os
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

import uvicorn
from dotenv import load_dotenv

load_dotenv()


def main():
    parser = argparse.ArgumentParser(description="Thronglets Simulation Server")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--agents", type=int, default=12, help="Number of agents")
    parser.add_argument("--llm", action="store_true", help="Use LLM-powered agents")
    parser.add_argument("--config-dir", type=str, default=None, help="Config directory")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    
    args = parser.parse_args()
    
    os.environ["THRONGLETS_AGENTS"] = str(args.agents)
    os.environ["THRONGLETS_LLM"] = str(args.llm)
    if args.config_dir:
        os.environ["THRONGLETS_CONFIG_DIR"] = args.config_dir
    os.environ["THRONGLETS_OUTPUT_DIR"] = args.output_dir
    
    print(f"Starting Thronglets Server on http://{args.host}:{args.port}")
    print(f"Mode: {'LLM' if args.llm else 'DEMO'} | Agents: {args.agents}")
    print(f"Frontend: http://localhost:{args.port}")
    print()
    
    uvicorn.run(
        "app:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )


if __name__ == "__main__":
    main()
