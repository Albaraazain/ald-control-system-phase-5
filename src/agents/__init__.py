"""
Agent package for running the headless service as multiple cooperating agents.

Agents are lightweight asyncio tasks with simple lifecycle managed by the
supervisor. They encapsulate listeners and monitors:

- CommandListenerAgent: subscribes to recipe_commands and polls fallback
- ConnectionMonitorAgent: maintains PLC connectivity and health reporting
"""

