"""Fetch discovered filing documents from EDGAR Archives.

The stage discovery never had: discover.py builds source_url values but never
retrieves them. SEC fair-access requires a contact email in the User-Agent and
caps request rate; both are enforced here.
"""
import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
UA = "Academic Research jerry.silvon@bbabah.christuniversity.in"
DOCS = ROOT / "data/raw/documents"
MIN_INTERVAL = 0.6


def fetch(paper, limit=None):
    records = json.loads((ROOT / f"data/discovery/{paper}.json").read_text(encoding="utf-8"))
    if limit:
        records = records[:limit]
    session = requests.Session()
    session.headers["User-Agent"] = UA
    out = DOCS / paper
    out.mkdir(parents=True, exist_ok=True)
    manifest, last = [], 0.0
    for i, rec in enumerate(records, 1):
        key = hashlib.sha256(rec["document_id"].encode()).hexdigest()[:24]
        path = out / (key + ".html")
        entry = dict(document_id=rec["document_id"], cik=rec["ciks"][0], adsh=rec["adsh"],
                     file_date=rec["file_date"], file_type=rec["file_type"],
                     display_names=rec.get("display_names"), path=str(path.relative_to(ROOT)))
        if path.exists():
            entry.update(status="cached", bytes=path.stat().st_size)
        else:
            time.sleep(max(0, MIN_INTERVAL - (time.monotonic() - last)))
            try:
                r = session.get(rec["source_url"], timeout=60)
                last = time.monotonic()
                if r.status_code == 200:
                    path.write_bytes(r.content)
                    entry.update(status="ok", bytes=len(r.content))
                else:
                    entry.update(status=f"http_{r.status_code}", bytes=0)
            except Exception as exc:
                last = time.monotonic()
                entry.update(status="error", error=str(exc)[:200], bytes=0)
        manifest.append(entry)
        if i % 25 == 0:
            print(f"{paper} {i}/{len(records)}", flush=True)
    ok = sum(e["status"] in ("ok", "cached") for e in manifest)
    (ROOT / f"outputs/{paper}").mkdir(parents=True, exist_ok=True)
    (ROOT / f"outputs/{paper}/fetch_manifest.json").write_text(
        json.dumps(dict(paper=paper, retrieved_utc=datetime.now(timezone.utc).isoformat(),
                        user_agent=UA, requested=len(manifest), retrieved=ok,
                        documents=manifest), indent=2), encoding="utf-8")
    print(json.dumps(dict(paper=paper, requested=len(manifest), retrieved=ok)), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--paper", default="conditional_maturity")
    p.add_argument("--limit", type=int)
    args = p.parse_args()
    fetch(args.paper, args.limit)
