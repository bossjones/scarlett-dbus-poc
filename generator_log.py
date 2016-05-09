import logging
logger = logging.getLogger('scarlettlogger')

try:
    from colorlog import ColoredFormatter
    from gettext import gettext as _
    """Return a logger with a default ColoredFormatter."""
    formatter = ColoredFormatter(
        "(%(threadName)-9s) %(log_color)s%(levelname)-8s%(reset)s (%(funcName)-5s) %(message_log_color)s%(message)s",
        datefmt=None,
        reset=True,
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red',
        },
        secondary_log_colors={
            'message': {
                'ERROR': 'red',
                'CRITICAL': 'red',
                'DEBUG': 'yellow'
            }
        },
        style='%'
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
except ImportError:
    # No color available, use default config
    logging.basicConfig(format='%(levelname)s: %(message)s')
    logger.warn("Disabling color, you really want to install colorlog.")
