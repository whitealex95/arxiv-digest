"""Tests for the static web digest (GitHub Pages) site builder."""

from datetime import date

from src.arxiv_digest.models.paper import Paper
from src.arxiv_digest.web.site_builder import build_site, list_days, load_day, save_day


def _paper(key, cat="Motion", score=0.5, community=False):
    return Paper(
        paper_key=key, title=f"Title {key}", authors_str="A",
        abstract="Abstract.", published=date(2026, 10, 20),
        updated=date(2026, 10, 21), primary_category="cs.GR",
        all_categories=["cs.GR", "cs.CV"], entry_id=f"http://arxiv.org/abs/{key}",
        abs_url=f"http://arxiv.org/abs/{key}", code_url="https://github.com/a/b",
        category=cat, score=score, matched_keywords=["motion"],
        upvotes=20 if community else None, is_community_signal=community,
    )


def test_paper_dict_roundtrip():
    paper = _paper("2610.00001", community=True)
    assert Paper.from_dict(paper.to_dict()) == paper


def test_save_day_merges_same_day_without_duplicates(tmp_path):
    day = date(2026, 10, 27)
    save_day(str(tmp_path), day, {"Motion": [_paper("1"), _paper("2")]})
    save_day(
        str(tmp_path), day,
        {"Motion": [_paper("2"), _paper("3")], "HF": [_paper("4", "HF", community=True)]},
    )

    loaded = load_day(str(tmp_path / "2026-10-27.json"))
    assert list(loaded) == ["Motion", "HF"]
    assert [p.paper_key for p in loaded["Motion"]] == ["1", "2", "3"]
    assert loaded["HF"][0].is_community_signal


def test_list_days_newest_first_and_skips_other_files(tmp_path):
    for d in (date(2026, 10, 25), date(2026, 10, 27), date(2026, 10, 26)):
        save_day(str(tmp_path), d, {"Motion": [_paper("1")]})
    (tmp_path / "notes.json").write_text("{}")
    (tmp_path / "2026-10-24.json.tmp").write_text("{}")

    assert list_days(str(tmp_path)) == [
        date(2026, 10, 27), date(2026, 10, 26), date(2026, 10, 25)
    ]


def test_build_site_keeps_newest_days_and_links_them(tmp_path):
    data_dir, site_dir = tmp_path / "data", tmp_path / "site"
    for day_num in range(20, 28):
        save_day(str(data_dir), date(2026, 10, day_num), {"Motion": [_paper(f"k{day_num}")]})

    count = build_site(str(data_dir), str(site_dir), keep_days=3, threshold=0.15)

    assert count == 3
    pages = sorted(p.name for p in site_dir.iterdir())
    assert pages == ["2026-10-25.html", "2026-10-26.html", "2026-10-27.html", "index.html"]

    index = (site_dir / "index.html").read_text()
    assert index == (site_dir / "2026-10-27.html").read_text()
    assert "Title k27" in index
    assert 'href="2026-10-26.html"' in index
    assert 'href="2026-10-25.html"' in index
    assert 'href="2026-10-27.html"' not in index
    assert 'href="2026-10-24.html"' not in index

    older = (site_dir / "2026-10-25.html").read_text()
    assert "Title k25" in older
    assert 'href="2026-10-27.html"' in older


def test_build_site_without_data_writes_index(tmp_path):
    site_dir = tmp_path / "site"
    assert build_site(str(tmp_path / "missing"), str(site_dir), keep_days=14) == 0
    assert "No new papers matched today" in (site_dir / "index.html").read_text()
