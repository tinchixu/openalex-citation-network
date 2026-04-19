"""
For a given DOI, retrieve all papers that cite it — with full metadata —
from the locally processed citing_works.jsonl. No API calls needed.

Optionally filters to a predefined list of top journals.

Inputs:
  data/processed/matched_works.jsonl   — resolves DOI → OpenAlex ID
  data/processed/citing_works.jsonl    — full metadata for all citing papers

Output:
  data/processed/citing_{slug}.xlsx
    Sheet "All"          — every citing paper with full metadata
    Sheet "Top Journals" — filtered to journals defined in TOP_JOURNALS
"""

import re
from pathlib import Path
import orjson
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# ── Configuration — edit these ────────────────────────────────────────────────

TARGET_DOI = "10.1016/j.jeconom.2007.05.001"   # ← change to any DOI in your dataset

TOP_JOURNALS = {
    "american economic review":                    "AER",
    "quarterly journal of economics":              "QJE",
    "journal of political economy":                "JPE",
    "american economic journal applied economics": "AEJ Applied",
    "american economic journal economic policy":   "AEJ Policy",
    "american economic journal macroeconomics":    "AEJ Macro",
    "american economic journal microeconomics":    "AEJ Micro",
    "journal of finance":                          "JF",
    "review of financial studies":                 "RFS",
    "journal of financial economics":              "JFE",
    "journal of econometrics":                     "JEconometrics",
}

OUT_DIR = Path("data/processed")

# ── Helpers ───────────────────────────────────────────────────────────────────

def norm_journal(name):
    if not name:
        return ""
    name = name.lower().strip()
    if name.startswith("the "):
        name = name[4:]
    name = re.sub(r"[^\w\s]", " ", name)
    return re.sub(r"\s+", " ", name).strip()

def doi_slug(doi):
    return re.sub(r"[^\w]", "_", doi)

def find_openalex_id(doi):
    with open(OUT_DIR / "matched_works.jsonl", "rb") as f:
        for line in f:
            w = orjson.loads(line)
            if w.get("doi") == doi or w.get("wos_doi") == doi:
                return w["id"], w.get("title"), w.get("year")
    return None, None, None

def write_sheet(ws, data, fields):
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="2F5496")
    for col, field in enumerate(fields, 1):
        cell = ws.cell(row=1, column=col, value=field)
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = Alignment(horizontal="center")
    for row_idx, record in enumerate(data, 2):
        for col, field in enumerate(fields, 1):
            ws.cell(row=row_idx, column=col, value=record.get(field))
    for col, field in enumerate(fields, 1):
        max_len = max((len(str(r.get(field) or "")) for r in data), default=0)
        ws.column_dimensions[get_column_letter(col)].width = min(max(max_len, len(field)) + 2, 60)
    ws.freeze_panes = "A2"

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    slug = doi_slug(TARGET_DOI)

    # 1. Resolve DOI → OpenAlex ID
    print(f"Looking up: {TARGET_DOI}")
    oa_id, title, year = find_openalex_id(TARGET_DOI)
    if not oa_id:
        raise SystemExit(f"DOI not found in matched_works.jsonl: {TARGET_DOI}")
    print(f"  {title} ({year})")
    print(f"  {oa_id}")

    # 2. Stream citing_works.jsonl — collect rows that cite this paper
    print("\nReading citing_works.jsonl...")
    rows = []
    with open(OUT_DIR / "citing_works.jsonl", "rb") as f:
        for line in f:
            w = orjson.loads(line)
            if oa_id in w.get("cites_our", []):
                w["journal_abbr"] = TOP_JOURNALS.get(norm_journal(w.get("journal")), "")
                rows.append(w)

    print(f"  {len(rows):,} citing papers found")

    # 3. Build field list (exclude internal cites_our)
    fields = ["id", "doi", "title", "year", "type", "journal", "journal_abbr",
              "issn_l", "authors", "institutions", "cited_by_count", "oa_status"]

    top_rows = [r for r in rows if r["journal_abbr"]]

    # 4. Write xlsx
    wb       = Workbook()
    ws_all   = wb.active
    ws_all.title = "All"
    write_sheet(ws_all, rows, fields)

    ws_top = wb.create_sheet("Top Journals")
    write_sheet(ws_top, top_rows, fields)

    out_path = OUT_DIR / f"citing_{slug}.xlsx"
    wb.save(out_path)

    print(f"\nOutput → {out_path}")
    print(f"  Sheet 'All'          {len(rows):,} rows")
    print(f"  Sheet 'Top Journals' {len(top_rows):,} rows")

    from collections import Counter
    print("\nBreakdown by journal:")
    for journal, n in sorted(Counter(r["journal_abbr"] for r in top_rows).items(),
                              key=lambda x: -x[1]):
        print(f"  {n:>5}  {journal}")

if __name__ == "__main__":
    main()
