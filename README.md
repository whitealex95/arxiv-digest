# arxiv-digest

[![Daily Digest][workflow-shield]][workflow-url]
[![License][license-shield]][license-url]
[![Python 3.11+][python-shield]][python-url]

> **A personal, curated arXiv digest, delivered as a daily web page (GitHub Pages) and optional email.**

arxiv-digest watches your research areas on arXiv (plus Hugging Face's
community-curated Daily Papers), scores every match against your own
keywords, and publishes a ranked shortlist each day — not a raw dump.
Papers are deduplicated across runs, so you see each one at most once, and
everything is archived to browsable markdown.

## ✨ What you get

- 🌐 **Web digest on GitHub Pages** — the same shortlist as a web page, one
  page per day, with links to the last 14 days (`web_digest.keep_days`) so a
  missed day is one click away. No email setup needed.
- 📧 **Daily arXiv Digest email** (optional) — a capped shortlist (top-4 per section,
  15 overall by default), sections ordered by your `priority`, each paper
  sorted by relevance score with a score badge and a `matched:` line showing
  exactly which keywords put it there
- 🔍 **Your keywords, your weights** — categories map arXiv category codes to
  include/exclude keywords (`ti:` prefix for title-only matching), with
  optional per-keyword weights so a signature phrase outranks a generic one
- 🔥 **Trending on HuggingFace** — the day's community-upvoted papers
  (upvote floor + top-N) as their own section
- 🔁 **At-most-once delivery** — a persistent notified-store means weekend
  stalls never re-send Thursday's papers
- 🔗 **Code discovery** — GitHub repos auto-resolved for each paper via the
  HF Papers API
- 📚 **Full archive** — the email is a shortlist, but dated snapshots, the
  flat `PAPER_LIST.md`, and the monthly 1-year archive keep *everything*,
  all committed to the `results` branch
