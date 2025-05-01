"""
Logging configuration for the machine control application.
"""
import logging

def setup_logger(name="machine_control"):
    """
    Configure and return a logger with console and file handlers.
    """
    logger = logging.getLogger(name)
    
    # Only set up handlers if they haven't been set up already
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Create file handler
        file_handler = logging.FileHandler("machine_control.log")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Create a default logger instance for import
logger = setup_logger()
