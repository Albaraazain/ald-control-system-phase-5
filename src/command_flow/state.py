"""
Shared state for command processing.
"""

class CommandState:
    """Singleton class to manage command state."""
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CommandState, cls).__new__(cls)
            cls._instance._current_command_id = None
        return cls._instance
    
    def __init__(self):
        """Initialize instance attributes"""
        # Only set if not already set by __new__
        if not hasattr(self, '_current_command_id'):
            self._current_command_id = None

    @property
    def current_command_id(self):
        return self._current_command_id

    @current_command_id.setter
    def current_command_id(self, value):
        self._current_command_id = value

# Global instance
state = CommandState()
