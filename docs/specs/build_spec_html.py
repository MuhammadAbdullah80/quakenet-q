"""Render the design spec markdown as a formatted, self-contained HTML document.

    python docs/specs/build_spec_html.py

Requires pandoc on PATH. The markdown file stays the single source of truth;
re-run this script after every edit so the HTML never drifts from it.
"""
from __future__ import annotations

import html
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE / "2026-11-12-quakenet-q-agent-design.md"
OUT = HERE / "quakenet-q-agent-design.html"


def md_to_html(md: str) -> str:
    return subprocess.run(["pandoc", "-f", "gfm", "-t", "html5", "--no-highlight"],
                          input=md, capture_output=True, text=True, encoding="utf-8", check=True).stdout


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", text).lower()).strip("-")


def split_front_matter(md: str) -> tuple[str, dict[str, str], str]:
    """Pull the title and the **Key:** metadata lines off the top of the document."""
    title = re.search(r"^# (.+)$", md, re.M).group(1)
    meta = dict(re.findall(r"^\*\*(\w+):\*\*\s*(.+?)\s*$", md.split("---", 1)[0], re.M))
    body = md.split("\n---\n", 1)[1]
    return title, meta, body


def inline(md_fragment: str) -> str:
    """Render a short markdown fragment (bold, code) without a wrapping <p>."""
    out = md_to_html(md_fragment).strip()
    return re.sub(r"^<p>(.*)</p>$", r"\1", out, flags=re.S)


def enhance(body: str) -> str:
    # requirement IDs at the start of list items -> tagged label
    body = re.sub(r"<li>((?:FR|NFR|EC|OS|R)-\d+): ",
                  lambda m: f'<li class="req" id="{m.group(1).lower()}"><span class="rid">{m.group(1)}</span> ', body)
    # RFC 2119 keywords
    body = re.sub(r"\b(MUST NOT|MUST|SHOULD NOT|SHOULD|MAY)\b", r'<span class="kw kw-\1">\1</span>', body)
    body = body.replace('kw-MUST NOT', 'kw-MUSTNOT').replace('kw-SHOULD NOT', 'kw-SHOULDNOT')
    # cross-references to requirement IDs elsewhere -> links
    def link(m: re.Match) -> str:
        rid = m.group(0)
        return f'<a class="xref" href="#{rid.lower()}">{rid}</a>'
    parts = re.split(r'(<span class="rid">.*?</span>|<h[1-6][^>]*>.*?</h[1-6]>|<pre\b.*?</pre>)', body, flags=re.S)
    body = "".join(p if i % 2 else re.sub(r"\b(?:FR|NFR|EC|OS|R|AC)-\d+\b", link, p) for i, p in enumerate(parts))
    # acceptance criteria: h3 + Given/When/Then list -> card
    def ac_card(m: re.Match) -> str:
        num = m.group(1)
        title, refs = " ".join(m.group(2).split()), " ".join(m.group(3).split())
        refs = re.sub(r"\b(?:FR|NFR|EC|OS|R)-\d+\b", link, refs)
        rows = re.findall(r"<li><strong>(Given|When|Then)</strong>\s*(.*?)</li>", m.group(4), re.S)
        cells = "".join(f'<div class="gwt-k">{k}</div><div class="gwt-v">{v.strip()}</div>' for k, v in rows)
        return (f'<article class="ac" id="ac-{num}"><header><span class="rid">AC-{num}</span>'
                f'<h3>{title}</h3><span class="refs">{refs}</span></header><div class="gwt">{cells}</div></article>')
    body = re.sub(r'<h3\s+id="[^"]*">AC-(\d+):\s+(.*?)\s+\(([^()]*)\)</h3>\s*<ul>(.*?)</ul>', ac_card, body, flags=re.S)
    # section ids for the sidebar
    body = re.sub(r"<h2[^>]*>(.*?)</h2>", lambda m: f'<h2 id="{slug(m.group(1))}">{m.group(1)}</h2>', body)
    # wide tables scroll inside their own keyboard-reachable box, named after the nearest label above them
    def wrap_table(m: re.Match) -> str:
        before = body[:m.start()]
        labels = re.findall(r"<h[23][^>]*>(.*?)</h[23]>|<p><strong>(.*?)</strong>", before, re.S)
        name = next((a or b for a, b in reversed(labels) if a or b), "Table")
        name = html.escape(" ".join(re.sub(r"<[^>]+>", "", name).split()), quote=True)
        return (f'<div class="table-wrap" role="region" tabindex="0" aria-label="{name}">'
                f'<table aria-label="{name}">')
    body = re.sub(r"<table>", wrap_table, body).replace("</table>", "</table></div>")
    body = body.replace("<hr />", "")
    return body


