import sys

from loguru import logger


_configured_level: str | None = None


def configure_logging(level: str = "INFO") -> None:
    global _configured_level
    level = level.upper()
    if level == _configured_level:
        return

    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}",
        enqueue=True,
    )
    _configured_level = level
