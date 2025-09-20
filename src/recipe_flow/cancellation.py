import asyncio
from typing import Dict

_tokens: Dict[str, asyncio.Event] = {}

def register(process_id: str) -> None:
    if process_id not in _tokens:
        _tokens[process_id] = asyncio.Event()

def cancel(process_id: str) -> None:
    ev = _tokens.get(process_id)
    if not ev:
        ev = asyncio.Event()
        _tokens[process_id] = ev
    ev.set()

def is_cancelled(process_id: str) -> bool:
    ev = _tokens.get(process_id)
    return bool(ev and ev.is_set())

def clear(process_id: str) -> None:
    _tokens.pop(process_id, None)

