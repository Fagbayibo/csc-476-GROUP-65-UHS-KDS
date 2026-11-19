"""Settings, read from environment variables (or a .env file in the backend folder)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
env_file = BASE_DIR / '.env'
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

DATABASE_URL = os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'uhs_kds.db'}")
JWT_SECRET = os.getenv('JWT_SECRET', 'change-this-to-a-long-random-secret-of-32-chars-or-more')
JWT_HOURS = int(os.getenv('JWT_HOURS', '8'))
# Secret used to turn clinic card numbers into pseudonyms. Keep it private and never change it
# after data has been loaded, or the same patient will get a different pseudonym.
PSEUDONYM_SALT = os.getenv('PSEUDONYM_SALT', 'change-this-salt')
CORS_ORIGINS = [o.strip() for o in os.getenv('CORS_ORIGINS', 'http://localhost:5173').split(',')]
MAX_UPLOAD_MB = int(os.getenv('MAX_UPLOAD_MB', '50'))
