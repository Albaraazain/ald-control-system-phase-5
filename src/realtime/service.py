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
        self._monitor_task: Optional[asyncio.Task] = None

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

    async def _monitor_loop(self):
        """Periodically check and attempt reconnection when disconnected."""
        try:
            while True:
                if not self._connected and self._channels:
                    logger.info("RealtimeService: monitoring detected disconnected state, attempting reconnects...")
                    await self.reconnect_all()
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            return

    def start_monitoring(self):
        if self._monitor_task is None or self._monitor_task.done():
            self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def self_test(self, table: str, schema: str = "public", timeout_seconds: float = 8.0) -> bool:
        """Attempt a short-lived subscription to verify realtime works.

        Returns True on successful subscribe/unsubscribe cycle, False otherwise.
        """
        try:
            client = await self._ensure_client()
            channel_name = f"self-test-{table}"
            channel = client.channel(channel_name)

            # No-op callback; just validating handshake
            def _noop(_payload):
                return None

            channel = channel.on_postgres_changes(
                event="INSERT", schema=schema, table=table, callback=_noop
            )

            try:
                await asyncio.wait_for(channel.subscribe(), timeout=timeout_seconds)
                logger.info(f"RealtimeService: self-test subscribed '{schema}.{table}'")
                self._connected = True
                connection_monitor.update_realtime_status(True)
            except asyncio.TimeoutError:
                logger.error(f"RealtimeService: self-test timeout subscribing '{schema}.{table}'")
                self._connected = False
                connection_monitor.update_realtime_status(False, "self-test subscribe timeout")
                return False
            except Exception as e:
                logger.error(f"RealtimeService: self-test subscribe error for '{schema}.{table}': {e}", exc_info=True)
                self._connected = False
                connection_monitor.update_realtime_status(False, str(e))
                return False

            # Attempt a clean unsubscribe
            try:
                if hasattr(channel, 'unsubscribe'):
                    await channel.unsubscribe()
            except Exception as e:
                logger.warning(f"RealtimeService: self-test unsubscribe error for '{schema}.{table}': {e}")

            return True
        except Exception as e:
            logger.error(f"RealtimeService: self-test fatal error for '{schema}.{table}': {e}", exc_info=True)
            return False

    async def cleanup(self):
        """Cleanup all channels and close the client connection."""
        async with self._lock:
            try:
                # Stop monitor task first
                if self._monitor_task and not self._monitor_task.done():
                    self._monitor_task.cancel()
                    try:
                        await self._monitor_task
                    except asyncio.CancelledError:
                        pass
                    logger.info("RealtimeService: monitor task stopped")

                if self._client and self._channels:
                    # Remove all channels
                    for name, channel in self._channels.items():
                        try:
                            await self._client.remove_channel(channel)
                            logger.info(f"RealtimeService: removed channel '{name}'")
                        except Exception as e:
                            logger.warning(f"RealtimeService: error removing channel '{name}': {e}")

                    # Close the realtime connection if available
                    try:
                        if hasattr(self._client, 'realtime') and hasattr(self._client.realtime, 'close'):
                            await self._client.realtime.close()
                            logger.info("RealtimeService: realtime connection closed")
                    except Exception as e:
                        logger.warning(f"RealtimeService: error closing realtime connection: {e}")

                # Clear channels and reset state
                self._channels.clear()
                self._connected = False
                connection_monitor.update_realtime_status(False, "service shutdown")
                logger.info("RealtimeService: cleanup completed")

            except Exception as e:
                logger.error(f"RealtimeService: cleanup error: {e}", exc_info=True)


