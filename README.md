# Citation Network Builder via OpenAlex

Build a full **citation and reference network** for any list of academic papers by matching them against the OpenAlex full snapshot, without touching any API rate limits for bulk work.

Given a list of papers (DOIs + titles), this pipeline:
1. Matches each paper to its OpenAlex record
2. Extracts all outgoing references (what your papers cite)
3. Finds all incoming citations across the entire OpenAlex corpus (who cites your papers)
4. Optionally fetches rich metadata (authors, institutions, journals) for citing papers via the API

---

## Requirements

Python 3.9+

```bash
pip install openpyxl requests orjson
```

---

## Step 0 — Download the OpenAlex Snapshot

OpenAlex distributes a full snapshot of ~200 million works via a public AWS S3 bucket.
You only need the **works** entity (~600 GB compressed). Use an external drive.

```bash
# Install AWS CLI if needed: https://aws.amazon.com/cli/
# No AWS account required — the bucket is public

aws s3 sync s3://openalex/data/works/ /your/local/path/works/ --no-sign-request
```

Full snapshot documentation: https://docs.openalex.org/download-all-data/snapshot

Once downloaded, set `WORKS_DIR` in `pass1_match.py` and `pass2_citations.py` to the path where you saved it.

---

## Step 1 — Prepare your input file

Create a CSV or xlsx file with your papers. Place it in `data/raw/`.

**Required columns** (column names are case-insensitive):

| Column | Required | Notes |
|---|---|---|
| `doi` | Recommended | Normalized with or without `https://doi.org/` prefix |
| `title` | Recommended | Used as fallback when DOI is missing or mismatched |
| `year` | Recommended | Required for title+year fallback matching |

You need at least one of `doi` or (`title` + `year`) per paper. See `data/raw/sample_input.csv` for an example.

Then set `INPUT_FILE` at the top of `pass1_match.py`:

```python
INPUT_FILE = Path("data/raw/your_papers.csv")
```

---

## Step 2 — Match your papers to OpenAlex

```bash
python3 pass1_match.py
```

Scans the full snapshot once. Matches papers by **DOI first**, then **title + year** as a fallback for papers without a DOI or where the DOI format differs between sources.

**Fallback guards** — to prevent false positives:
- Titles shorter than 5 words are excluded
- Any title+year that maps to more than one paper is discarded as ambiguous

**Output:** `data/processed/matched_works.jsonl`
Each line: `{id, doi, title, year, match_method, referenced_works}`

> **Benchmarked runtime:** 3h 37m for ~33K input papers against the full 600 GB snapshot
> (6 workers, external spinning HDD). Reduce `N_WORKERS` to 2–3 for spinning HDDs; 6–8 for SSDs.

---

## Step 3 — Find all citing papers

```bash
python3 pass2_citations.py
```

Scans the snapshot a second time. For each work in OpenAlex, checks whether its `referenced_works` list contains any of your matched paper IDs.

**Output:** `data/processed/citing_works.jsonl`
Each line: `{id, doi, title, year, cites_our: [list of your paper IDs it cites]}`

> **Benchmarked runtime:** 3h 37m (same machine as Step 2).

---

## Step 4 — Export metadata for a specific paper

To get full metadata for all papers citing a single DOI, filtered to top journals:

1. Set `TARGET_DOI` in `fetch_citing_metadata.py`
2. Run:

```bash
python3 fetch_citing_metadata.py
```

Reads entirely from `citing_works.jsonl` — **no API calls, no internet connection needed**.

**Output:** `data/processed/citing_{doi}.xlsx`
- Sheet **"All"** — every citing paper with title, authors, institutions, journal, year, OA status, citation count
- Sheet **"Top Journals"** — filtered to the journals defined in `TOP_JOURNALS`

The default `TOP_JOURNALS` covers top economics and finance journals (AER, QJE, JPE, AEJ ×4, JF, RFS, JFE, Journal of Econometrics). Edit the dict at the top of the script to use your own list.

---

## How it works

The pipeline relies on a single field in every OpenAlex work record:

```json
{
  "id": "https://openalex.org/W111",
  "doi": "https://doi.org/10.xxxx/xxxxx",
  "display_name": "Paper title here",
  "publication_year": 2020,
  "referenced_works": [
    "https://openalex.org/W222",
    "https://openalex.org/W333"
  ]
}
```

OpenAlex internally resolves all references to their Work IDs. Finding citations is therefore a set-intersection problem: scan every work, check if its `referenced_works` overlaps with your matched paper IDs. No external API calls needed for the bulk work.

---

## Project structure

```
├── pass1_match.py               # Step 2 — match papers to OpenAlex
├── pass2_citations.py           # Step 3 — find citing papers + full metadata
├── fetch_citing_metadata.py     # Step 4 — export xlsx for a specific paper
├── validate_citation_counts.py  # Optional — compare against known citation counts
├── data/
│   ├── raw/
│   │   └── sample_input.csv     # Example input format
│   └── processed/               # All outputs land here (gitignored)
└── README.md
```

---

## Performance

Benchmarked on ~33K input papers against the full 600 GB OpenAlex snapshot:

| Step | Runtime | Output |
|---|---|---|
| Pass 1 — match papers | **3h 37m** | 35,110 matched (28,325 DOI + 6,785 title+year) |
| Pass 2 — find citations | **3h 37m** | 1,839,886 citing papers with full metadata |
| fetch_citing_metadata | **~5 sec** | per-paper xlsx, reads locally |

*Machine: external spinning HDD, macOS, 6 parallel workers (`N_WORKERS = 6`).*

Adjust `N_WORKERS` in each script based on your disk type:

| Disk type | Recommended `N_WORKERS` |
|---|---|
| Spinning HDD (USB) | 2–3 |
| SSD (Thunderbolt) | 6–8 |

---

## Known limitations

| Issue | Cause | Affected papers |
|---|---|---|
| Undercounted citations for classic papers | JSTOR DOIs (`10.2307/`) pre-date digital reference linking; authors cite by journal/volume/page, not DOI | Pre-1995 highly-cited works |
| Undercounted citations for recent papers | OpenAlex snapshot lags ~weeks behind live databases | 2020–2024 papers (~49% gap vs WoS) |
| Title+year false positives | Two different papers share an identical normalized title and year | Rare; mitigated by 5-word minimum and ambiguity removal |

---

## Citation

If you use this pipeline in your research, please cite OpenAlex:

> Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of the world's research works. *arXiv*. https://arxiv.org/abs/2205.01833
