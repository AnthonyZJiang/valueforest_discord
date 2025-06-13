import logging
from logging.handlers import RotatingFileHandler
from discord.utils import _ColourFormatter
import os

ASHLEY_ID = 1313007325224898580
ANGELA_ID = 1313008328229785640
TESTER_ID = 185020620310839296

def setup_logging(log_file: str = None) -> logging.Handler:
    level = logging.DEBUG
    
    library, _, _ = __name__.partition('.')
    logger = logging.getLogger(library)
    logger.setLevel(level)

    # Stream handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    formatter = _ColourFormatter()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    
    # File handler
    if not log_file:
        return stream_handler
    
    if not os.path.exists(os.path.dirname(log_file)):
        os.makedirs(os.path.dirname(log_file))
        
    file_handler_info = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=10)
    file_handler_info.setLevel(logging.INFO)
    f_format = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s::%(module)s %(message)s', '%Y-%m-%d %H:%M:%S')
    file_handler_info.setFormatter(f_format)
    
    file_handler_debug = RotatingFileHandler(log_file.rstrip('.log') + '_debug.log', maxBytes=5*1024*1024, backupCount=10)
    file_handler_debug.setLevel(logging.DEBUG)
    f_format = logging.Formatter('%(asctime)s %(levelname)-8s %(name)s::%(module)s %(message)s', '%Y-%m-%d %H:%M:%S')
    file_handler_debug.setFormatter(f_format)
    
    logger.addHandler(file_handler_info)
    logger.addHandler(file_handler_debug)
    
    return stream_handler
