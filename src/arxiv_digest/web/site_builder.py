"""Static web digest: one page per run day, with links to recent days.

Each daily run saves its digest slice (the same papers the email would carry)
to ``<data_dir>/YYYY-MM-DD.json``. The site is always rebuilt from those
files, so the date navigation on every page stays current. Pages reuse the
email renderer, so the site and the email look the same.
"""

import argparse
import datetime
import json
import logging
import os
from typing import Dict, List, Optional

from ..core.config import load_config
from ..models.paper import Paper
from ..services.email_service import _ACCENT, _MONO, _MUTED, EmailService, _esc


def _day_path(data_dir: str, day: datetime.date) -> str:
    return os.path.join(data_dir, f"{day.isoformat()}.json")


def list_days(data_dir: str) -> List[datetime.date]:
    """Dates that have a saved digest, newest first."""
    if not os.path.isdir(data_dir):
        return []
    days = []
    for name in os.listdir(data_dir):
        stem, ext = os.path.splitext(name)
        if ext != ".json":
            continue
        try:
            days.append(datetime.date.fromisoformat(stem))
        except ValueError:
            continue
    return sorted(days, reverse=True)


def load_day(path: str) -> Dict[str, List[Paper]]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return {
        section["name"]: [Paper.from_dict(p) for p in section["papers"]]
        for section in data["sections"]
    }


def save_day(
    data_dir: str,
    day: datetime.date,
    papers_by_category: Dict[str, List[Paper]],
) -> str:
    """Merge this run's slice into the day's file and return its path.

    A second run on the same day must add to the page, not replace it: its
    slice holds only papers that the first run had not dispatched yet.
    """
    path = _day_path(data_dir, day)
    merged = load_day(path)
    for name, papers in papers_by_category.items():
        section = merged.setdefault(name, [])
        known = {p.paper_key for p in section}
        section.extend(p for p in papers if p.paper_key not in known)

    payload = {
        "date": day.isoformat(),
        "sections": [
            {"name": name, "papers": [p.to_dict() for p in papers]}
            for name, papers in merged.items()
        ],
    }
    os.makedirs(data_dir, exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)
    return path


# The daily workflow commits logs/ to this branch, not to main.
RESULTS_BRANCH = "results"


def _github_url(kind: str, branch: Optional[str], path: str) -> Optional[str]:
    """URL of ``path`` in the repo of the running Actions job, else None."""
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo or os.path.isabs(path):
        return None
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    branch = branch or os.environ.get("GITHUB_REF_NAME", "main")
    return f"{server}/{repo}/{kind}/{branch}/{os.path.normpath(path)}"


def config_edit_url(config_path: str) -> Optional[str]:
    return _github_url("edit", None, config_path)


def paper_list_url(paper_list_path: str) -> Optional[str]:
    return _github_url("blob", RESULTS_BRANCH, paper_list_path)


def _nav_link(label: str, url: str) -> str:
    return (
        f'<a href="{_esc(url)}" class="accent" style="color:{_ACCENT}; '
        f'text-decoration:none;">{label}</a>'
    )


def _render_nav(
    days: List[datetime.date],
    current: datetime.date,
    edit_url: Optional[str] = None,
    list_url: Optional[str] = None,
) -> str:
    items = []
    for day in days:
        label = day.strftime("%a&nbsp;%m-%d")
        if day == current:
            items.append(
                f'<span class="accent" style="color:{_ACCENT}; '
                f'font-weight:600;">{label}</span>'
            )
        else:
            items.append(
                f'<a href="{day.isoformat()}.html" class="muted" '
                f'style="color:{_MUTED}; text-decoration:none;">{label}</a>'
            )
    tools = []
    if list_url:
        tools.append(_nav_link("full&nbsp;paper&nbsp;list&nbsp;↗", list_url))
    if edit_url:
        tools.append(_nav_link("edit&nbsp;config.yaml&nbsp;↗", edit_url))
    # Not inside the .muted div: its dark-mode "a" rule would turn these gray.
    tools_html = (
        f'<div style="font-family:{_MONO}; font-size:11px; line-height:2;">'
        + " · ".join(tools)
        + "</div>"
        if tools else ""
    )
    return (
        f'<div style="padding-bottom:20px;">'
        f'<div class="muted" style="font-family:{_MONO}; color:{_MUTED}; '
        f'font-size:11px; line-height:2;">'
        + " · ".join(items)
        + "</div>"
        + tools_html
        + "</div>"
    )


def _write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def build_site(
    data_dir: str,
    site_dir: str,
    keep_days: int,
    threshold: Optional[float] = None,
    edit_url: Optional[str] = None,
    list_url: Optional[str] = None,
) -> int:
    """Render the newest ``keep_days`` digests into ``site_dir``.

    ``index.html`` is a copy of the newest day. Returns the number of day
    pages written.
    """
    days = list_days(data_dir)[:max(keep_days, 1)]
    os.makedirs(site_dir, exist_ok=True)
    renderer = EmailService({})

    if not days:
        today = datetime.date.today().isoformat()
        _write(os.path.join(site_dir, "index.html"), renderer.render_email({}, today))
        return 0

    for i, day in enumerate(days):
        papers_by_category = load_day(_day_path(data_dir, day))
        stats = {
            "total": sum(len(v) for v in papers_by_category.values()),
            "categories": sum(1 for v in papers_by_category.values() if v),
            "threshold": threshold,
        }
        page = renderer.render_email(
            papers_by_category, day.isoformat(), stats,
            nav_html=_render_nav(days, day, edit_url, list_url),
            paper_list_url=list_url,
        )
        _write(os.path.join(site_dir, f"{day.isoformat()}.html"), page)
        if i == 0:
            _write(os.path.join(site_dir, "index.html"), page)
    return len(days)


def main() -> int:
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        )
    parser = argparse.ArgumentParser(description="Build the static web digest site")
    parser.add_argument(
        '--config_path', type=str, default='config.yaml',
        help='configuration file path'
    )
    args = parser.parse_args()

    config = load_config(args.config_path)
    web = config["web_digest"]
    count = build_site(
        web.data_dir, web.site_dir, web.keep_days, config["scoring"].threshold,
        edit_url=config_edit_url(args.config_path),
        list_url=paper_list_url(config["toc"].paper_list_path),
    )
    logging.info("Web digest site: %d day page(s) -> %s", count, web.site_dir)
    return 0
