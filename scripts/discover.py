"""SEC filing discovery only; no inference from keyword absence or present listings."""
import argparse
import calendar
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
API = "https://efts.sec.gov/LATEST/search-index"


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


class Client:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Academic Research jerry.silvon@bbabah.christuniversity.in"
        self.last = 0.0

    def get(self, url, params=None):
        key = hashlib.sha256((url + json.dumps(params, sort_keys=True)).encode()).hexdigest()
        path = ROOT / "data/raw/http" / (key + ".json")
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))["payload"]
        for attempt in range(4):
            time.sleep(max(0, 0.6 - (time.monotonic() - self.last)))
            response = self.session.get(url, params=params, timeout=45)
            self.last = time.monotonic()
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 3:
                break
            time.sleep(2 ** attempt)
        response.raise_for_status()
        payload = response.json()
        save_json(path, {"url": response.url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                         "response_sha256": hashlib.sha256(response.content).hexdigest(),
                         "payload": payload})
        return payload


def discover(client, paper, settings, cutoff):
    records, audit = {}, []
    periods = []
    for year in range(settings["start_year"], int(cutoff[:4]) + 1):
        for month in range(1, 13):
            start = f"{year}-{month:02d}-01"
            if start <= cutoff:
                periods.append((start, min(f"{year}-{month:02d}-{calendar.monthrange(year, month)[1]}", cutoff)))
    for start, end in periods:
        for query in settings["queries"]:
            params = dict(q=query, dateRange="custom", startdt=start,
                          enddt=end, forms=settings["root_forms"], size=100)
            offset, seen = 0, set()
            while True:
                payload = client.get(API, dict(params, **{"from": offset}))
                if payload.get("timed_out") or payload.get("_shards", {}).get("failed", 0):
                    raise RuntimeError("Incomplete SEC search response")
                total = payload["hits"]["total"]
                hits = payload["hits"]["hits"]
                if total["relation"] != "eq" or total["value"] > 10000:
                    raise RuntimeError("Partition requires finer dates; search total truncated")
                for hit in hits:
                    identity = hit["_id"]
                    seen.add(identity)
                    src = hit["_source"]
                    if not (params["startdt"] <= src["file_date"] <= params["enddt"]):
                        raise ValueError("Filing outside requested dates")
                    if identity not in records:
                        filename = identity.split(":", 1)[1]
                        cik = int(src["ciks"][0])
                        accession = src["adsh"]
                        records[identity] = dict(document_id=identity, **src,
                            source_url=f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{filename}",
                            matched_queries=[])
                    if query not in records[identity]["matched_queries"]:
                        records[identity]["matched_queries"].append(query)
                offset += len(hits)
                if offset >= total["value"]:
                    break
                if not hits:
                    raise RuntimeError("Empty page before reported total")
            audit.append(dict(start=start, end=end, query=query, reported_documents=total["value"],
                              unique_returned=len(seen), complete=len(seen) == total["value"]))
            print(paper, start, query, len(seen), flush=True)
    docs = sorted(records.values(), key=lambda r: (r["file_date"], r["document_id"]))
    stats = dict(paper=paper, cutoff=cutoff, status="keyword_discovery_only",
                 documents=len(docs), accessions=len({r["adsh"] for r in docs}),
                 ciks=len({c for r in docs for c in r["ciks"]}),
                 primary_10k_documents=sum(r["file_type"] == "10-K" for r in docs),
                 complete=all(a["complete"] for a in audit), partitions=audit)
    save_json(ROOT / f"data/discovery/{paper}.json", docs)
    save_json(ROOT / f"outputs/{paper}/discovery_audit.json", stats)
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--paper", choices=["all", "conditional_maturity", "supplier_finance"], default="all")
    args = parser.parse_args()
    config = json.loads((ROOT / "research_config.json").read_text())
    client = Client()
    for paper, settings in config["papers"].items():
        if args.paper in ("all", paper):
            print(json.dumps(discover(client, paper, settings, config["cutoff"])), flush=True)
