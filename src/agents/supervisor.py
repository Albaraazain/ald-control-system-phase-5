"""
Agent supervisor to run core service components as separate asyncio agents.

This keeps the service headless while making roles explicit and restartable.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, List, Optional

from src.log_setup import logger
from src.command_flow.listener import setup_command_listener
from src.connection_monitor import connection_monitor
from src.parameter_control_listener import setup_parameter_control_listener


# Type alias for an async callable factory returning a long-lived task
AgentFactory = Callable[[], Awaitable[None]]


@dataclass
class Agent:
    name: str
    factory: AgentFactory


class AgentSupervisor:
    """Runs multiple agents and restarts them if they unexpectedly exit."""

    def __init__(self, agents: List[Agent]) -> None:
        self._agents = agents
        self._tasks: Dict[str, asyncio.Task] = {}
        self._stopping = asyncio.Event()

    async def _run_agent(self, name: str, factory: AgentFactory) -> None:
        backoff = 1.0
        max_backoff = 30.0
        while not self._stopping.is_set():
            try:
                logger.info(f"[agent:{name}] starting")
                await factory()  # should be long-lived / await forever
                if self._stopping.is_set():
                    break
                logger.warning(f"[agent:{name}] exited unexpectedly; restarting in {backoff:.0f}s")
            except asyncio.CancelledError:
                logger.info(f"[agent:{name}] cancelled")
                raise
            except Exception as e:
                logger.exception(f"[agent:{name}] crashed: {e}")

            await asyncio.sleep(backoff)
            backoff = min(max_backoff, backoff * 2)

    async def start(self) -> None:
        for agent in self._agents:
            task = asyncio.create_task(self._run_agent(agent.name, agent.factory), name=f"agent:{agent.name}")
            self._tasks[agent.name] = task
        logger.info(f"Started {len(self._tasks)} agents: {', '.join(self._tasks.keys())}")

    async def stop(self) -> None:
        self._stopping.set()
        for name, task in self._tasks.items():
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        logger.info("All agents stopped")


def make_command_listener_agent(async_supabase) -> Agent:
    async def run() -> None:
        # Set up listener and keep the agent alive
        await setup_command_listener(async_supabase)
        # setup_command_listener spawns background polling; we park here
        await asyncio.Event().wait()

    return Agent(name="command-listener", factory=run)


def make_connection_monitor_agent() -> Agent:
    async def run() -> None:
        await connection_monitor.start_monitoring()
        await asyncio.Event().wait()

    return Agent(name="connection-monitor", factory=run)


def make_parameter_control_listener_agent(async_supabase) -> Agent:
    async def run() -> None:
        await setup_parameter_control_listener(async_supabase)
        await asyncio.Event().wait()

    return Agent(name="parameter-control-listener", factory=run)