def sidebar(body: str, md: str) -> str:
    counts = {"functional-requirements": ("FR", r"^- FR-\d+:"), "non-functional-requirements": ("NFR", r"^- NFR-\d+:"),
              "acceptance-criteria": ("AC", r"^### AC-\d+:"), "edge-cases": ("EC", r"^- EC-\d+:"),
              "out-of-scope": ("OS", r"^- OS-\d+:"), "risks-and-open-checks": ("R", r"^- R-\d+:")}
    items = []
    for sid, text in re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', body):
        badge = ""
        if sid in counts:
            badge = f'<span class="count">{len(re.findall(counts[sid][1], md, re.M))}</span>'
        items.append(f'<li><a href="#{sid}">{text}</a>{badge}</li>')
    return "\n".join(items)


# A seismogram: quiet background, a mainshock, then decaying aftershocks.
def trace_path(width: int = 1200, height: int = 90) -> str:
    import math, random
    rnd = random.Random(7)
    mid, pts = height / 2, []
    for x in range(0, width + 1, 3):
        t = x / width
        amp = 1.2
        if 0.18 < t:
            amp += 38 * math.exp(-(t - 0.18) * 26) if t > 0.18 else 0
        for at, size in ((0.42, 14), (0.55, 9), (0.66, 11), (0.78, 6), (0.88, 7)):
            if t > at:
                amp += size * math.exp(-(t - at) * 140)
        y = mid + amp * math.sin(x * 0.9 + rnd.uniform(-0.6, 0.6)) * rnd.uniform(0.6, 1.0)
        pts.append(f"{x},{y:.1f}")
    return "M" + " L".join(pts)


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>QuakeNet-Q Agent Design</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Sans:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root {{
  --paper: #f4f6f5;      /* seismograph drum paper */
  --sheet: #ffffff;
  --ink: #17212b;        /* basalt */
  --ink-soft: #4d5965;
  --rule: #d4dbde;
  --mark: #b3261e;       /* red time-mark ink: requirement IDs only */
  --survey: #0b6461;     /* geologic-survey teal: links */
  --must: #17212b; --should: #8a5a00; --may: #4d5965;
  --display: "IBM Plex Sans Condensed", "Arial Narrow", system-ui, sans-serif;
  --body: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Consolas, monospace;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; scroll-padding-top: 24px; }}
@media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior: auto; }} }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 16px/1.65 var(--body); }}
a {{ color: var(--survey); text-underline-offset: 2px; }}
a:focus-visible, summary:focus-visible, .table-wrap:focus-visible {{ outline: 3px solid var(--survey); outline-offset: 2px; border-radius: 2px; }}
.skip {{ position: absolute; left: -9999px; }}
.skip:focus {{ left: 16px; top: 16px; background: var(--sheet); padding: 8px 12px; z-index: 10; }}

/* masthead */
.mast {{ background: var(--sheet); border-bottom: 1px solid var(--rule); }}
.mast-inner {{ max-width: 1240px; margin: 0 auto; padding: 40px 32px 0; }}
.eyebrow {{ font: 600 13px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--ink-soft); margin: 0 0 14px; }}
.mast h1 {{ font: 700 clamp(34px, 5vw, 56px)/1.02 var(--display); letter-spacing: -.01em; margin: 0; }}
.mast .lede {{ max-width: 720px; color: var(--ink-soft); font-size: 18px; margin: 14px 0 0; }}
.meta {{ display: flex; flex-wrap: wrap; gap: 8px 28px; margin: 22px 0 0; padding: 0; list-style: none; font-size: 14px; }}
.meta dt {{ font: 600 11px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--ink-soft); margin-bottom: 4px; }}
.meta dd {{ margin: 0; }}
.status {{ display: inline-block; font: 600 12px/1 var(--mono); padding: 5px 9px; border: 1.5px solid var(--should); color: var(--should); border-radius: 3px; text-transform: uppercase; letter-spacing: .06em; }}
.trace {{ display: block; width: 100%; height: 90px; margin-top: 26px; }}
.trace path {{ fill: none; stroke: var(--ink); stroke-width: 1.2; }}
.trace .tick {{ stroke: var(--mark); stroke-width: 1; }}
.trace text {{ font: 600 10px var(--mono); fill: var(--mark); letter-spacing: .06em; }}

