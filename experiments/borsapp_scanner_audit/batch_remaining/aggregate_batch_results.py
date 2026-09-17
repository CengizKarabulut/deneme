from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path


def gh_json(path: str) -> dict:
    out = subprocess.check_output(["gh", "api", path], text=True)
    return json.loads(out)


def fetch_all_artifacts(repo: str, run_id: int) -> list[dict]:
    artifacts: list[dict] = []
    page = 1
    while True:
        payload = gh_json(
            f"repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100&page={page}"
        )
        batch = payload.get("artifacts", [])
        artifacts.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return artifacts


def download_zip(repo: str, artifact_id: int, target: Path) -> None:
    with target.open("wb") as fh:
        subprocess.run(
            ["gh", "api", f"repos/{repo}/actions/artifacts/{artifact_id}/zip"],
            stdout=fh,
            check=True,
        )


def read_artifact(repo: str, artifact: dict) -> tuple[dict, list[dict]]:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "artifact.zip"
        download_zip(repo, int(artifact["id"]), path)
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            manifest_name = next((n for n in names if n.endswith("/manifest.json")), None)
            summary_name = next((n for n in names if n.endswith("/summary.csv")), None)
            if manifest_name is None or summary_name is None:
                raise RuntimeError(f"manifest/summary missing in {artifact['name']}")
            manifest = json.loads(zf.read(manifest_name).decode("utf-8"))
            summary_text = zf.read(summary_name).decode("utf-8")
            summary_rows = list(csv.DictReader(io.StringIO(summary_text)))
    manifest["artifact_id"] = int(artifact["id"])
    manifest["artifact_name"] = artifact["name"]
    manifest["artifact_size_bytes"] = int(artifact.get("size_in_bytes", 0))
    return manifest, summary_rows


def numeric(value: str | None):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return value


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = fetch_all_artifacts(args.repo, args.run_id)
    manifests: list[dict] = []
    cells: list[dict] = []

    for idx, artifact in enumerate(sorted(artifacts, key=lambda x: x["name"]), 1):
        manifest, summary_rows = read_artifact(args.repo, artifact)
        manifests.append(manifest)
        print(
            json.dumps(
                {
                    "progress": f"{idx}/{len(artifacts)}",
                    "scanner": manifest.get("scanner"),
                    "period": manifest.get("period"),
                    "events": manifest.get("events"),
                    "size": manifest.get("artifact_size_bytes"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        for row in summary_rows:
            converted = {k: numeric(v) for k, v in row.items()}
            converted.update(
                {
                    "scanner": manifest.get("scanner"),
                    "period": manifest.get("period"),
                    "parity_note": manifest.get("parity_note", ""),
                    "symbols_in_db": manifest.get("symbols_in_db"),
                    "symbols_with_min_history": manifest.get("symbols_with_min_history"),
                    "manifest_events": manifest.get("events"),
                    "artifact_id": manifest.get("artifact_id"),
                }
            )
            cells.append(converted)

    manifest_fields = [
        "scanner",
        "period",
        "symbols_in_db",
        "symbols_with_min_history",
        "events",
        "holdout_fraction",
        "parity_note",
        "artifact_id",
        "artifact_name",
        "artifact_size_bytes",
    ]
    write_csv(args.out_dir / "manifests.csv", manifests, manifest_fields)

    cell_fields = sorted({key for row in cells for key in row.keys()})
    preferred = [
        "scanner",
        "period",
        "split",
        "events",
        "symbols",
        "fresh_rate",
        "hit_1",
        "median_signed_1",
        "median_abs_1",
        "median_range_atr_1",
        "hit_3",
        "median_signed_3",
        "median_abs_3",
        "median_range_atr_3",
        "hit_5",
        "median_signed_5",
        "median_abs_5",
        "median_range_atr_5",
        "hit_10",
        "median_signed_10",
        "median_abs_10",
        "median_range_atr_10",
        "hit_20",
        "median_signed_20",
        "median_abs_20",
        "median_range_atr_20",
        "parity_note",
        "symbols_in_db",
        "symbols_with_min_history",
        "manifest_events",
        "artifact_id",
    ]
    ordered = [x for x in preferred if x in cell_fields] + [
        x for x in cell_fields if x not in preferred
    ]
    write_csv(args.out_dir / "cells.csv", cells, ordered)

    by_scanner: dict[str, list[dict]] = defaultdict(list)
    for m in manifests:
        by_scanner[str(m["scanner"])].append(m)

    scanner_rows: list[dict] = []
    for scanner, rows in sorted(by_scanner.items()):
        rows = sorted(rows, key=lambda x: str(x["period"]))
        notes = sorted({str(x.get("parity_note", "")) for x in rows})
        zero_tfs = [str(x["period"]) for x in rows if int(x.get("events", 0)) == 0]
        scanner_rows.append(
            {
                "scanner": scanner,
                "timeframes": len(rows),
                "total_events": sum(int(x.get("events", 0)) for x in rows),
                "zero_event_timeframes": ",".join(zero_tfs),
                "parity_notes": " | ".join(notes),
            }
        )
    write_csv(
        args.out_dir / "scanner_summary.csv",
        scanner_rows,
        ["scanner", "timeframes", "total_events", "zero_event_timeframes", "parity_notes"],
    )

    holdout_lookup = {
        (str(r.get("scanner")), str(r.get("period"))): r
        for r in cells
        if r.get("split") == "holdout"
    }
    lines = [
        "# Remaining Scanner Batch Aggregate",
        "",
        f"- Source run: `{args.run_id}`",
        f"- Artifacts collected: **{len(manifests)}**",
        f"- Scanner/timeframe cells: **{len(manifests)}**",
        "",
        "## Scanner overview",
        "",
        "| Scanner | TF | Total events | Zero-event TFs | Parity note |",
        "|---|---:|---:|---|---|",
    ]
    for r in scanner_rows:
        lines.append(
            f"| `{r['scanner']}` | {r['timeframes']} | {r['total_events']} | "
            f"{r['zero_event_timeframes'] or '-'} | {r['parity_notes']} |"
        )

    lines += [
        "",
        "## Holdout H5 by timeframe",
        "",
        "| Scanner | TF | Events | Hit H5 | Median signed H5 | Median abs H5 | Range/ATR H5 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for m in sorted(manifests, key=lambda x: (str(x["scanner"]), str(x["period"]))):
        key = (str(m["scanner"]), str(m["period"]))
        r = holdout_lookup.get(key, {})
        def fmt(name: str) -> str:
            value = r.get(name)
            if value in (None, ""):
                return "-"
            if isinstance(value, (int, float)):
                return f"{value:.6f}"
            return str(value)
        lines.append(
            f"| `{key[0]}` | {key[1]} | {int(r.get('events', 0) or 0)} | "
            f"{fmt('hit_5')} | {fmt('median_signed_5')} | {fmt('median_abs_5')} | "
            f"{fmt('median_range_atr_5')} |"
        )

    (args.out_dir / "AGGREGATE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"artifacts": len(manifests), "scanners": len(by_scanner)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
