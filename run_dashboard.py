#!/usr/bin/env python3
import sys
import argparse
import threading
import time
import re
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.simulation import run_silently
from core.logging import LiveLogger
from core.logging.live_logger import LogLevel
from core.visualization import (
    TradeNetworkVisualizer,
    WealthPriceDashboard,
    SpecializationClusterMap,
    GovernanceTimeline,
    DashboardServer,
)


class SimulationDashboard:
    def __init__(self, host="127.0.0.1", port=8080, output_dir="output"):
        self.trade_network = TradeNetworkVisualizer()
        self.wealth_dashboard = WealthPriceDashboard()
        self.specialization_map = SpecializationClusterMap()
        self.governance_timeline = GovernanceTimeline()
        self.dashboard_server = DashboardServer(
            trade_network=self.trade_network,
            wealth_dashboard=self.wealth_dashboard,
            specialization_map=self.specialization_map,
            governance_timeline=self.governance_timeline,
            host=host,
            port=port,
        )
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        self.live_logger = LiveLogger(
            enabled=True,
            min_level=LogLevel.INFO,
            output_dir=str(output_path),
        )
        self._running = False
        self._last_snapshot_tick = None

    def start_dashboard(self):
        self.dashboard_server.start(blocking=False)

        def resolved_tick(tick):
            return tick if tick is not None else self.dashboard_server.state.current_tick

        def log_event(tick, agent_id, event_type, message, details=None):
            self.dashboard_server.log_event(
                tick=resolved_tick(tick),
                agent_id=agent_id,
                event_type=event_type,
                message=message,
                details=details or {},
            )

        def update_location_from_details(agent_id, details):
            dest = details.get("dest") or details.get("destination") or details.get("location")
            if dest:
                self.dashboard_server.update_agent(agent_id, location=dest)

        def on_action(level, message, agent_id, tick, extra):
            if not agent_id:
                return

            payload = extra or {}
            payload_type = payload.get("type", "")

            if payload_type == "message":
                content = payload.get("content") or message
                recipient = payload.get("recipient_id") or payload.get("channel") or "broadcast"
                self.dashboard_server.update_agent(agent_id, speech=content[:150])
                log_event(
                    tick,
                    agent_id,
                    "message",
                    content,
                    {
                        "recipient": recipient,
                        "channel": payload.get("channel"),
                    },
                )
                return

            if payload_type == "action_execute":
                action_type = (payload.get("action_type") or "").lower()
                details = payload.get("details") or {}
                if action_type:
                    self.dashboard_server.update_agent(agent_id, action=action_type)
                update_location_from_details(agent_id, details)
                if details.get("inventory"):
                    self.dashboard_server.update_agent(agent_id, inventory=details["inventory"])
                return

            if payload_type == "action_result":
                success = payload.get("success", True)
                log_event(
                    tick,
                    agent_id,
                    "action" if success else "warning",
                    message,
                    {
                        "action": payload.get("action_type"),
                        "success": success,
                        "details": payload.get("message"),
                    },
                )
                return

            action_match = re.search(r'Executing (\w+):', message)
            if action_match:
                action_type = action_match.group(1).lower()
                self.dashboard_server.update_agent(agent_id, action=action_type)
                if 'dest=' in message:
                    dest_match = re.search(r'dest=(\w+)', message)
                    if dest_match:
                        self.dashboard_server.update_agent(agent_id, location=dest_match.group(1))
                return

            if 'Moved from' in message:
                loc_match = re.search(r'to (\w+)', message)
                if loc_match:
                    self.dashboard_server.update_agent(agent_id, location=loc_match.group(1))
                return

            if 'Harvested' in message:
                log_event(tick, agent_id, "harvest", message)

        def on_llm(level, message, agent_id, tick, extra):
            if not agent_id:
                return

            payload = extra or {}
            payload_type = payload.get("type", "")

            if payload_type == "decision":
                decision = payload.get("decision", {})
                reasoning = decision.get("reasoning", "")
                self.dashboard_server.update_agent(agent_id, thinking=reasoning)
                log_event(
                    tick,
                    agent_id,
                    "decision",
                    decision.get("llm_response") or message,
                    {
                        "action": decision.get("action"),
                        "reason": reasoning,
                        "observation": decision.get("observation_summary"),
                    },
                )
                return

            if payload_type == "llm_response":
                reasoning = payload.get("reason") or ""
                action_type = payload.get("action")
                if reasoning:
                    self.dashboard_server.update_agent(agent_id, thinking=reasoning)
                    log_event(
                        tick,
                        agent_id,
                        "decision",
                        message,
                        {
                            "action": action_type,
                            "reason": reasoning,
                            "latency_ms": payload.get("latency_ms"),
                            "tokens": payload.get("tokens"),
                        },
                    )
                return

            if payload_type == "llm_request":
                model = payload.get("model")
                prompt_preview = payload.get("prompt")
                self.dashboard_server.update_agent(
                    agent_id,
                    thinking=f"Requesting decision via {model}" if model else "Requesting decision",
                )
                if prompt_preview:
                    log_event(
                        tick,
                        agent_id,
                        "llm_request",
                        prompt_preview,
                        {"model": model},
                    )
                return

            reason_match = re.search(r'reason=([^)]+)', message)
            if reason_match:
                reason = reason_match.group(1).strip()
                self.dashboard_server.update_agent(agent_id, thinking=reason)
                log_event(tick, agent_id, "decision", message, {"reason": reason})

        def on_trade(level, message, agent_id, tick, extra):
            if not agent_id:
                return

            payload = extra or {}
            payload_type = payload.get("type", "")

            if payload_type == "trade_proposal":
                log_event(
                    tick,
                    agent_id,
                    "trade",
                    message,
                    {
                        "target": payload.get("target"),
                        "offered": payload.get("offered"),
                        "requested": payload.get("requested"),
                        "id": payload.get("id"),
                    },
                )
                return

            if payload_type == "trade_result":
                log_event(
                    tick,
                    agent_id,
                    "trade_result",
                    message,
                    {
                        "with": payload.get("with"),
                        "id": payload.get("id"),
                        "accepted": payload.get("accepted"),
                    },
                )
                return

            log_event(tick, agent_id, "trade", message)

        self.live_logger.add_callback(LogLevel.ACTION, on_action)
        self.live_logger.add_callback(LogLevel.LLM, on_llm)
        self.live_logger.add_callback(LogLevel.TRADE, on_trade)

    def _build_agent_snapshot(self, agent, memory_subsystem):
        memory_summary = ""
        if memory_subsystem:
            try:
                memory_summary = memory_subsystem.get_memory_summary(agent.id, max_short_term=4)
            except Exception:
                memory_summary = ""

        attributes = getattr(agent, "attributes", {}) or {}
        inventory = getattr(agent, "inventory", {}) or {}
        needs = getattr(agent, "needs", {}) or {}
        skills = getattr(agent, "skills", {}) or {}
        reputation = getattr(agent, "reputation", {}) or {}

        return {
            "id": agent.id,
            "name": getattr(agent, "name", agent.id),
            "location": getattr(agent, "location", ""),
            "inventory": dict(inventory),
            "needs": dict(needs),
            "skills": dict(skills),
            "reputation": dict(reputation),
            "attributes": dict(attributes),
            "capacity": getattr(agent, "capacity", 0),
            "memory": memory_summary,
        }

    def _handle_tick_update(self, tick, stats, agent_manager, world_state, memory_subsystem):
        agents = agent_manager.list_agents()
        payload = [
            self._build_agent_snapshot(agent, memory_subsystem)
            for agent in agents
        ]

        self.dashboard_server.sync_agents(
            tick=tick,
            agents=payload,
            stats={
                "actions_executed": getattr(stats, "actions_executed", len(agents)),
                "actions_succeeded": getattr(stats, "actions_succeeded", 0),
                "actions_failed": getattr(stats, "actions_failed", 0),
                "duration_ms": getattr(stats, "duration_ms", 0.0),
            },
        )
        self.dashboard_server.update_state(
            tick=tick,
            is_running=True,
            agents=len(agents),
            trades=self.dashboard_server.state.total_trades,
        )
        self._last_snapshot_tick = tick

    def run_simulation(self, ticks=100, agents=10, use_llm=False, output_dir="output", config_dir=None):
        self.live_logger.log_system("Dashboard Simulation Starting")
        self._running = True
        self.dashboard_server.update_state(tick=0, is_running=True, agents=agents)
        result = run_silently(
            config_dir=config_dir,
            output_dir=output_dir,
            num_ticks=ticks,
            agent_count=agents,
            use_llm=use_llm,
            live_logger=self.live_logger,
            tick_observer=self._handle_tick_update,
        )
        self.dashboard_server.update_state(
            tick=result.final_tick,
            is_running=False,
            agents=result.metrics.get("agent_count", 0),
        )
        self.live_logger.log_system("Simulation Complete")
        return result

    def stop(self):
        self._running = False
        self.dashboard_server.stop()


