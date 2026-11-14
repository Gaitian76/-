import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env(path=None):
    """读取简单的 KEY=VALUE 文件；已有环境变量始终优先。"""
    path = Path(path) if path else ROOT / '.env'
    if not path.exists():
        return
    for raw in path.read_text(encoding='utf-8-sig').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def provider(prefix):
    return {
        'base_url': os.getenv(f'{prefix}_BASE_URL', '').strip(),
        'api_key': os.getenv(f'{prefix}_API_KEY', '').strip(),
        'model': os.getenv(f'{prefix}_MODEL', '').strip(),
    }
