from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

PERIOD_ORDER = {"15m": 0, "30m": 1, "45m": 2, "1H": 3, "2H": 4, "4H": 5, "1D": 6, "1W": 7}


def extract(args: argparse.Namespace) -> int:
    text = Path(args.log_file).read_text(encoding="utf-8", errors="replace")
    found = None
    for line in text.splitlines():
        pos = line.find('{"scanner"')
        if pos < 0:
            continue
        candidate = line[pos:].strip()
        try:
            obj = json.loads(candidate)
        except Exception:
            continue
        if isinstance(obj, dict) and "scanner" in obj and "summary" in obj:
            found = obj
    if found is None:
        raise SystemExit(f"No audit JSON found in {args.job_name}")
    found["_group"] = args.group
    found["_run_id"] = int(args.run_id)
    found["_job_id"] = int(args.job_id)
    found["_job_name"] = args.job_name
    with Path(args.output).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(found, ensure_ascii=False) + "\n")
    return 0


def build(args: argparse.Namespace) -> int:
    records = [
        json.loads(line)
        for line in Path(args.input).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records.sort(key=lambda x: (x.get("scanner", ""), PERIOD_ORDER.get(x.get("period", ""), 99)))

    rows: list[dict] = []
    for rec in records:
        summaries = rec.get("summary", []) or []
        hold = next((x for x in summaries if x.get("split") == "holdout"), {})
        research = next((x for x in summaries if x.get("split") == "research"), {})
        row = {
            "group": rec.get("_group"),
            "scanner": rec.get("scanner"),
            "period": rec.get("period"),
            "events": rec.get("events", 0),
            "symbols_in_db": rec.get("symbols_in_db"),
            "symbols_with_min_history": rec.get("symbols_with_min_history"),
            "parity_note": rec.get("parity_note"),
            "holdout_events": hold.get("events", 0),
            "holdout_symbols": hold.get("symbols", 0),
            "fresh_rate": hold.get("fresh_rate"),
            "operation_status": rec.get("operation_status"),
            "limitation": rec.get("limitation"),
            "setup_counts": json.dumps(rec.get("setup_counts", {}), ensure_ascii=False, sort_keys=True),
            "qualification_level_classes": json.dumps(
                rec.get("qualification_level_classes", {}), ensure_ascii=False, sort_keys=True
            ),
        }
        for horizon in (1, 3, 5, 10, 20):
            for key in ("hit", "median_signed", "median_abs", "median_mfe", "median_mae", "median_range_atr"):
                row[f"{key}_{horizon}"] = hold.get(f"{key}_{horizon}")
            row[f"research_hit_{horizon}"] = research.get(f"hit_{horizon}")
            row[f"research_signed_{horizon}"] = research.get(f"median_signed_{horizon}")
        rows.append(row)

    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "exact_holdout_matrix.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (out_dir / "exact_records_pretty.json").write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Aggregated {len(records)} exact scanner/timeframe records")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract")
    p_extract.add_argument("--group", required=True)
    p_extract.add_argument("--run-id", required=True)
    p_extract.add_argument("--job-id", required=True)
    p_extract.add_argument("--job-name", required=True)
    p_extract.add_argument("--log-file", required=True)
    p_extract.add_argument("--output", required=True)
    p_extract.set_defaults(func=extract)

    p_build = sub.add_parser("build")
    p_build.add_argument("--input", required=True)
    p_build.add_argument("--out-dir", required=True)
    p_build.set_defaults(func=build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