def main():
    parser = argparse.ArgumentParser(
        description="Run Thronglets with live dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_dashboard.py --ticks 100 --agents 10
    python run_dashboard.py --llm --ticks 50
    python run_dashboard.py --port 3000 --no-browser
        """
    )
    parser.add_argument("--ticks", type=int, default=100, help="Number of ticks to run")
    parser.add_argument("--agents", type=int, default=10, help="Number of agents")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Dashboard host")
    parser.add_argument("--port", type=int, default=8080, help="Dashboard port")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    parser.add_argument("--config-dir", type=str, default=None, help="Config directory")
    parser.add_argument("--llm", action="store_true", help="Use LLM-powered agents")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")

    args = parser.parse_args()

    dashboard = SimulationDashboard(host=args.host, port=args.port, output_dir=args.output_dir)
    dashboard.start_dashboard()

    if not args.no_browser:
        try:
            import subprocess
            url = f"http://{args.host}:{args.port}"
            subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except:
            pass

    print(f"\n{'='*60}")
    print(f"Dashboard: http://{args.host}:{args.port}")
    print(f"Simulation: {args.ticks} ticks, {args.agents} agents")
    print(f"LLM Mode: {'ON' if args.llm else 'OFF'}")
    print(f"{'='*60}\n")

    try:
        dashboard.run_simulation(
            ticks=args.ticks,
            agents=args.agents,
            use_llm=args.llm,
            output_dir=args.output_dir,
            config_dir=args.config_dir,
        )

        print("\nSimulation complete. Dashboard still running.")
        print("   Press Ctrl+C to exit.\n")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n\nShutting down...")
        dashboard.stop()
        print("Done.")


if __name__ == "__main__":
    main()
