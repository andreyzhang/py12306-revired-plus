"""Local environment diagnostic for py12306.

Run with ``python doctor.py`` before starting the ticketing service.
The checker is intentionally offline and does not contact 12306.
"""
import importlib.util
import sys
from pathlib import Path

REQUIRED = {
    "flask": "Flask",
    "requests": "requests",
    "requests_html": "requests-html",
    "flask_jwt_extended": "Flask-JWT-Extended",
    "redis": "redis",
    "pyppeteer": "pyppeteer-box",
}

def main():
    print(f"Python: {sys.version.split()[0]}")
    print(f"Project: {Path(__file__).resolve().parent}")
    missing = []
    for module, package in REQUIRED.items():
        ok = importlib.util.find_spec(module) is not None
        print(f"{'OK  ' if ok else 'MISS'} {module} ({package})")
        if not ok:
            missing.append(package)
    env = Path(__file__).with_name("env.py")
    print(f"{'OK  ' if env.exists() else 'MISS'} env.py")
    if missing:
        print("Missing packages:", ", ".join(missing))
        print("Install with: python -m pip install -r requirements.txt")
        return 1
    print("Environment is ready for import checks.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
