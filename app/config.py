import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url


def resolve_base_dir():
    candidates = [Path.cwd(), Path(__file__).resolve().parent.parent]
    for candidate in candidates:
        if (candidate / ".env").exists():
            return candidate
    return Path.cwd()


BASE_DIR = resolve_base_dir()
load_dotenv(BASE_DIR / ".env", override=True)


class Config:
    # Expose project base directory for external scripts
    BASE_DIR = BASE_DIR
    # Directory for uploaded avatar images
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "app", "static", "uploads", "avatars")

    @staticmethod
    def init_upload_folder(app):
        folder = app.config.get("UPLOAD_FOLDER")
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)

    SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_NAME = os.getenv("DB_NAME", "general")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")

    # TiDB Cloud requires the exact username shown in its Connect instructions.
    # Do not substitute DB_NAME or manufacture a username if DB_USER is missing.
    if not DB_USER:
        raise RuntimeError(
            "DB_USER is missing. Set it to the complete username shown in TiDB Cloud Connect."
        )

    raw_db_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if raw_db_url:
        # Parse and normalize the URL without logging credentials.
        parsed_url = make_url(raw_db_url)
        if parsed_url.drivername == "mysql":
            parsed_url = parsed_url.set(drivername="mysql+pymysql")
        SQLALCHEMY_DATABASE_URI = parsed_url
    else:
        try:
            db_port = int(DB_PORT)
        except (TypeError, ValueError) as exc:
            raise RuntimeError("DB_PORT must be a valid integer.") from exc

        SQLALCHEMY_DATABASE_URI = URL.create(
            drivername="mysql+pymysql",
            username=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=db_port,
            database=DB_NAME,
            query={"charset": "utf8mb4"},
        )

    # PyMySQL accepts TLS verification options as connection arguments.
    # An optional CA bundle can be provided via DB_SSL_CA when required by the environment.
    ssl_options = {}
    ssl_ca = os.getenv("DB_SSL_CA")
    if ssl_ca:
        ssl_options["ca"] = ssl_ca

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "connect_args": {
            "ssl": ssl_options,
            "ssl_verify_cert": True,
            "ssl_verify_identity": True,
        },
    }

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = 3600
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = False