/* layout */
.layout {{ max-width: 1240px; margin: 0 auto; padding: 32px; display: grid; grid-template-columns: 250px minmax(0, 1fr); gap: 48px; }}
nav.toc {{ position: sticky; top: 24px; align-self: start; max-height: calc(100vh - 48px); overflow: auto; }}
nav.toc h2 {{ font: 600 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--ink-soft); margin: 4px 0 12px; }}
nav.toc ol {{ list-style: none; margin: 0; padding: 0; border-left: 1px solid var(--rule); }}
nav.toc li {{ display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }}
nav.toc a {{ display: block; padding: 6px 0 6px 14px; margin-left: -1px; border-left: 2px solid transparent; color: var(--ink); text-decoration: none; font-size: 14.5px; line-height: 1.3; }}
nav.toc a:hover, nav.toc a.on {{ border-left-color: var(--mark); }}
nav.toc .count {{ font: 12px var(--mono); color: var(--ink-soft); }}
main {{ background: var(--sheet); border: 1px solid var(--rule); border-radius: 4px; padding: 8px 56px 56px; min-width: 0; }}
main > h2 {{ font: 700 30px/1.15 var(--display); margin: 56px 0 18px; padding-top: 22px; border-top: 1px solid var(--rule); }}
main > h2:first-child {{ border-top: 0; margin-top: 28px; }}
main h3 {{ font: 600 20px/1.3 var(--display); margin: 32px 0 10px; }}
main p, main li {{ max-width: 76ch; }}
main ul, main ol {{ padding-left: 22px; }}
main li {{ margin: 6px 0; }}
code {{ font: 0.88em var(--mono); background: #eef2f2; padding: 1px 5px; border-radius: 3px; }}
pre {{ font: 13px/1.5 var(--mono); background: #f7f9f8; border: 1px solid var(--rule); border-left: 3px solid var(--ink);
       padding: 18px 20px; overflow-x: auto; border-radius: 3px; }}
pre code {{ background: none; padding: 0; font-size: inherit; }}
.table-wrap {{ overflow-x: auto; margin: 16px 0 24px; border: 1px solid var(--rule); border-radius: 3px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 14.5px; }}
th {{ text-align: left; font: 600 12px/1.3 var(--mono); letter-spacing: .05em; text-transform: uppercase; color: var(--ink-soft); background: #f7f9f8; }}
th, td {{ padding: 10px 14px; border-bottom: 1px solid var(--rule); vertical-align: top; }}
tr:last-child td {{ border-bottom: 0; }}

/* requirements */
li.req {{ list-style: none; position: relative; margin: 14px 0 14px -22px; padding-left: 78px; scroll-margin-top: 24px; }}
li.req > .rid {{ position: absolute; left: 0; top: 2px; }}
.rid {{ font: 600 12.5px/1.6 var(--mono); color: var(--mark); white-space: nowrap; }}
.kw {{ font: 600 11.5px/1 var(--mono); letter-spacing: .06em; padding: 2px 5px; border-radius: 2px; border: 1px solid currentColor; vertical-align: 1px; }}
.kw-MUST, .kw-MUSTNOT {{ color: var(--must); }}
.kw-SHOULD, .kw-SHOULDNOT {{ color: var(--should); }}
.kw-MAY {{ color: var(--may); border-style: dashed; }}
a.xref {{ font: 600 0.86em var(--mono); color: var(--survey); text-decoration: none; border-bottom: 1px dotted currentColor; }}
a.xref:hover {{ border-bottom-style: solid; }}

/* acceptance criteria */
.ac {{ border: 1px solid var(--rule); border-radius: 4px; margin: 14px 0; scroll-margin-top: 24px; }}
.ac header {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; padding: 12px 16px; border-bottom: 1px solid var(--rule); background: #f9fbfa; }}
.ac h3 {{ margin: 0; font: 600 17px/1.3 var(--display); flex: 1 1 260px; }}
.ac .refs {{ font: 12px var(--mono); color: var(--ink-soft); }}
.gwt {{ display: grid; grid-template-columns: 74px 1fr; }}
.gwt-k {{ font: 600 12px/1.6 var(--mono); text-transform: uppercase; letter-spacing: .06em; color: var(--ink-soft); padding: 9px 0 9px 16px; }}
.gwt-v {{ padding: 8px 16px 8px 0; font-size: 15px; }}
.gwt-k:not(:nth-last-child(2)), .gwt-v:not(:last-child) {{ border-bottom: 1px dashed var(--rule); }}

footer.doc {{ max-width: 1240px; margin: 0 auto; padding: 0 32px 48px; color: var(--ink-soft); font-size: 13px; }}

@media (max-width: 960px) {{
  .layout {{ grid-template-columns: minmax(0, 1fr); padding: 16px; gap: 16px; }}
  .trace text, .trace .tick {{ display: none; }}
  nav.toc {{ position: static; max-height: none; background: var(--sheet); border: 1px solid var(--rule); border-radius: 4px; padding: 14px 16px; }}
  main {{ padding: 4px 18px 32px; }}
  .mast-inner {{ padding: 28px 16px 0; }}
  li.req {{ padding-left: 0; margin-left: -22px; }}
  li.req > .rid {{ position: static; display: block; }}
  .gwt {{ grid-template-columns: 1fr; }}
  .gwt-k {{ padding: 8px 14px 0; border-bottom: 0 !important; }}
  .gwt-v {{ padding: 0 14px 8px; }}
  footer.doc {{ padding: 0 16px 32px; }}
}}
@media print {{
  body {{ background: #fff; font-size: 11pt; }}
  nav.toc, .skip {{ display: none; }}
  .layout {{ display: block; padding: 0; }}
  main {{ border: 0; padding: 0; }}
  .ac, pre, table {{ break-inside: avoid; }}
  a.xref {{ border: 0; color: var(--ink); }}
}}
</style>
</head>
<body>
<a class="skip" href="#content">Skip to content</a>
<header class="mast">
  <div class="mast-inner">
    <p class="eyebrow">Design specification · Disaster Response · Qiskit</p>
    <h1>{title}</h1>
    <p class="lede">An autonomous agent that decides where the first portable seismometers go after a major earthquake, with a quantum optimisation algorithm as its decision step.</p>
    <dl class="meta">
      <div><dt>Status</dt><dd><span class="status">{status}</span></dd></div>
      <div><dt>Date</dt><dd>{date}</dd></div>
      <div><dt>Author</dt><dd>{author}</dd></div>
      <div><dt>Reviewers</dt><dd>{reviewers}</dd></div>
      <div><dt>Supersedes</dt><dd>{supersedes}</dd></div>
    </dl>
  </div>
  <svg class="trace" viewBox="0 0 1200 90" preserveAspectRatio="none" role="img" aria-label="Seismogram trace: a quiet background, a large mainshock, then smaller decaying aftershocks">
    <line class="tick" x1="216" y1="4" x2="216" y2="18"/><text x="222" y="14">MAINSHOCK</text>
    <line class="tick" x1="504" y1="4" x2="504" y2="18"/><text x="510" y="14">T0 PLAN</text>
    <line class="tick" x1="792" y1="4" x2="792" y2="18"/><text x="798" y="14">RE-PLAN</text>
    <path d="{trace}"/>
  </svg>
</header>
<div class="layout">
  <nav class="toc" aria-label="Contents">
    <h2>Contents</h2>
    <ol>
{toc}
    </ol>
  </nav>
  <main id="content">
{body}
  </main>
</div>
<footer class="doc">Generated from <code>{src}</code> by <code>docs/specs/build_spec_html.py</code>. The markdown file is the source of truth.</footer>
<script>
// highlight the contents entry for the section in view (enhancement only)
const links = [...document.querySelectorAll('nav.toc a')];
const map = new Map(links.map(a => [a.getAttribute('href').slice(1), a]));
const io = new IntersectionObserver(es => es.forEach(e => {{
  if (e.isIntersecting) {{ links.forEach(a => a.classList.remove('on')); map.get(e.target.id)?.classList.add('on'); }}
}}), {{ rootMargin: '0px 0px -75% 0px' }});
document.querySelectorAll('main > h2[id]').forEach(h => io.observe(h));
</script>
</body>
</html>
"""


def main() -> None:
    md = SRC.read_text(encoding="utf-8")
    title, meta, body_md = split_front_matter(md)
    body = enhance(md_to_html(body_md))
    page = TEMPLATE.format(
        title=html.escape(title), status=html.escape(meta.get("Status", "")), date=html.escape(meta.get("Date", "")),
        author=html.escape(meta.get("Author", "")), reviewers=html.escape(meta.get("Reviewers", "")),
        supersedes=inline(meta.get("Supersedes", "")), trace=trace_path(), toc=sidebar(body, md),
        body=body, src=SRC.name)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT} ({len(page) // 1024} KB)")


if __name__ == "__main__":
    main()