- 🤖 **Fully automated** — GitHub Actions runs the whole pipeline daily at
  14:53 UTC (after both arXiv's overnight postings and HF's ~13:00 UTC
  publish; off the top-of-hour minute GitHub's scheduler jams)

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

### Installation

```bash
git clone https://github.com/AlanSynn/arxiv-digest.git
cd arxiv-digest
uv sync
```

### Configuration

Everything you track lives in [`config.yaml`](config.yaml):

```yaml
categories:
  - name: "Character Motion Synthesis & Animation"
    cat_codes: ["cs.GR", "cs.CV"]        # arXiv categories to search
    priority: 9                          # section ordering (higher = earlier)
    include_keywords:                    # abstract matches
      - "motion synthesis"
      - "ti:character motion"            # ti: = title-only (higher precision)
    weights:                             # optional per-keyword multipliers
      "ti:character motion": 1.5         # (default 1.0; decides the ranking)
    exclude_keywords:                    # whole-word penalty, e.g. "sport"
      - "motion planning"                # (never fires on "transport")

scoring:
  threshold: 0.15
  title_weight: 2.0
  include_boost: 1.0
  exclude_penalty: 1.0
  email_max_per_category: 4            # digest shortlist caps (0 = uncapped)
  email_max_total: 15
  digest_window_days: 4                # digest draws from the newest N publish days
```

How selection works: include keywords are baked into the arXiv query, so
every fetched paper scores at least one hit — the **caps** (per-category,
then global, by score) are what make the email a digest instead of a dump.
Candidates come from the newest `digest_window_days` publish days. Papers
already shown in an earlier run are dropped first, then the caps apply, so a
day with no new arXiv mailing still shows the best papers not yet shown.
Archives and `PAPER_LIST.md` keep the full set either way.

Email is optional. To send it, set these environment variables (no secrets
in the repo):

```bash
export SMTP_USER="your-email@gmail.com"      # Gmail: use an app password
export SMTP_PASSWORD="your-app-password"
export EMAIL_RECIPIENT="you@example.com"
```

### Usage

```bash
# Fetch + score + update the local archive (no email)
uv run python -m src.arxiv_digest

# Full run: fetch, score, and send the digest email
uv run python -m src.arxiv_digest --send-email

# Build the web digest site (./site) from the saved daily digests
uv run python -m src.arxiv_digest.web

# Reset accumulated JSON state first
uv run python -m src.arxiv_digest --fresh-run

# Installed console scripts (after `uv sync`)
uv run arxiv-digest --help
uv run archive-papers --help

# Preview the email HTML with mock papers (no network, no send)
PYTHONPATH=. uv run python scripts/generate_email_preview.py
```

## 🤖 Running on GitHub Actions (forks)

The repo ships three workflows: a daily run (`daily-arxiv.yml`, 14:53 UTC), a
monthly archive (`archive-old-papers.yml`), and state persistence — every run
commits `logs/` (snapshots + dedup state) to the `results` branch.

The daily run also deploys the web digest to GitHub Pages.

To run your own copy:

1. **Turn on GitHub Pages**: Settings → Pages → Source: "GitHub Actions".
   The site is then at `https://<user>.github.io/<repo>/`. Pages of a public
   repo are public.
2. **Enable workflows on a fork**: open the Actions tab and enable them
   (GitHub turns off workflows, including scheduled ones, on new forks).
3. **(Optional) email**: add repository secrets
   (Settings → Secrets and variables → Actions):
   `SMTP_USER`, `SMTP_PASSWORD`, `EMAIL_RECIPIENT`. Without `SMTP_PASSWORD`
   the run skips email and only updates the web digest.
4. **Allow workflow pushes** — the workflows declare
   `permissions: contents: write`; if your fork restricts the default
   `GITHUB_TOKEN`, set Settings → Actions → General → Workflow permissions to
   "Read and write".
5. Push to `main` and trigger **Run Daily Arxiv** manually once to create the
   `results` branch and the first web page.

If `SMTP_PASSWORD` is set but another email secret is missing, the run
**fails loudly** (non-zero exit). It never silently skips your digest.

Ops liveness alarm: with failures going red, **"the web digest stopped
updating" (or "the daily email stopped arriving") is a reliable signal**.
Enable failure notifications
(Settings → Notifications → Actions) or watch the
[Actions tab][workflow-url]; a red run means the digest did not go out.

## 📋 Command Line Options

```
-h, --help            Show help message
--config_path PATH    Configuration file path (default: config.yaml)
--fresh-run           Reset all JSON files before running
--send-email          Send the digest email
--email-recipient ADDR  Override recipient
--smtp-user / --smtp-password  Override SMTP credentials
```

## 📁 Outputs (`logs/`)

| Path | Content |
|---|---|
| `ARXIV_PAPERS.md` / `arxiv-web.md` | accumulated collection, grouped by category |
| `daily-arxiv*.json` / dated `logs/json`, `logs/md` | per-day snapshots |
| `PAPER_LIST.md` | flat, deduplicated, newest-first list |
| `digests/YYYY-MM-DD.json` | each day's digest shortlist, source of the web digest |
| `notified_papers.json` | dedup state (dispatched paper keys) |
| `archive/archive_YYYYMM.*` | monthly archive of >1-year-old papers |

All of the above live on the `results` branch via the daily workflow.

## 🧪 Development

```bash
uv run pytest              # full test suite
uv run ruff check src      # lint
```

## 📄 License

Distributed under the Apache License 2.0. See `LICENSE` and `NOTICE` for
more information.

## 🙏 Acknowledgments

- Started from [Vincentqyw/cv-arxiv-daily](https://github.com/Vincentqyw/cv-arxiv-daily) (Apache-2.0)
- [arXiv](https://arxiv.org/) for open access to research
- [Hugging Face Daily Papers](https://huggingface.co/papers) for community curation

<!-- MARKDOWN LINKS & IMAGES -->
[workflow-shield]: https://github.com/AlanSynn/arxiv-digest/actions/workflows/daily-arxiv.yml/badge.svg
[workflow-url]: https://github.com/AlanSynn/arxiv-digest/actions/workflows/daily-arxiv.yml
[license-shield]: https://img.shields.io/github/license/AlanSynn/arxiv-digest.svg?style=for-the-badge
[license-url]: https://github.com/AlanSynn/arxiv-digest/blob/main/LICENSE
[python-shield]: https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge
[python-url]: https://www.python.org/downloads/
