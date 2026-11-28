#!/usr/bin/env python3
"""Render the landing page: site/src/index.html in site/src/layout.html, with site/data/air.json.

Standard library only. The template speaks the small part of Liquid the page uses, so the text
reads as it did when Jekyll rendered it:

    {{ a.toll.pm25 }}                      a value (dotted path; ["key"] for keys with punctuation)
    {{ a.city_pages | size }}              the one filter used
    {%- assign m = a.ladder.measures -%}   a variable (the dashes trim the whitespace beside the tag)
    {% if x and y != "" %}...{% else %}...{% endif %}
    {% include fig/toll.html %}            a file from site/src/ (includes may use tags too)

`data.air` is site/data/air.json and `page.*` is site/src/page.json. A value that is missing,
None, false or "" counts as false in an if (Liquid treats "" as true; nothing here relies on that).
An unknown name in {{ }} is an error, so a number cannot silently drop out of the page.

    python site/render.py [outdir]        # writes outdir/index.html (default site/dist)
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"

TOKEN = re.compile(r"(\{\{-?.*?-?\}\}|\{%-?.*?-?%\})", re.S)


class TemplateError(Exception):
    pass


def lookup(path: str, scope: dict):
    """Resolve a dotted path against the scope. Raises KeyError for a name that is not there."""
    if not re.fullmatch(r'[A-Za-z_]\w*(\.\w+|\["[^"]+"\])*', path):
        raise TemplateError(f"cannot read {path!r}")
    parts = [m.group(1) or m.group(2) for m in re.finditer(r'\["([^"]+)"\]|(?:^|\.)(\w+)', path)]
    cur = scope
    for p in parts:
        if p == "size" and isinstance(cur, (list, dict, str)):
            cur = len(cur)
        elif isinstance(cur, dict):
            cur = cur[p]
        elif isinstance(cur, list) and p.isdigit():
            cur = cur[int(p)]
        else:
            raise KeyError(path)
    return cur


def soft(path: str, scope: dict):
    try:
        return lookup(path, scope)
    except KeyError:
        return None


def condition(expr: str, scope: dict) -> bool:
    """`a and b != "" or c > 1`: paths, string and number literals, == != > <, and/or."""
    def atom(tok: str):
        tok = tok.strip()
        if re.fullmatch(r'"[^"]*"|\'[^\']*\'', tok):
            return tok[1:-1]
        if re.fullmatch(r"-?\d+(\.\d+)?", tok):
            return float(tok) if "." in tok else int(tok)
        return soft(tok, scope)

    def compare(term: str):
        m = re.fullmatch(r"(.+?)\s*(==|!=|>=|<=|>|<)\s*(.+)", term.strip())
        if not m:
            return bool(atom(term))
        a, op, b = atom(m.group(1)), m.group(2), atom(m.group(3))
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if a is None or b is None:
            return False
        return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[op]

    return any(all(compare(t) for t in re.split(r"\s+and\s+", chunk)) for chunk in re.split(r"\s+or\s+", expr))


def parse(src: str):
    """Tokens to a tree of ("text", s), ("var", expr), ("assign", name, expr), ("include", name),
    ("if", [(cond|None, children), ...])."""
    toks = TOKEN.split(src)
    out_stack: list = [[]]
    if_stack: list = []
    trim_next = False
    for t in toks:
        if not t:
            continue
        is_tag = t.startswith("{%") or t.startswith("{{")
        if not is_tag:
            if trim_next:
                t = t.lstrip()
                trim_next = False
            out_stack[-1].append(("text", t))
            continue
        left, right = t[2] == "-", t[-3] == "-"
        if left and out_stack[-1] and out_stack[-1][-1][0] == "text":
            out_stack[-1][-1] = ("text", out_stack[-1][-1][1].rstrip())
        trim_next = right
        inner = t[2:-2].strip("-").strip()
        if t.startswith("{{"):
            out_stack[-1].append(("var", inner))
            continue
        word, _, rest = inner.partition(" ")
        rest = rest.strip()
        if word == "assign":
            name, _, expr = rest.partition("=")
            out_stack[-1].append(("assign", name.strip(), expr.strip()))
        elif word == "include":
            out_stack[-1].append(("include", rest))
        elif word == "if":
            node = ("if", [(rest, [])])
            out_stack[-1].append(node)
            if_stack.append(node)
            out_stack.append(node[1][0][1])
        elif word in ("else", "elsif"):
            node = if_stack[-1]
            node[1].append((None if word == "else" else rest, []))
            out_stack[-1] = node[1][-1][1]
        elif word == "endif":
            if_stack.pop()
            out_stack.pop()
        else:
            raise TemplateError(f"unknown tag {inner!r}")
    if if_stack or len(out_stack) != 1:
        raise TemplateError("an {% if %} is not closed")
    return out_stack[0]


def value(expr: str, scope: dict):
    path, *filters = [p.strip() for p in expr.split("|")]
    v = lookup(path, scope)
    for f in filters:
        if f != "size":
            raise TemplateError(f"unknown filter {f!r}")
        v = len(v)
    return v


def render_nodes(nodes, scope: dict) -> str:
    out = []
    for n in nodes:
        kind = n[0]
        if kind == "text":
            out.append(n[1])
        elif kind == "var":
            try:
                v = value(n[1], scope)
            except KeyError:
                raise TemplateError(f"{{{{ {n[1]} }}}} is not in the data") from None
            out.append("" if v is None else str(v))
        elif kind == "assign":
            scope[n[1]] = value(n[2], scope)
        elif kind == "include":
            out.append(render_nodes(parse((SRC / n[1]).read_text()), scope))
        elif kind == "if":
            for cond, children in n[1]:
                if cond is None or condition(cond, scope):
                    out.append(render_nodes(children, scope))
                    break
    return "".join(out)


def render_template(path: Path, scope: dict) -> str:
    return render_nodes(parse(path.read_text()), scope)


def load_scope() -> dict:
    return {"data": {"air": json.loads((HERE / "data/air.json").read_text())},
            "page": json.loads((SRC / "page.json").read_text())}


def render_page() -> str:
    scope = load_scope()
    scope["content"] = render_template(SRC / "index.html", scope)
    return render_template(SRC / "layout.html", scope)


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "dist"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(render_page())
    print("wrote", out / "index.html")
