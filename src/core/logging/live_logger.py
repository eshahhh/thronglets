import sys
import time
import json
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
import threading


class LogLevel(Enum):
    DEBUG = auto()
    INFO = auto()
    ACTION = auto()
    LLM = auto()
    TRADE = auto()
    GOVERNANCE = auto()
    METRIC = auto()
    WARNING = auto()
    ERROR = auto()


class LogColors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"


class LiveLogger:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(
        self,
        enabled=True,
        min_level=LogLevel.INFO,
        show_timestamps=True,
        show_colors=True,
        log_file=None,
        output_dir=None,
    ):
        if self._initialized:
            if output_dir and not self._file_handle:
                self._setup_file_logging(output_dir)
            return
            
        self.enabled = enabled
        self.min_level = min_level
        self.show_timestamps = show_timestamps
        self.show_colors = show_colors
        self.log_file = log_file
        self._file_handle = None
        self._jsonl_handle = None
        self._callbacks = {level: [] for level in LogLevel}
        self._stats = {
            "total_logs": 0,
            "llm_calls": 0,
            "actions": 0,
            "trades": 0,
            "errors": 0,
        }
        self._start_time = time.time()
        self._full_logs = []
        self._initialized = True
        
        if log_file:
            self._file_handle = open(log_file, "a", encoding="utf-8")
        
        if output_dir:
            self._setup_file_logging(output_dir)
    
    def _setup_file_logging(self, output_dir):
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if not self._file_handle:
            log_file = output_path / f"simulation_{timestamp}.log"
            self._file_handle = open(log_file, "w", encoding="utf-8")
        
        jsonl_file = output_path / f"full_log_{timestamp}.jsonl"
        self._jsonl_handle = open(jsonl_file, "w", encoding="utf-8")
    
    def _get_level_style(self, level):
        c = LogColors
        styles = {
            LogLevel.DEBUG: (c.DIM + c.WHITE, "DBG"),
            LogLevel.INFO: (c.CYAN, "INF"),
            LogLevel.ACTION: (c.GREEN, "ACT"),
            LogLevel.LLM: (c.MAGENTA, "LLM"),
            LogLevel.TRADE: (c.YELLOW, "TRD"),
            LogLevel.GOVERNANCE: (c.BLUE, "GOV"),
            LogLevel.METRIC: (c.CYAN + c.BOLD, "MET"),
            LogLevel.WARNING: (c.YELLOW + c.BOLD, "WRN"),
            LogLevel.ERROR: (c.RED + c.BOLD, "ERR"),
        }
        return styles.get(level, (c.WHITE, "???"))
    
    def _format_timestamp(self):
        elapsed = time.time() - self._start_time
        return f"[{elapsed:8.2f}s]"
    
    def _format_message(
        self,
        level,
        message,
        agent_id=None,
        tick=None,
        extra=None,
    ):
        c = LogColors
        color, label = self._get_level_style(level)
        
        parts = []
        
        if self.show_timestamps:
            ts = self._format_timestamp()
            if self.show_colors:
                parts.append(f"{c.DIM}{ts}{c.RESET}")
            else:
                parts.append(ts)
        
        if self.show_colors:
            parts.append(f"{color}[{label}]{c.RESET}")
        else:
            parts.append(f"[{label}]")
        
        if tick is not None:
            if self.show_colors:
                parts.append(f"{c.DIM}T{tick:04d}{c.RESET}")
            else:
                parts.append(f"T{tick:04d}")
        
        if agent_id:
            if self.show_colors:
                parts.append(f"{c.BOLD}{agent_id}{c.RESET}")
            else:
                parts.append(agent_id)
        
        parts.append(message)
        
        if extra:
            extra_str = " ".join(f"{k}={v}" for k, v in extra.items())
            if self.show_colors:
                parts.append(f"{c.DIM}({extra_str}){c.RESET}")
            else:
                parts.append(f"({extra_str})")
        
        return " ".join(parts)
    
    def log(
        self,
        level,
        message,
        agent_id=None,
        tick=None,
        extra=None,
    ):
        if not self.enabled:
            return
        if level.value < self.min_level.value:
            return
        
        self._stats["total_logs"] += 1
        
        formatted = self._format_message(level, message, agent_id, tick, extra)
        
        print(formatted, file=sys.stderr, flush=True)
        
        if self._file_handle:
            plain = self._strip_colors(self._format_message(level, message, agent_id, tick, extra))
            self._file_handle.write(plain + "\n")
            self._file_handle.flush()
        
        if self._jsonl_handle:
            log_entry = {
                "timestamp": datetime.now().isoformat(),
                "elapsed_s": time.time() - self._start_time,
                "level": level.name,
                "message": message,
                "agent_id": agent_id,
                "tick": tick,
                "extra": extra,
            }
            self._jsonl_handle.write(json.dumps(log_entry) + "\n")
            self._jsonl_handle.flush()
        
        for callback in self._callbacks.get(level, []):
            try:
                callback(level, message, agent_id, tick, extra)
            except Exception:
                pass
    
    def _strip_colors(self, text):
        for code in ["\033[0m", "\033[1m", "\033[2m", "\033[30m", "\033[31m", 
                     "\033[32m", "\033[33m", "\033[34m", "\033[35m", "\033[36m", "\033[37m",
                     "\033[40m", "\033[41m", "\033[42m", "\033[43m", "\033[44m", 
                     "\033[45m", "\033[46m", "\033[47m"]:
            text = text.replace(code, "")
        return text
    
    def debug(self, message, **kwargs):
        self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message, **kwargs):
        self.log(LogLevel.INFO, message, **kwargs)
    
    def action(self, message, **kwargs):
        self._stats["actions"] += 1
        self.log(LogLevel.ACTION, message, **kwargs)
    
    def llm(self, message, **kwargs):
        self._stats["llm_calls"] += 1
        self.log(LogLevel.LLM, message, **kwargs)
    
    def trade(self, message, **kwargs):
        self._stats["trades"] += 1
        self.log(LogLevel.TRADE, message, **kwargs)
    
    def governance(self, message, **kwargs):
        self.log(LogLevel.GOVERNANCE, message, **kwargs)
    
    def metric(self, message, **kwargs):
        self.log(LogLevel.METRIC, message, **kwargs)
    
    def system(self, message, **kwargs):
        self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message, **kwargs):
        self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message, **kwargs):
        self._stats["errors"] += 1
        self.log(LogLevel.ERROR, message, **kwargs)
    
    def log_llm_request(
        self,
        agent_id,
        tick,
        model_name,
        prompt_preview="",
    ):
        preview = prompt_preview[:80] + "..." if len(prompt_preview) > 80 else prompt_preview
        self.llm(
            "Requesting decision",
            agent_id=agent_id,
            tick=tick,
            extra={
                "type": "llm_request",
                "model": model_name,
                "prompt": preview,
            }
        )
    
    def log_llm_response(
        self,
        agent_id,
        tick,
        success,
        latency_ms,
        tokens,
        action_type=None,
        reasoning="",
        error=None,
    ):
        if success:
            reason_preview = reasoning[:60] + "..." if len(reasoning) > 60 else reasoning
            self.llm(
                f"Response: {action_type or 'UNKNOWN'}",
                agent_id=agent_id,
                tick=tick,
                extra={
                    "type": "llm_response",
                    "latency_ms": latency_ms,
                    "tokens": tokens,
                    "reason": reasoning,
                    "reason_preview": reason_preview,
                    "action": action_type,
                }
            )
        else:
            self.error(
                f"LLM failed: {error}",
                agent_id=agent_id,
                tick=tick,
                extra={
                    "type": "llm_error",
                    "latency_ms": latency_ms,
                    "tokens": tokens,
                    "action": action_type,
                    "error": error,
                }
            )
    
    def log_action_execute(
        self,
        agent_id,
        tick,
        action_type,
        details,
    ):
        details = details or {}
        detail_str = ", ".join(f"{k}={v}" for k, v in list(details.items())[:3])
        self.action(
            f"Executing {action_type}: {detail_str}",
            agent_id=agent_id,
            tick=tick,
            extra={
                "type": "action_execute",
                "action_type": action_type,
                "details": details,
            }
        )
    
    def log_action_result(
        self,
        agent_id,
        tick,
        action_type,
        success,
        message,
    ):
        status = "OK" if success else "FAIL"
        level = LogLevel.ACTION if success else LogLevel.WARNING
        self.log(
            level,
            f"{status} {action_type}: {message}",
            agent_id=agent_id,
            tick=tick,
            extra={
                "type": "action_result",
                "action_type": action_type,
                "success": success,
                "message": message,
            }
        )
    
    def log_trade_proposal(
        self,
        proposer_id,
        target_id,
        tick,
        offered,
        requested,
        proposal_id,
    ):
        offered_str = ", ".join(f"{q}x{t}" for t, q in offered[:3])
        requested_str = ", ".join(f"{q}x{t}" for t, q in requested[:3])
        self.trade(
            f"Proposing: [{offered_str}] <-> [{requested_str}]",
            agent_id=proposer_id,
            tick=tick,
            extra={
                "type": "trade_proposal",
                "target": target_id,
                "id": proposal_id[:8],
                "offered": offered,
                "requested": requested,
            }
        )
    
    def log_trade_complete(
        self,
        proposer_id,
        target_id,
        tick,
        accepted,
        proposal_id,
    ):
        status = "ACCEPTED" if accepted else "REJECTED"
        self.trade(
            f"{status}",
            agent_id=proposer_id,
            tick=tick,
            extra={
                "type": "trade_result",
                "with": target_id,
                "id": proposal_id[:8],
                "accepted": accepted,
            }
        )
    
    def log_tick_start(self, tick, agent_count):
        self.info(
            "═══════════════════════════════════════",
            tick=tick,
        )
        self.info(
            f"TICK START - {agent_count} agents",
            tick=tick,
        )
    
    def log_tick_end(
        self,
        tick,
        duration_ms,
        actions_executed,
        actions_succeeded,
    ):
        success_rate = (actions_succeeded / actions_executed * 100) if actions_executed > 0 else 0
        self.info(
            f"TICK END - {duration_ms:.1f}ms, {actions_executed} actions ({success_rate:.0f}% success)",
            tick=tick,
        )
    
    def log_system(self, message):
        self.info(message)
    
    def log_simulation_start(self, agent_count, max_ticks):
        self.info("")
        self.info("╔══════════════════════════════════════════════════════════╗")
        self.info("║          THRONGLETS SIMULATION STARTING                  ║")
        self.info("╠══════════════════════════════════════════════════════════╣")
        self.info(f"║  Agents: {agent_count:<10} Max Ticks: {max_ticks:<15}      ║")
        self.info("╚══════════════════════════════════════════════════════════╝")
        self.info("")
    
    def log_simulation_end(self, total_ticks, duration_ms):
        self.info("")
        self.info("╔══════════════════════════════════════════════════════════╗")
        self.info("║          SIMULATION COMPLETE                             ║")
        self.info("╠══════════════════════════════════════════════════════════╣")
        self.info(f"║  Ticks: {total_ticks:<10} Duration: {duration_ms/1000:.1f}s                   ║")
        self.info(f"║  LLM Calls: {self._stats['llm_calls']:<8} Actions: {self._stats['actions']:<10}     ║")
        self.info(f"║  Trades: {self._stats['trades']:<10} Errors: {self._stats['errors']:<10}       ║")
        self.info("╚══════════════════════════════════════════════════════════╝")
    
    def log_governance_action(
        self,
        agent_id,
        tick,
        action_type,
        group_id=None,
        details=None,
    ):
        self.governance(
            f"{action_type}",
            agent_id=agent_id,
            tick=tick,
            extra={
                "type": "governance",
                "group": group_id,
                **(details or {}),
            }
        )
    
    def log_metric(
        self,
        metric_name,
        value,
        tick=None,
    ):
        self.metric(
            f"{metric_name}: {value}",
            tick=tick,
        )
    
    def add_callback(self, level, callback):
        self._callbacks[level].append(callback)
    
    def remove_callback(self, level, callback):
        if callback in self._callbacks[level]:
            self._callbacks[level].remove(callback)
    
    def get_stats(self):
        return dict(self._stats)
    
    def reset_stats(self):
        self._stats = {
            "total_logs": 0,
            "llm_calls": 0,
            "actions": 0,
            "trades": 0,
            "errors": 0,
        }
        self._start_time = time.time()
    
    def set_enabled(self, enabled):
        self.enabled = enabled
    
    def set_level(self, level):
        self.min_level = level
    
    def close(self):
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None
        if self._jsonl_handle:
            self._jsonl_handle.close()
            self._jsonl_handle = None
    
    def log_agent_decision(
        self,
        agent_id,
        tick,
        observation_summary,
        llm_response,
        chosen_action,
        reasoning,
    ):
        self.llm(
            f"DECISION: {chosen_action}",
            agent_id=agent_id,
            tick=tick,
            extra={
                "type": "decision",
                "decision": {
                    "action": chosen_action,
                    "reasoning": reasoning,
                    "observation_summary": observation_summary,
                    "llm_response": llm_response,
                },
            }
        )
        if reasoning:
            self.debug(f"Reasoning: {reasoning}", agent_id=agent_id, tick=tick)
        
        if self._jsonl_handle:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "agent_decision",
                "tick": tick,
                "agent_id": agent_id,
                "observation_summary": observation_summary,
                "llm_response": llm_response,
                "chosen_action": chosen_action,
                "reasoning": reasoning,
            }
            self._jsonl_handle.write(json.dumps(entry) + "\n")
            self._jsonl_handle.flush()
    
    def log_full_llm_exchange(
        self,
        agent_id,
        tick,
        system_prompt,
        user_prompt,
        raw_response,
        parsed_action=None,
        latency_ms=0.0,
        tokens=0,
    ):
        if self._jsonl_handle:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "llm_exchange",
                "tick": tick,
                "agent_id": agent_id,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "raw_response": raw_response,
                "parsed_action": parsed_action,
                "latency_ms": latency_ms,
                "tokens": tokens,
            }
            self._jsonl_handle.write(json.dumps(entry) + "\n")
            self._jsonl_handle.flush()
    
    def log_message_sent(
        self,
        agent_id,
        tick,
        recipient_id,
        channel,
        content,
    ):
        target = recipient_id or f"[{channel}]"
        preview = content[:100] + "..." if len(content) > 100 else content
        self.action(
            f"MESSAGE -> {target}: {preview}",
            agent_id=agent_id,
            tick=tick,
            extra={
                "type": "message",
                "channel": channel,
                "recipient_id": recipient_id,
                "content": content,
            }
        )
        
        if self._jsonl_handle:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "type": "message",
                "tick": tick,
                "agent_id": agent_id,
                "recipient_id": recipient_id,
                "channel": channel,
                "content": content,
            }
            self._jsonl_handle.write(json.dumps(entry) + "\n")
            self._jsonl_handle.flush()


def get_live_logger():
    return LiveLogger()
