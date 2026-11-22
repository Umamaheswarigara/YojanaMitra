"""Quick inspect of schemes.json structure."""
import json
from pathlib import Path

data_path = Path(__file__).parent.parent / "data" / "schemes.json"
with open(data_path, encoding="utf-8") as f:
    schemes = json.load(f)

print(f"Total schemes: {len(schemes)}")
print("\nAll schemes:")
for s in schemes:
    keys = list(s.keys())
    print(f"  [{s.get('id','?')}] {s.get('name','?')} | cat={s.get('category','?')}")

print("\nFirst scheme full keys:", list(schemes[0].keys()))
