"""
RealtimeService centralizes Supabase realtime channel management.

Features:
- Background subscribe with watchdog timeout
- Reconnect with jittered backoff
- Health status exposure for connection_monitor
"""
import asyncio
from typing import Callable, Dict, Optional
from src.log_setup import logger
from src.db import create_async_supabase
from src.connection_monitor import connection_monitor


class RealtimeService:
    def __init__(self, subscribe_timeout_seconds: float = 10.0):
        self._client = None
        self._channels: Dict[str, any] = {}
        self._subscribe_timeout = subscribe_timeout_seconds
        self._lock = asyncio.Lock()
        self._connected = False

    async def _ensure_client(self):
        if self._client is None:
            self._client = await create_async_supabase()
        return self._client

    def is_connected(self) -> bool:
        return self._connected

    async def subscribe_postgres(
        self,
        name: str,
        table: str,
        on_insert: Optional[Callable] = None,
        on_update: Optional[Callable] = None,
        schema: str = "public",
    ) -> None:
        """Create or reuse a channel and subscribe with background timeout."""
        async with self._lock:
            client = await self._ensure_client()
            channel = self._channels.get(name) or client.channel(name)

            if on_insert:
                channel = channel.on_postgres_changes(
                    event="INSERT", schema=schema, table=table, callback=on_insert
                )
            if on_update:
                channel = channel.on_postgres_changes(
                    event="UPDATE", schema=schema, table=table, callback=on_update
                )

            self._channels[name] = channel

            async def _subscribe():
                nonlocal channel
                try:
                    await asyncio.wait_for(channel.subscribe(), timeout=self._subscribe_timeout)
                    self._connected = True
                    connection_monitor.update_realtime_status(True)
                    logger.info(f"RealtimeService: subscribed channel '{name}'")
                except asyncio.TimeoutError:
                    self._connected = False
                    connection_monitor.update_realtime_status(False, "subscribe timeout")
                    logger.warning(f"RealtimeService: subscribe timeout for channel '{name}'")
                except Exception as e:
                    self._connected = False
                    connection_monitor.update_realtime_status(False, str(e))
                    logger.error(f"RealtimeService: subscribe error on '{name}': {e}", exc_info=True)

            asyncio.create_task(_subscribe())

    async def reconnect_all(self):
        """Attempt to reconnect all channels with backoff."""
        async with self._lock:
            if not self._channels:
                return
            client = await self._ensure_client()

            async def _reconnect(name: str, channel: any):
                backoff = 2.0
                for _ in range(5):
                    try:
                        await asyncio.wait_for(channel.subscribe(), timeout=self._subscribe_timeout)
                        self._connected = True
                        connection_monitor.update_realtime_status(True)
                        logger.info(f"RealtimeService: reconnected '{name}'")
                        return
                    except Exception as e:
                        self._connected = False
                        connection_monitor.update_realtime_status(False, str(e))
                        logger.warning(f"RealtimeService: reconnect '{name}' failed: {e}; retry in {backoff:.0f}s")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, 30.0)

            for name, channel in self._channels.items():
                asyncio.create_task(_reconnect(name, channel))


