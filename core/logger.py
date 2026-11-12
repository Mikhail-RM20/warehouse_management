from pathlib import Path

# Создаем папку и описываем путь относительно рабочей директории.
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

dict_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "base": {
            "format": (
                "%(asctime)s | %(name)s | %(levelname)s | "
                "%(filename)s:%(lineno)d | %(message)s"
            ),
        }
    },
    "handlers": {
        "file_routes": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "base",
            "filename": str(LOG_DIR / "routes.log"),
            "encoding": "utf-8",  # Кодировка для RU сообщений.
            "maxBytes": 10 * 1024 * 1024,  # Лимит размера файла.
            "backupCount": 5,  # Храним 5 файлов, старые удаляются.
        },
        "file_services": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "INFO",
            "formatter": "base",
            "filename": str(LOG_DIR / "services.log"),
            "encoding": "utf-8",
            "maxBytes": 10 * 1024 * 1024,
            "backupCount": 5,
        },
    },
    "loggers": {
        "route_logger": {
            "level": "INFO",
            "handlers": ["file_routes"],
            "propagate": False,  # Обработать своими сообщениями, а не передавать род.логгеру.
        },
        "services_logger": {
            "level": "INFO",
            "handlers": ["file_services"],
            "propagate": False,
        },
    },
}
