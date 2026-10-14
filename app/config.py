import os
from pathlib import Path

from dotenv import load_dotenv


def resolve_base_dir():
    candidates = [Path.cwd(), Path(__file__).resolve().parent.parent]
    for candidate in candidates:
        if (candidate / '.env').exists():
            return candidate
    return Path.cwd()


BASE_DIR = resolve_base_dir()
load_dotenv(BASE_DIR / '.env')


class Config:
    # Existing settings above
    # Directory for uploaded avatar images
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'avatars')
    # Ensure the upload directory exists when the app starts
    @staticmethod
    def init_upload_folder(app):
        import os
        folder = app.config.get('UPLOAD_FOLDER')
        if folder and not os.path.isdir(folder):
            os.makedirs(folder, exist_ok=True)

    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me-in-production')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'general')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')

    raw_db_url = os.getenv('DATABASE_URL') or os.getenv('MYSQL_URL')
    if raw_db_url:
        if raw_db_url.startswith('mysql://'):
            raw_db_url = raw_db_url.replace('mysql://', 'mysql+pymysql://', 1)
        SQLALCHEMY_DATABASE_URI = raw_db_url
    else:
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
        )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 300}

    WTF_CSRF_TIME_LIMIT = 3600
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = False
