"""The landing page renders from what the repository holds: template, air.json and the figure fragments.

Run from the repository root:  .venv/bin/python -m pytest site/tests -q
"""
import copy
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import pytest

import render

SITE = Path(__file__).resolve().parents[1]
SRC, STATIC = SITE / "src", SITE / "static"
AIR = json.loads((SITE / "data/air.json").read_text())


@pytest.fixture(scope="module")
def page() -> str:
    return render.render_page()


class Text(HTMLParser):
    """Text of each paragraph, list item and heading outside figures, with style and script left out."""

    def __init__(self):
        super().__init__()
        self.skip = self.fig = 0
        self.prose, self.cur = [], None

    def handle_starttag(self, tag, attrs):
        if tag in ("style", "script"):
            self.skip += 1
        if tag == "figure":
            self.fig += 1
        if tag in ("p", "li", "h2", "h1") and not self.fig and not self.skip:
            self.cur = []

    def handle_endtag(self, tag):
        if tag in ("style", "script"):
            self.skip -= 1
        if tag == "figure":
            self.fig -= 1
        if tag in ("p", "li", "h2", "h1") and self.cur is not None:
            self.prose.append((tag, " ".join("".join(self.cur).split())))
            self.cur = None

    def handle_data(self, data):
        if self.cur is not None and not self.skip:
            self.cur.append(data)


def prose(html: str):
    t = Text()
    t.feed(html)
    return t.prose


def leaves(x):
    if isinstance(x, dict):
        for v in x.values():
            yield from leaves(v)
    elif isinstance(x, list):
        for v in x:
            yield from leaves(v)
    else:
        yield x


def test_renders_with_every_section(page):
    heads = [t for tag, t in prose(page) if tag == "h2"]
    expect = [f"{AIR['toll']['fold']} times apart on the toll, one order of what to do", "What changes the order",
              "Where the smoke goes", "One city, end to end", "Fifty cities", "Open questions", "Run it",
              "The notebook", "What Diwali does to the air", "The question behind all of it",
              "What hasn’t been analysed", "Work with me"]
    assert heads == expect
    for kind in ("toll", "cli", "ladder", "stab", "moves", "smoke", "day", "cities"):
        assert f'class="af af-{kind}' in page, kind
    assert page.count("<figure") == 8
    assert '<h1 class="post-title">air apocalypse</h1>' in page


def test_no_template_syntax_left(page):
    assert "{{" not in page and "}}" not in page and "{%" not in page and "%}" not in page
    assert not re.search(r"\$[A-Za-z_{]", page)
    markup = re.sub(r"<(style|script).*?</\1>", "", page, flags=re.S)
    assert not re.search(r"\b(nan|NaN|None)\b", markup)   # case-sensitive: svg uses fill="none"


def test_links(page):
    for link in ('href="/cities/"', 'href="/cities/bengaluru/"', 'href="/start.txt"', 'href="/open-work/"'):
        assert link in page, link


def test_no_other_site_except_author_link(page):
    found = set(re.findall(r"https?://(?:www\.)?dogl\.uk[^\"' <)]*", page))
    assert found == {"https://dogl.uk", "https://dogl.uk/about/"}
    assert "posts_assets" not in page and "/assets/css/" not in page
    for f in ("airhealth.css", "film.html", "card.html"):
        assert "dogl.uk" not in (SRC / f).read_text(), f


def test_every_number_in_the_prose_is_in_air_json(page):
    known = set()
    for v in leaves(AIR):
        known.update(re.findall(r"\d+(?:\.\d+)?", str(v).replace(",", "")))
    body = []
    for tag, t in prose(page):
        if tag == "h2" and t == "Run it":     # after this: the commands and the hand-written notebook
            break
        body.append(t)
    text = " ".join(body)
    # wording that is not a result: the two standards, the paper's year, clock times, the unit
    for fixed in ("PM2.5", "Lan et al. 2022", "8 pm", "2 pm", "standard of 40", "guideline of 5"):
        text = text.replace(fixed, "")
    missing = [n for n in re.findall(r"\d+(?:\.\d+)?", text.replace(",", "")) if n not in known]
    assert not missing, missing


def test_prose_follows_the_data():
    data = copy.deepcopy(AIR)
    data["toll"]["pm25"] = "123.4"
    data["cities"]["dirtiest"] = "Testville"
    scope = render.load_scope()
    scope["data"]["air"] = data
    scope["content"] = render.render_template(SRC / "index.html", scope)
    out = render.render_template(SRC / "layout.html", scope)
    assert "read 123.4 μg/m³" in out and "from Testville at" in out and "read 27.9" not in out


def test_assets_the_page_loads_exist(page):
    built = {p.relative_to(STATIC).as_posix() for p in STATIC.rglob("*") if p.is_file()}
    built |= {"assets/airhealth.css", "start.txt"}
    for ref in set(re.findall(r'(?:href|src)="/([^"#?]*)"', page)):
        if ref and not ref.startswith(("cities/", "open-work")):
            assert ref in built, ref
    for ref in re.findall(r'url\("/([^"]+)"\)', (SRC / "airhealth.css").read_text()):
        assert ref in built, ref


def test_card_and_film_ship():
    assert (STATIC / "assets/img/air-apocalypse-ladder.png").stat().st_size > 50_000
    assert (STATIC / "assets/media/air-apocalypse-film.mp4").stat().st_size > 500_000


def test_engine():
    s = {"d": {"a": 3, "xs": [1, 2], "e": "", "k:v": 7}, "t": "x"}

    def r(src):
        return render.render_nodes(render.parse(src), s)

    assert r("{{ d.a }}-{{ d.xs | size }}-{{ d[\"k:v\"] }}") == "3-2-7"
    assert r("{% if d.e %}A{% elsif d.a > 2 and t == \"x\" %}B{% else %}C{% endif %}") == "B"
    assert r("{% if d.missing %}A{% else %}C{% endif %}") == "C"
    assert r("a  {%- assign z = d.a -%}  b{{ z }}") == "ab3"
    with pytest.raises(render.TemplateError):
        r("{{ d.nope }}")
