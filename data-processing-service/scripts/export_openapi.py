"""Run from data-processing-service: python scripts/export_openapi.py."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from main import app


if __name__ == "__main__":
    target = ROOT / "contracts" / "data-processing-v1.openapi.json"
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)
