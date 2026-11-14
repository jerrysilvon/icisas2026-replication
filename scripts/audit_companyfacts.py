"""Small named-source access pilot, not a representative empirical sample."""
from discover import Client, ROOT, save_json


if __name__ == "__main__":
    client = Client()
    audit = []
    for cik in [98362, 30625, 67215, 1050446, 1071255]:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
        data = client.get(url)
        tags = [dict(namespace=ns, tag=tag, label=definition.get("label"),
                     description=definition.get("description"), units=definition.get("units"))
                for ns, namespace in data["facts"].items() for tag, definition in namespace.items()
                if "supplier" in tag.lower() or "financeprogram" in tag.lower()]
        entry = dict(cik=f"{cik:010d}", entity=data["entityName"], source=url,
                     supplier_finance_tags=tags, status="access_pilot_not_analysis_sample")
        audit.append(entry)
        print(cik, data["entityName"], len(tags), flush=True)
    save_json(ROOT / "outputs/companyfacts_access_pilot.json", audit)
