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
You only need the **works** entity (~1.2 TB compressed). Use an external drive.

```bash
# Install AWS CLI if needed: https://aws.amazon.com/cli/
# No AWS account required — the bucket is public

aws s3 sync s3://openalex/data/works/ /path/to/openalex/data/works/ --no-sign-request
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

> The sample list we originally ran this pipeline on is the **full publication history from Web of Science** of 11 journals: AER, QJE, JPE, the four AEJs (Applied, Policy, Macro, Micro), and JF, RFS, JFE, Journal of Econometrics. Any DOI/title list works — this is just what the benchmarks below refer to.

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
Each line: `{id, doi, title, year, match_method, referenced_works}` — plus `input_doi` for title+year matches (the original DOI from your input, when present and different from OpenAlex's).

---

## Step 3 — Find all citing papers

```bash
python3 pass2_citations.py
```

Scans the snapshot a second time. For each work in OpenAlex, checks whether its `referenced_works` list contains any of your matched paper IDs.

**Output:** `data/processed/citing_works.jsonl`
Each line: `{id, doi, title, year, type, journal, issn_l, authors, institutions, cited_by_count, oa_status, cites_our}`

---

## Step 4 — Export metadata for a specific paper

To get full metadata for all papers citing a single DOI:

1. Set `TARGET_DOI` in `fetch_citing_metadata.py`
2. Run:

```bash
python3 fetch_citing_metadata.py
```

Reads entirely from `citing_works.jsonl`

**Output:** `data/processed/citing_{doi}.xlsx` — one sheet with every citing paper (title, authors, institutions, journal, year, OA status, citation count). Filter/sort in Excel as needed. The script also prints the top 20 citing journals to the console.

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

Benchmarked on ~33K input papers (full WoS history of the 11 journals listed above) against the full ~1.2 TB OpenAlex snapshot:

| Step | Runtime | Output |
|---|---|---|
| Pass 1 — match papers | **~3h 59m** | 35,110 matched (28,325 DOI + 6,785 title+year) |
| Pass 2 — find citations | **~3h 36m** | 1,839,886 citing papers with full metadata |
| fetch_citing_metadata | **~5 sec** | per-paper xlsx, reads locally |

*Machine: external HDD over USB, mac Mini.*

---

## Known limitations

| Issue | Cause | Affected papers |
|---|---|---|
| Potentially undercounted citations for recent papers | OpenAlex snapshot lags ~weeks behind live databases | 2020–2024 papers |

---

## Citation

If you use this pipeline in your research, please cite OpenAlex:

> Priem, J., Piwowar, H., & Orr, R. (2022). OpenAlex: A fully-open index of the world's research works. *arXiv*. https://arxiv.org/abs/2205.01833
