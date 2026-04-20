"""
Pass 2: Find all OpenAlex papers that cite our matched papers.
Extracts full metadata during the scan — no API needed later.

Input : data/processed/matched_works.jsonl  (from pass1)
Output: data/processed/citing_works.jsonl
          Each line: {id, doi, title, year, type, journal, issn_l,
                      authors, institutions, cited_by_count, oa_status,
                      cites_our}
"""

import gzip
from pathlib import Path
from multiprocessing import Pool
import orjson

WORKS_DIR    = Path("/path/to/openalex/data/works")  # ← set to your snapshot path
OUT_DIR      = Path("data/processed")
MATCHED_FILE = OUT_DIR / "matched_works.jsonl"
OUT_FILE     = OUT_DIR / "citing_works.jsonl"
N_WORKERS    = 6

# ── Worker globals ────────────────────────────────────────────────────────────

_OUR_IDS = None

def init_worker(our_ids):
    global _OUR_IDS
    _OUR_IDS = our_ids

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_our_ids(matched_file):
    ids = set()
    with open(matched_file, "rb") as f:
        for line in f:
            ids.add(orjson.loads(line)["id"])
    return ids

def extract_metadata(w, cited):
    loc    = w.get("primary_location") or {}
    source = loc.get("source") or {}
    auths  = w.get("authorships") or []

    authors = "; ".join(
        a["author"]["display_name"]
        for a in auths if a.get("author")
    )
    # set comprehension: faster than dict.fromkeys on a generator
    institutions = "; ".join({
        inst["display_name"]
        for a in auths
        for inst in (a.get("institutions") or [])
        if inst.get("display_name")
    })

    return {
        "id":             w["id"],
        "doi":            (w.get("doi") or "").lower().removeprefix("https://doi.org/"),
        "title":          w.get("display_name"),
        "year":           w.get("publication_year"),
        "type":           w.get("type"),
        "journal":        source.get("display_name"),
        "issn_l":         source.get("issn_l"),
        "authors":        authors,
        "institutions":   institutions,
        "cited_by_count": w.get("cited_by_count"),
        "oa_status":      (w.get("open_access") or {}).get("oa_status"),
        "cites_our":      list(cited),
    }

def scan_file(gz_path):
    results = []
    try:
        with gzip.open(gz_path, "rb") as f:
            for line in f:
                if not line or line == b"\n":
                    continue
                # Bytes-level skip: ~40% of works have no references at all.
                # Matches OpenAlex's current serialization exactly (no space after colon);
                # if the snapshot format ever changes this becomes a no-op but stays correct.
                if b'"referenced_works":[]' in line:
                    continue
                w     = orjson.loads(line)
                cited = _OUR_IDS.intersection(w.get("referenced_works", []))
                if cited:
                    results.append(extract_metadata(w, cited))
    except Exception as e:
        print(f"  [error] {gz_path}: {e}")
    return results

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Loading matched OpenAlex IDs...")
    our_ids = load_our_ids(MATCHED_FILE)
    print(f"  {len(our_ids):,} IDs loaded")

    files = sorted(WORKS_DIR.rglob("*.gz"))
    print(f"  {len(files):,} files to scan")
    print(f"  Writing to {OUT_FILE}\n")

    found = 0
    seen = set()
    with open(OUT_FILE, "wb", buffering=8 * 1024 * 1024) as out, \
         Pool(N_WORKERS, initializer=init_worker, initargs=(our_ids,)) as pool:
        for i, batch in enumerate(
            pool.imap_unordered(scan_file, map(str, files), chunksize=32), 1
        ):
            for r in batch:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                out.write(orjson.dumps(r) + b"\n")
                found += 1
            if i % 200 == 0:
                print(f"  {i}/{len(files)} files | {found:,} citing papers found")

    print(f"\nDone: {found:,} citing papers → {OUT_FILE}")

if __name__ == "__main__":
    main()
