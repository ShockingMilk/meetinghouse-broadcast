import logging
from logging.handlers import RotatingFileHandler

def configure_logging(config, log_directory):
    settings = config["application"]["logging"]

    level = getattr(
        logging,
        settings.get("level", "INFO").upper(),
        logging.INFO
    )

    logger = logging.getLogger("broadcast")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )

    file_handler = RotatingFileHandler(
        log_directory / "broadcast.log",
        maxBytes=settings["max_bytes"],
        backupCount=settings["backup_count"],
    )

    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger
