"""Explicitly download or verify exact upstream data; never redistribute them."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", choices=("graphgnss", "urbannav", "all"), required=True)
    parser.add_argument("--destination-root", type=Path, default=HERE)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((HERE / "external_data_manifest.json").read_text())
    for source in manifest["sources"]:
        if args.dataset not in ("all", source["dataset"]):
            continue
        target = args.destination_root / source["path"]
        if target.exists():
            content = target.read_bytes()
        elif args.verify_only:
            raise SystemExit(f"Missing source: {target}; request an explicit download first.")
        else:
            with urlopen(source["url"], timeout=60) as response:
                content = response.read()
        if hashlib.sha256(content).hexdigest() != source["sha256"]:
            raise SystemExit(f"SHA-256 mismatch: {target}; existing files are never overwritten.")
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        print(f"Verified {source['dataset']}: {target}")


if __name__ == "__main__":
    main()
