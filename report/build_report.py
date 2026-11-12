"""Builds report/QuakeNet-Q_Report.docx.

    python report/make_diagram.py      # figures/architecture.png, figures/system.png
    python report/build_report.py      # this report

Every number comes from results/results.json (run_experiment.py), results/benchmarks.json
(run_benchmarks.py) or results/extras.json (run_extras.py). Nothing is typed in by hand except
the history of the idea (Chapter 2), which records what the team decided and when.

If Microsoft Word is installed (Windows), the script asks Word to fill in the table of contents
and also writes a PDF copy. Without Word, the contents fill in when the file is first opened.
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
R = json.loads((ROOT / "results" / "results.json").read_text())
BENCH = json.loads((ROOT / "results" / "benchmarks.json").read_text())
EXTRA = json.loads((ROOT / "results" / "extras.json").read_text())
FIG = ROOT / "figures"
OUT = ROOT / "report" / "QuakeNet-Q_Report.docx"

TEAM = ["Muhammad Abdullah", "Muhammad Hassaan-ul-Mustafa", "Rafia Ali"]
REPO = "https://github.com/MuhammadAbdullah80/quakenet-q"
CONSOLE = "https://quakenet-q.vercel.app"

# ---------------------------------------------------------------------------- palette and type
NAVY, TEAL, INK, MUTED = "1F3864", "2E75B6", "1F2933", "5A6570"
HEAD_FILL, ZEBRA, RULE = "1F3864", "F2F5F9", "BFC8D2"
NOTE_FILL = {"key": "E8F1FA", "warn": "FFF4E5", "good": "EAF5EA"}
NOTE_BAR = {"key": "2E75B6", "warn": "C55A11", "good": "3B7D23"}
BODY_FONT, HEAD_FONT = "Calibri", "Calibri"


def rgb(hexstr: str) -> RGBColor:
    return RGBColor.from_string(hexstr)


# ---------------------------------------------------------------------------- low-level XML helpers
def shade(cell, fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear"); shd.set(qn("w:color"), "auto"); shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def cell_borders(cell, **edges) -> None:
    """edges: top/bottom/left/right = (size_eighths_pt, hex) or None for no border."""
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        spec = edges.get(edge)
        if spec is None:
            el.set(qn("w:val"), "nil")
        else:
            el.set(qn("w:val"), "single"); el.set(qn("w:sz"), str(spec[0])); el.set(qn("w:color"), spec[1])
        borders.append(el)
    tcPr.append(borders)


def cell_margins(table, top=60, bottom=60, left=100, right=100) -> None:
    tblPr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for edge, v in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:w"), str(v)); el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def repeat_header(row) -> None:
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader"); el.set(qn("w:val"), "true")
    trPr.append(el)


def keep_row_together(row) -> None:
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit"); el.set(qn("w:val"), "true")
    trPr.append(el)


def para_border_bottom(p, colour=NAVY, size=12) -> None:
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    b.set(qn("w:val"), "single"); b.set(qn("w:sz"), str(size)); b.set(qn("w:space"), "4"); b.set(qn("w:color"), colour)
    bdr.append(b); pPr.append(bdr)


def add_field(paragraph, instr: str, placeholder: str = "") -> None:
    run = paragraph.add_run()
    b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin"); run._r.append(b)
    t = OxmlElement("w:instrText"); t.set(qn("xml:space"), "preserve"); t.text = instr; run._r.append(t)
    s = OxmlElement("w:fldChar"); s.set(qn("w:fldCharType"), "separate"); run._r.append(s)
    paragraph.add_run(placeholder)
    run2 = paragraph.add_run()
    e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end"); run2._r.append(e)


# ---------------------------------------------------------------------------- document set-up
doc = Document()
sec = doc.sections[0]
sec.page_height, sec.page_width = Cm(29.7), Cm(21.0)
sec.top_margin = sec.bottom_margin = Cm(2.2)
sec.left_margin = sec.right_margin = Cm(2.3)
sec.header_distance = sec.footer_distance = Cm(1.1)
TEXT_W = 21.0 - 2 * 2.3            # usable width in cm

normal = doc.styles["Normal"]
normal.font.name, normal.font.size, normal.font.color.rgb = BODY_FONT, Pt(10.5), rgb(INK)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.15

for name, size, colour, before, after in (("Title", 30, NAVY, 0, 4), ("Heading 1", 17, NAVY, 18, 8),
                                          ("Heading 2", 13, TEAL, 14, 4), ("Heading 3", 11, INK, 10, 3)):
    st = doc.styles[name]
    st.font.name, st.font.size, st.font.bold, st.font.color.rgb = HEAD_FONT, Pt(size), True, rgb(colour)
    st.element.rPr.rFonts.set(qn("w:asciiTheme"), "") if False else None
    rf = st.element.rPr.rFonts
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        rf.set(qn(attr), HEAD_FONT)
    for attr in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        if rf.get(qn(attr)) is not None:
            del rf.attrib[qn(attr)]
    st.paragraph_format.space_before, st.paragraph_format.space_after = Pt(before), Pt(after)
    st.paragraph_format.keep_with_next = True
doc.styles["Heading 1"].paragraph_format.page_break_before = False

for name in ("List Bullet", "List Number"):
    st = doc.styles[name]
    st.font.name, st.font.size = BODY_FONT, Pt(10.5)
    st.paragraph_format.space_after = Pt(3)

cap = doc.styles.add_style("Caption QN", 1)
cap.base_style = doc.styles["Normal"]
cap.font.size, cap.font.italic, cap.font.color.rgb = Pt(9), True, rgb(MUTED)
cap.paragraph_format.space_after = Pt(10)
cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER

for lvl, size, indent in ((1, 10.5, 0.0), (2, 9.5, 0.5)):
    st = doc.styles.add_style(f"toc {lvl}", 1)          # Word's built-in name is lower case
    st.element.set(qn("w:styleId"), f"TOC{lvl}")        # ...and the id Word looks for
    st.element.set(qn("w:customStyle"), "0")
    st.base_style = doc.styles["Normal"]
    st.font.size, st.font.bold = Pt(size), lvl == 1
    st.paragraph_format.space_before = Pt(4 if lvl == 1 else 0)
    st.paragraph_format.space_after = Pt(0)
    st.paragraph_format.line_spacing = 1.0
    st.paragraph_format.left_indent = Cm(indent)

COUNT = {"Figure": 0, "Table": 0}


# ---------------------------------------------------------------------------- content helpers
def para(text: str = "", *, bold=False, italic=False, size=None, colour=None, align=None, after=None, style=None):
    p = doc.add_paragraph(style=style)
    if text:
        rich(p, text, bold=bold, italic=italic, size=size, colour=colour)
    if align is not None:
        p.alignment = align
    if after is not None:
        p.paragraph_format.space_after = Pt(after)
    return p


def rich(p, text: str, *, bold=False, italic=False, size=None, colour=None):
    """Adds text to p; **double stars** mark bold spans."""
    parts = text.split("**")
    for i, part in enumerate(parts):
        if not part:
            continue
        r = p.add_run(part)
        r.bold = bold or (i % 2 == 1)
        r.italic = italic
        if size:
            r.font.size = Pt(size)
        if colour:
            r.font.color.rgb = rgb(colour)
    return p


def bullets(items, style="List Bullet"):
    for it in items:
        rich(doc.add_paragraph(style=style), it)


def caption(kind: str, text: str):
    COUNT[kind] += 1
    p = doc.add_paragraph(style="Caption QN")
    r = p.add_run(f"{kind} {COUNT[kind]}. "); r.bold = True
    p.add_run(text)
    return COUNT[kind]


def figure(name: str, text: str, width_cm: float = 15.5):
    doc.add_picture(str(FIG / name), width=Cm(width_cm))
    pic = doc.paragraphs[-1]
    pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pic.paragraph_format.keep_with_next = True
    pic.paragraph_format.space_after = Pt(2)
    return caption("Figure", text)


def table(header, rows, widths, *, title=None, align=None, size=9, bold_first=False):
    """A styled table: navy header, zebra rows, thin rules, repeating header row.

    widths in cm (they are scaled to the text width); align: list of 'l'/'c'/'r' per column."""
    if title:
        caption_above = doc.add_paragraph(style="Caption QN")
        COUNT["Table"] += 1
        r = caption_above.add_run(f"Table {COUNT['Table']}. "); r.bold = True
        caption_above.add_run(title)
        caption_above.alignment = WD_ALIGN_PARAGRAPH.LEFT
        caption_above.paragraph_format.space_after = Pt(3)
        caption_above.paragraph_format.keep_with_next = True
    scale = TEXT_W / sum(widths)
    widths = [w * scale for w in widths]
    align = align or ["l"] * len(header)
    amap = {"l": WD_ALIGN_PARAGRAPH.LEFT, "c": WD_ALIGN_PARAGRAPH.CENTER, "r": WD_ALIGN_PARAGRAPH.RIGHT}
    t = doc.add_table(rows=1, cols=len(header))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    cell_margins(t)
    for i, (cell, text) in enumerate(zip(t.rows[0].cells, header)):
        shade(cell, HEAD_FILL)
        cell_borders(cell, top=(4, HEAD_FILL), bottom=(4, HEAD_FILL), left=None, right=None)
        p = cell.paragraphs[0]
        r = p.add_run(text); r.bold = True; r.font.size = Pt(size); r.font.color.rgb = rgb("FFFFFF")
        p.alignment = amap[align[i]]
        p.paragraph_format.space_after = Pt(0)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    repeat_header(t.rows[0])
    for c in t.rows[0].cells:
        c.paragraphs[0].paragraph_format.keep_with_next = True
    for ri, row in enumerate(rows):
        cells = t.add_row().cells
        keep_row_together(t.rows[-1])
        for i, (cell, text) in enumerate(zip(cells, row)):
            if ri % 2 == 1:
                shade(cell, ZEBRA)
            cell_borders(cell, top=None, bottom=(4, RULE), left=None, right=None)
            p = cell.paragraphs[0]
            rich(p, str(text), size=size, bold=bold_first and i == 0)
            p.alignment = amap[align[i]]
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            if ri == 0 and len(rows) > 1:
                p.paragraph_format.keep_with_next = True
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    for row in t.rows:
        for cell, w in zip(row.cells, widths):
            cell.width = Cm(w)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(4)
    return t


def note(title: str, lines, kind: str = "key"):
    """A call-out box: tinted background with a coloured bar on the left."""
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell_margins(t, 100, 100, 180, 140)
    c = t.rows[0].cells[0]
    c.width = Cm(TEXT_W)
    shade(c, NOTE_FILL[kind])
    cell_borders(c, top=None, bottom=None, right=None, left=(36, NOTE_BAR[kind]))
    p = c.paragraphs[0]
    r = p.add_run(title); r.bold = True; r.font.color.rgb = rgb(NOTE_BAR[kind]); r.font.size = Pt(10.5)
    p.paragraph_format.space_after = Pt(3)
    for line in ([lines] if isinstance(lines, str) else lines):
        q = c.add_paragraph()
        rich(q, line, size=10)
        q.paragraph_format.space_after = Pt(2)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def h1(text): return doc.add_heading(text, 1)
def h2(text): return doc.add_heading(text, 2)
def h3(text): return doc.add_heading(text, 3)


def page_break():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def pct(x, d=1): return f"{100 * x:.{d}f}%"


# ---------------------------------------------------------------------------- numbers from the scripts
I, F, Q, B, M = R["instance"], R["formulation"], R["qaoa"], R["blur"], R["methods"]
QAOA = M["Hybrid QAOA (XY mixer)"]
EXPERT = M["Expert rule (azimuthal gap)"]
LT = R["location_test"]
FID = {f["order"]: f for f in F["fidelity"]}
RUNS = Q["runs"]
LAYERS = sorted({r["reps"] for r in RUNS})


def stats(key, reps):
    v = [r[key] for r in RUNS if r["reps"] == reps]
    return float(np.mean(v)), float(min(v)), float(max(v))


UNI = Q["uniform_p_opt"]
N_RUNS, N_EXACT = len(RUNS), sum(r["xy_final_is_exact"] for r in RUNS)
P_BY_LAYER = {p: stats("xy_p_opt", p)[0] for p in LAYERS}
LAM300 = next(s for s in F["lam_sweep"] if s["lam"] == 300)
SITES = "{" + ", ".join(map(str, QAOA["sites"])) + "}"
DEPTH = {p: stats("xy_depth", p)[0] for p in LAYERS}
PEN_DEPTH = {p: stats("pen_depth", p)[0] for p in LAYERS}

EV = [e for e in BENCH["events"] if not e.get("skipped")]
SKIPPED = [e for e in BENCH["events"] if e.get("skipped")]
FINAL_EXACT = {k: sum(e["variants"][k]["final_exact"] for e in EV) for k in ("mean-cold", "cvar-cold", "cvar-warm")}
N_BENCH_RUNS = sum(e["variants"]["cvar-cold"]["runs"] for e in EV)
WINS = [e for e in EV if e["gain_over_expert"]["exact"]["plain_pct"] > 0]
WORST = min(EV, key=lambda e: e["gain_over_expert"]["exact"]["plain_pct"])
BEST_P = max(v["p_best_mean"] for e in EV for v in e["variants"].values())

NOISE = EXTRA["noise"]
NOISE_PTS = NOISE["points"]
N_CLEAN, N_1PC = NOISE_PTS[0], next(p for p in NOISE_PTS if abs(p["gate_error"] - 0.01) < 1e-12)
REPLAY = EXTRA["replay"]
REPLANS = [s for s in REPLAY["steps"] if s["stage"] in ("first_plan", "replan")]


# ============================================================================ cover page
for _ in range(5):
    para(after=6)
p = para("QISKIT FALL FEST 2026  ·  HACKATHON SUBMISSION", bold=True, size=10, colour=TEAL, after=10)
p = doc.add_paragraph(style="Title")
p.add_run("QuakeNet-Q")
p = para("An autonomous agent that uses quantum optimisation to decide where the first portable "
         "seismometers go after a major earthquake", size=15, colour=INK, after=4)
para_border_bottom(p, NAVY, 18)
para(after=14)
cover = [("Domain", "Disaster Response"),
         ("Team", ", ".join(TEAM)),
         ("Quantum method", "Dicke-state, XY-mixer QAOA in Qiskit 2.6.2, trained on CVaR, checked by exact search"),
         ("Data", "Real USGS aftershock catalogues and IRIS station lists; six earthquakes"),
         ("Code", REPO),
         ("Live console", CONSOLE),
         ("Date", date(2026, 11, 12).strftime("%d %B %Y"))]
t = doc.add_table(rows=0, cols=2)
cell_margins(t, 50, 50, 0, 100)
for k, v in cover:
    row = t.add_row().cells
    row[0].width, row[1].width = Cm(3.6), Cm(TEXT_W - 3.6)
    for c in row:
        cell_borders(c, top=None, bottom=(4, RULE), left=None, right=None)
    r = row[0].paragraphs[0].add_run(k.upper()); r.bold = True; r.font.size = Pt(8.5); r.font.color.rgb = rgb(MUTED)
    r = row[1].paragraphs[0].add_run(v); r.font.size = Pt(10.5)
    for c in row:
        c.paragraphs[0].paragraph_format.space_after = Pt(0)
for _ in range(6):
    para(after=6)
note("In one paragraph",
     f"After a large earthquake, response teams have hours to decide where a handful of portable seismometers go. "
     f"QuakeNet-Q watches the USGS feed, starts itself, builds an exact score for every possible network, lets a "
     f"quantum circuit choose {I['k']} of {I['candidates']} sites, checks the choice against every alternative, and "
     f"re-plans hourly as aftershocks arrive. On the 2019 Ridgecrest earthquake the quantum step found the best "
     f"network in {N_EXACT} of {N_RUNS} runs. It is a proof of concept: no quantum speedup is claimed, and the "
     f"limitations in Chapter 9 are part of the result.", "key")

# ---------------------------------------------------------------------------- header and footer (body section)
body = doc.add_section(WD_SECTION.NEW_PAGE)
body.different_first_page_header_footer = False
doc.sections[0].different_first_page_header_footer = True
body.header.is_linked_to_previous = False
body.footer.is_linked_to_previous = False
hp = body.header.paragraphs[0]
hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
r = hp.add_run("QuakeNet-Q  ·  Qiskit Fall Fest 2026  ·  Disaster Response")
r.font.size, r.font.color.rgb = Pt(8.5), rgb(MUTED)
para_border_bottom(hp, RULE, 4)
fp = body.footer.paragraphs[0]
fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
for piece in ("Page ", ("PAGE", "1"), " of ", ("NUMPAGES", "1")):
    if isinstance(piece, tuple):
        add_field(fp, piece[0], piece[1])
    else:
        fp.add_run(piece)
for r in fp.runs:
    r.font.size, r.font.color.rgb = Pt(8.5), rgb(MUTED)

# ============================================================================ contents
p = para("Contents", bold=True, size=17, colour=NAVY, after=10)
toc = doc.add_paragraph()
add_field(toc, 'TOC \\o "1-2" \\h \\z \\u', "Right-click and choose Update Field to show the contents.")
page_break()

# ============================================================================ executive summary
h1("Executive summary")
para("**The problem.** When a major earthquake strikes, the permanent seismic network is usually too sparse to "
     "locate the thousands of aftershocks that follow. Teams therefore rush a few portable seismometers into the "
     "field within hours. Where those instruments go decides how sharply the aftershocks can be located, and sharp "
     "locations show which faults are still active, which feeds aftershock forecasts and decisions about where "
     "rescuers and residents are safe. In the published deployment reports we found, the sites are chosen by expert "
     "judgement and simple rules, under time pressure.")
para("**What we built.** QuakeNet-Q is an automated program (not an AI or chatbot) that makes this decision and keeps "
     "it up to date. It reads the USGS feed, starts itself when a qualifying earthquake occurs, plans a first network "
     "within minutes, then checks every hour whether the aftershocks have moved and re-plans if they have. Every plan "
     "is made by a quantum algorithm written in Qiskit and checked against an exact search over all possible "
     "networks. A web console lets anyone test each part by hand.")
para("**Why the quantum part is real work.** The choice of sites is made by the quantum circuit, not decorated by "
     "it. We encode the seismological score exactly (all "
     f"{FID[4]['terms']} terms up to groups of four sites), start the circuit in a Dicke state that holds only "
     "valid networks, and use an XY mixer that never leaves them. A classical optimiser tunes the circuit; classical "
     "code then re-scores and verifies the answer.")
table(["Question", "Result", "Source"], [
    ["Does the circuit encode the true score?", f"Yes: zero error on all {I['feasible_networks']} networks "
     f"({FID[4]['terms']} terms)", "run_experiment.py"],
    ["Does the quantum step find the best network?", f"{N_EXACT} of {N_RUNS} runs on Ridgecrest; "
     f"{FINAL_EXACT['cvar-cold']} of {N_BENCH_RUNS} on five more earthquakes (CVaR)", "run_experiment.py, run_benchmarks.py"],
    ["How often does one measurement give the best network?",
     f"{pct(P_BY_LAYER[1])} to {pct(P_BY_LAYER[max(LAYERS)])} (random: {pct(UNI, 2)}); our 20% target was **missed**",
     "run_experiment.py"],
    ["Does the chosen network locate aftershocks better?",
     f"Ridgecrest: {LT['no_new_sensors_mean_km']:.2f} km with no new sensors, {EXPERT['loc_error_mean_km']:.2f} km "
     f"expert rule, **{QAOA['loc_error_mean_km']:.2f} km** our pick (simulated test)", "run_experiment.py"],
    ["Does it beat the expert rule elsewhere?",
     f"**Only on {len(WINS)} of {len(EV)} earthquakes**; {WORST['name']} was "
     f"{-WORST['gain_over_expert']['exact']['plain_pct']:.1f}% worse", "run_benchmarks.py"],
    ["Does the agent work end to end?",
     f"A 24-hour Ridgecrest replay ran in {REPLAY['seconds']:.0f} s and made {REPLAY['plans_made']} plans", "run_extras.py"],
    ["What would hardware noise do?", f"At 1% gate error the chance of the best network fell from "
     f"{pct(N_CLEAN['p_best'], 0)} to {pct(N_1PC['p_best'], 0)} (small simulated case)", "run_extras.py"],
], [5.2, 7.6, 3.6], title="Headline results. Every number is produced by a script in the repository.",
    align=["l", "l", "l"])
note("What we do not claim", [
    "No quantum speedup: with 210 possible networks a laptop checks every one in milliseconds, and greedy search also "
    "finds the optimum. The instance is kept small on purpose so that every answer can be verified.",
    "No field validation: the location test is a simulation, and live mode has not yet run during a real qualifying earthquake.",
    "The score we optimise does not always beat a simple field rule (Section 8.1). Better placement on those "
    "earthquakes needs a better score, not a better search.",
], "warn")

# ============================================================================ 1 problem
h1("1. The problem and who it serves")
h2("1.1 What happens after a big earthquake")
para("A large earthquake is followed by thousands of aftershocks over days and weeks, some of them damaging. "
     "Seismologists locate each aftershock from the times its waves reach different seismometers, much as a phone "
     "can be located from the timing of signals at several towers. If all the instruments sit on one side of the "
     "aftershocks, the locations are blurred. The permanent network is rarely dense enough near a new rupture, so "
     "agencies such as the USGS deploy portable instruments within hours to days (Cochran et al. 2020).")
para("Optimal network design has been studied since the 1970s (Kijko 1977; Rabinowitz & Steinberg 1990), and "
     "Hardt & Scherbaum (1994) designed optimum aftershock networks specifically. But the deployment accounts we "
     "read describe siting in qualitative terms: improve azimuthal coverage, get near-field observations, work "
     "around road access and permits. Tools that do exist, such as SN-CAST, the AuScope network design app and "
     "NetOpt3D, are built for planning a network in advance; we did not find one that starts by itself after an "
     "earthquake and re-plans as the aftershocks evolve.")
h2("1.2 Problem statement")
note("Problem statement",
     "Given the aftershocks recorded so far, the permanent stations, and a set of candidate sites, choose where to put "
     "a limited number of portable seismometers so that later aftershocks are located as accurately as possible, "
     "without wasting instruments on redundant sites and without sending crews to needlessly risky places. Do this "
     "automatically within minutes of the earthquake, and update the choice as the aftershocks move.", "key")
table(["Element", "In this project"], [
    ["Users", "Rapid-response seismology teams (for example USGS, INGV, GFZ) and the emergency managers who rely on their aftershock maps"],
    ["Limited resource", f"{I['k']} portable instruments, {I['candidates']} candidate sites"],
    ["Competing objectives", "Location accuracy against sensor redundancy against crew risk. The most informative "
     "sites lie on the active rupture, which is also the hardest and most dangerous place to work"],
    ["Decision speed", "A first plan within minutes, before many real aftershocks exist; re-plans every hour"],
    ["Success measure", "Mean error when locating later aftershocks that the planner never saw"],
], [3.6, 12.8], title="The problem in the terms of the hackathon brief.", bold_first=True)

# ============================================================================ 2 idea development
h1("2. How the idea developed")
para("The brief asks teams to choose their own problem. We did not start with seismometers. This chapter records "
     "the stages we went through, the ideas we rejected and why, and the corrections we made along the way, because "
     "the path explains several design choices that would otherwise look arbitrary.")
h2("2.1 Stages at a glance")
STAGES = [
    ["1", "Read the brief", "Translated the problem statement and the six domains into plain language; learned what "
     "QUBO, QAOA, a qubit budget and an exact baseline mean", "A shared vocabulary; the rule of thumb that a laptop "
     "simulates about 10 to 16 qubits, so one qubit per yes/no decision"],
    ["2", "First domain: UAVs and robotics", "Mapped 12 sub-areas (task allocation, routing, scheduling, charging, "
     "coverage, swarms, airspace, payload, bases, relays, warehouses, inspection) and generated ideas for each",
     "Ideas were sound but generic: drone routing and task assignment are what most teams would submit"],
    ["3", "Search for non-generic problems", "Asked for research-led problems across all six domains and tagged each as "
     "a research gap (no quantum paper found) or research-backed (a paper to build on)", "About 15 candidates, from "
     "sterile-insect release drones to proton-therapy beam angles"],
    ["4", "Shortlist and hybrid test", "Took five favourites and asked of each: can it be hybrid, with one decision type "
     "and one simple rule, scored by a physical model, small enough to verify exactly?", "Seismometer siting ranked "
     "first; intercropping dropped (too many penalty terms)"],
    ["5", "Gap check", "Asked why no seismometer placement agent exists; searched both the seismology and the quantum "
     "literature", "Classical methods since the 1990s, quantum sensor placement in other fields, no link between them"],
    ["6", "Deep research", "Three parallel searches (classical lineage, quantum gap, data and Qiskit feasibility), "
     "about 30 sources, four hypotheses tested", "Gap and data confirmed; one source we had relied on was wrong for "
     "our case (2.4); self-assessed fit with the brief 8.6 of 10"],
    ["7", "Judge's view", "Asked how a judge with no seismology would see it", "Reframed as a rescue story with a "
     "'blur' metric and a phone-location analogy; jargon kept for the report"],
    ["8", "Version 1 proof of concept", "Pairwise QUBO on real Ridgecrest data, XY-mixer QAOA, brute-force and greedy "
     "baselines", "Worked, but two weak points: an approximate score and only model-predicted errors"],
    ["9", "Critique and upgrade", "The team asked for an autonomous, self-checking agent rather than a support tool, "
     "and for the highest success rate possible", "Exact 385-term score, independent location test, CVaR training, "
     "more earthquakes, the agent loop"],
    ["10", "Technique comparison", "Compared our method with two published network-design systems "
     "(Strutz & Curtis 2024; NetOpt3D)", "Adopted hearing range and a slope filter; rejected 3D ray tracing and "
     "genetic algorithms at our size"],
    ["11", "System decisions", "Chose how the agent is hosted and tested", "FastAPI on the team laptop, a Next.js "
     "console on Vercel, no AI or LLM features anywhere"],
    ["12", "Build and measure version 2", "Built and tested the agent, ran five more earthquakes and a noise study",
     "The results in Chapters 7 and 8, including the ones that did not go our way"],
]
table(["#", "Stage", "What we did", "Outcome"], STAGES, [0.7, 3.0, 6.6, 6.1],
      title="The twelve stages from brief to submission.", align=["c", "l", "l", "l"], size=8.5)

h2("2.2 The ideas we considered")
para("In stage 3 we deliberately looked for problems that real specialists work on but that hackathon teams rarely "
     "pick. Table 4 lists the shortlist from stage 4 with the assessment we made at the time.")
table(["Idea", "Domain", "Unique", "Hard to criticise", "Impact", "Effort", "Decision"], [
    ["Aftershock seismometer network", "Disaster Response", "High", "High", "High", "Medium",
     "**Chosen.** One decision type, one rule, a physical score, a real dataset"],
    ["Proton-therapy beam angles", "Healthcare", "High", "Medium to high", "Very high", "Medium to high",
     "Runner-up. Needs a toy patient model, which invites the criticism that it is not real"],
    ["PMU placement in a power grid", "Energy", "Low", "Very high", "Medium", "Low to medium",
     "Safest, but well studied; the coverage rule needs penalty terms"],
    ["In-pipe robot entry points", "Robotics", "High", "Medium", "Medium", "Medium",
     "Pairwise overlap is only an approximation of true pipe coverage"],
    ["Intercropping layout", "Agriculture", "Medium", "Low", "Medium", "Medium",
     "Dropped: 'one crop per plot' needs many penalties that are easy to get wrong"],
], [3.2, 2.3, 1.7, 2.0, 1.7, 1.8, 4.9], title="The five shortlisted ideas (stage 4).",
    align=["l", "l", "c", "c", "c", "c", "l"], size=8.5)
para("Ideas considered earlier and set aside included sterile-insect release drones, mass-casualty triage to "
     "hospitals, kidney paired exchange, beehive placement for orchards, cold-chain vaccine carriers, drones as "
     "emergency cell towers and urban drone altitude lanes. Several were promising but either had published quantum "
     "solutions already, or needed penalty-heavy formulations that a judge could easily pick apart.")
h3("Why seismometer siting won")
bullets([
    "**It fits the quantum method naturally.** 'Choose exactly k of n sites' is one decision type with one constraint, "
    "which a Dicke state and XY mixer enforce without any penalty weight to tune.",
    "**The score is physics, not invented numbers.** The D-criterion comes from the seismology literature and can be "
    "computed from public data.",
    "**It can be judged independently.** Locating later aftershocks gives an error in kilometres that is separate "
    "from the score we optimise.",
    "**Real data is free and keyless.** USGS and IRIS returned the Ridgecrest catalogue and station list on the first try.",
    "**It is fresh.** We found no published quantum formulation of seismic station placement (Section 2.3).",
])

h2("2.3 What the research established")
table(["Hypothesis", "Verdict", "Basis"], [
    ["No published quantum (QUBO, QAOA or annealing) formulation of seismic station placement exists",
     "Not refuted", "About eight targeted searches found none. The closest work is quantum seismic inversion "
     "(Nguyen & Tura 2024) and quantum sensor placement on bridges, water networks and factories. Google Scholar and "
     "non-English literature were not searched, so we say 'first we found', never 'first ever'"],
    ["Rapid aftershock deployments choose sites by judgement and logistics, not an optimiser",
     "Leaning confirmed", "USGS Ridgecrest (Cochran et al. 2020), Italy's SISMIKO, Turkey 2023 and EarthScope RAMP "
     "describe qualitative goals only. Full texts were not all available"],
    ["The seismological score can be written in a form a quantum circuit can optimise",
     "Confirmed, then improved", "Version 1 used a pairwise approximation; version 2 uses the exact expansion up to "
     "four-site terms"],
    ["Open data is enough for a realistic instance", "Confirmed",
     "USGS ComCat and the IRIS station service, no key needed; Qiskit 2.6.2 supports every gate we need"],
], [5.2, 2.4, 8.8], title="Hypotheses tested before building (stage 6).", align=["l", "c", "l"], size=8.5)

h2("2.4 Corrections we made along the way")
para("Being honest about the project includes being honest about our own mistakes. These are the ones that changed "
     "the design:")
bullets([
    "**A borrowed formulation did not fit.** We first planned to use a mutual-information QUBO (arXiv 2407.14747). "
    "On reading it closely, it is quadratic only for three sensors and becomes higher-order beyond that. We switched "
    "to the pattern of San Martín et al. (Dicke state plus XY mixer).",
    "**'No tool exists' was too strong.** Pre-deployment design tools (SN-CAST, AuScope, NetOpt3D, Strutz & Curtis) "
    "do exist. The claim became: no tool we found is built for aftershocks, starts itself, or re-plans.",
    "**An early headline number was a prediction, not a measurement.** Version 1 reported a drop in 'blur' from 2.73 km "
    "to 1.50 km. That was the model's own predicted uncertainty. Version 2 replaced it with a separate simulated "
    "location test using a different wave speed and added timing noise.",
    "**A confidence score could blow up.** The agent measured drift relative to the net score, which can be near zero; "
    "one error read 988% and could have triggered false re-plans. Drift is now measured relative to the predicted "
    "information gain.",
    "**An AI layer was proposed and withdrawn.** The team decided the app has no AI or LLM features; 'agent' means an "
    "automated program.",
])

h2("2.5 Technique comparison with published systems")
para("Before version 2 we compared our method with two published network-design systems: Strutz & Curtis (2024), "
     "which uses a Bayesian information score and a genetic algorithm, and NetOpt3D (Keil et al. 2023), which uses "
     "ray tracing and signal-to-noise modelling.")
table(["Technique", "Decision", "Reason", "Status"], [
    ["Signal-to-noise dependent timing error ('hearing range')", "Adopt, simplified",
     "Distant sites cannot record small aftershocks", "Built, opt-in"],
    ["Slope filter for candidate sites (under 20°)", "Adopt", "Steep sites are unusable; keyless terrain tiles", "Built"],
    ["Bayesian DN score next to the D-criterion", "Adopt as a candidate",
     "Better in one study, but all evidence is from one group", "Computed in the experiment; not used by the agent"],
    ["Nested Monte Carlo check of top designs", "Adopt", "Guards against DN's failure on clustered aftershocks", "Not built"],
    ["Genetic algorithm or annealing as the main search", "Reject", "Exhaustive search is exact at 210 networks",
     "Annealing kept as a baseline"],
    ["3D ray tracing", "Reject", "Needs 3D Earth models and heavy solvers", "Stated as a limitation"],
    ["Reuse of published code (WoWED)", "Reject", "GPL-3.0 licence would bind our whole project", "Own implementation"],
], [4.6, 2.6, 5.4, 3.8], title="What we took from published network-design systems (stage 10).", size=8.5)

# ============================================================================ 3 formulation
h1("3. Formulation")
h2("3.1 Test instance")
table(["Item", "Value", "Source"], [
    ["Earthquake", "M7.1 Ridgecrest, California, 6 July 2019", "USGS ComCat"],
    ["Planning data", f"{I['design_events']} aftershocks (M ≥ 3) in the first {I['decision_hours']} hours", "USGS ComCat"],
    ["Test data", f"{I['validation_events']} later aftershocks (to 13 July), never seen by the planner", "USGS ComCat"],
    ["Permanent stations", f"{I['permanent_stations']} stations of network CI", "IRIS / EarthScope FDSN"],
    ["Candidate sites", f"{I['candidates']} grid nodes at least 6 km from any permanent station", "Our rule (3.3)"],
    ["Budget", f"k = {I['k']} sensors, so {I['feasible_networks']} possible networks", "Assumption"],
], [3.4, 8.6, 4.4], title="The Ridgecrest test instance (real data).", bold_first=True)
figure("map.png", "The instance. Grey dots were used for planning, orange dots for testing. Numbered circles are "
       "candidate sites coloured by access risk; blue rings mark the sites the hybrid QAOA chose.", 11.5)

h2("3.2 Variables, objective and constraint")
table(["Part", "Definition"], [
    ["Decision variables", "x_i ∈ {0, 1} for i = 0…9; x_i = 1 means a sensor goes to candidate site i. One qubit per site"],
    ["Constraint", f"Σ x_i = {I['k']} (exactly {I['k']} sensors)"],
    ["Information score", "D(S) = Σ_e log det F_e(S), the D-optimality criterion. F_e is the 4×4 Fisher information "
     "matrix of aftershock e's position and origin time, from P-wave arrival times at the permanent stations plus "
     "the chosen sites. A larger determinant means a smaller error ellipsoid"],
    ["Access risk", "c_i = exp(−d_i / 5 km), where d_i is the distance from site i to the nearest early aftershock"],
    ["Objective", f"maximise D(S) − λ Σ c_i x_i with λ = {I['lam']:.0f}"],
], [3.4, 13.0], title="The optimisation problem.", bold_first=True)
para("The log-determinant is not a quadratic function, so it does not fit the usual QUBO form. Because the circuit "
     "only ever holds networks of exactly four sites, we can still encode it exactly, using its inclusion–exclusion "
     "(Möbius) expansion up to groups of four sites:")
para("f(x) = Σ_{T, |T| ≤ 4} w_T Π_{i∈T} x_i − λ Σ_i c_i x_i", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, size=11.5)
bullets([
    "w_{i} = D({i}) − D(∅): the information site i adds on its own.",
    "w_{i,j} = D({i, j}) − D({i}) − D({j}) + D(∅): how two sites interact; negative when they are redundant. Groups "
    "of three and four follow the same pattern.",
    f"With 10 sites this gives {FID[4]['terms']} terms, and on every four-site network the sum equals the true score exactly.",
])
para("Substituting x_i = (1 − Z_i)/2 turns f into a Hamiltonian of Z, ZZ, ZZZ and ZZZZ terms whose lowest-energy "
     "state among four-site networks is the best network.")
h2("3.3 Assumptions")
bullets([
    "A uniform P-wave speed of 6 km/s and a picking error of 0.1 s (the agent averages three speeds: 5.5, 6.0, 6.5 km/s).",
    "Candidate sites come from a regular grid; nodes within 6 km of a permanent station are dropped and the 10 "
    "closest to the aftershock cloud kept. In the benchmarks, candidates also pass a road-access and slope check.",
    "The access-risk rule is our own proxy. A real deployment would use roads, permits and safety assessments.",
])

# ============================================================================ 4 algorithm
h1("4. The quantum algorithm")
para("We use the Quantum Approximate Optimization Algorithm (QAOA; Farhi et al. 2014) in its constraint-preserving "
     "form, the Quantum Alternating Operator Ansatz (Hadfield et al. 2019). Each part has a specific job:")
table(["Component", "What it does", "Why"], [
    ["Dicke state |D(10,4)⟩", "Starts the circuit in an equal superposition of exactly the 210 valid networks "
     "(deterministic circuit of Bärtschi & Eidenbenz 2019)", "No probability is wasted on networks with the wrong number of sensors"],
    ["Cost layer exp(−iγH)", "Gives each network a phase proportional to its score; multi-qubit Z terms use a CX "
     "ladder, one RZ, and the ladder undone", "Encodes the exact score, including four-site terms"],
    ["XY ring mixer", "exp(−iβ(XX+YY)/2) on neighbouring qubits swaps a chosen site with an unchosen one",
     "The number of chosen sites never changes"],
    ["Classical optimiser", "COBYLA tunes the 2p angles", "Standard derivative-free choice for noisy objectives"],
    ["CVaR training (α = 0.1)", "Tunes for the mean of the best 10% of outcomes rather than the average",
     f"Raised exact final picks from {FINAL_EXACT['mean-cold']}/{N_BENCH_RUNS} to {FINAL_EXACT['cvar-cold']}/{N_BENCH_RUNS} in the benchmarks"],
    ["Warm start", "Starts from angles that worked on earlier earthquakes, kept in memory", "Starts closer to a good answer"],
    ["Sampling and check", "1,024 measurements on Qiskit's StatevectorSampler; the top networks are re-scored "
     "with the true score and compared with exhaustive search", "The published answer is always verified"],
], [3.6, 7.2, 5.6], title="The parts of the hybrid algorithm.", bold_first=True, size=9)
para("**Why not the textbook penalty approach?** Adding a penalty P(Σx − 4)² lets the circuit put probability on "
     "invalid answers and requires tuning P. San Martín et al. (arXiv:2305.08738) found XY mixers with Dicke states "
     "better for sensor placement on structures; we tested the same question on our problem (Section 7.2).")

# ============================================================================ 5 architecture
h1("5. System architecture")
h2("5.1 One plan: the hybrid pipeline")
figure("architecture.png", "How one plan is made. Classical code builds the exact Hamiltonian, the Qiskit circuit "
       "chooses the sites, and classical code re-scores and verifies the result.", 16.0)
h2("5.2 The whole system")
figure("system.png", "The agent loop and where each part runs. The quantum step (Figure 2) sits inside the loop; "
       "the browser never talks to the laptop directly.", 16.0)
table(["Part", "Role", "Where in the code"], [
    ["Data gateway", "Fetches and caches USGS catalogues, station lists and terrain tiles; one place for rate "
     "limits, retries and a circuit breaker", "data/, src/sources.py"],
    ["Science layer", "Travel times, D-criterion, hearing range, exact objective, candidate pools", "src/geometry.py, src/qubo.py, src/candidates.py"],
    ["Quantum solver", "Dicke state, XY mixer, cost layer, CVaR training, sampling", "src/qaoa_solver.py"],
    ["Baselines", "Exhaustive search, greedy, backward elimination, annealing, expert rule", "src/baselines.py"],
    ["Agent", "Settings, trigger, first plan, hourly checks, re-plans, memory", "src/agent/"],
    ["Web API", "FastAPI with a bearer token, rate limits and a job queue; bound to 127.0.0.1", "api/"],
    ["Test console", "Next.js pages for every module; server-side calls; passcode for any change", "web/"],
    ["Tests", f"303 offline checks for the Python code (about 45 s) and 10 for the console", "tests/, web/lib/"],
], [3.0, 8.6, 4.8], title="Components.", bold_first=True, size=9)
h2("5.3 Hosting and security")
bullets([
    "The backend runs on the team laptop and listens only on 127.0.0.1. A Tailscale Funnel tunnel exposes it over "
    "HTTPS without opening ports; every request needs a shared bearer token.",
    "The console on Vercel calls the backend from the server only, so the token never reaches a browser. Any change "
    "(settings, starting a run) needs a passcode, checked in an HTTP-only cookie with same-origin checks.",
    "Secrets live in environment variables only and are never committed. With the laptop off, the console shows saved results.",
])

# ============================================================================ 6 agent
h1("6. The autonomous agent")
para("The experiment in Chapter 7 is one decision. The agent makes that decision automatically and keeps it up to date.")
table(["Step", "What happens", "Setting (default)"], [
    ["Trigger", "An earthquake at or above the trigger magnitude, with a permanent station within range, starts a run",
     "Trigger magnitude, editable from 3.0 to 9.0; live watching is off by default"],
    ["First plan", "If fewer than 30 real aftershocks exist, it simulates them along the expected rupture (length from "
     "Wells & Coppersmith 1994, magnitudes from a Gutenberg–Richter law) and plans on those", "Minimum real aftershocks"],
    ["Plan", "The quantum circuit chooses the sites; exhaustive search checks them. After two failed retries (each with "
     "two more layers and 4,096 shots) the exact answer is published and flagged", "Retries, layers, shots"],
    ["Hourly check", "Compares the plan with the aftershocks recorded since. Re-plans if their centre moved more than "
     "5 km or the plan's score fell more than 20%", "Interval, duration, thresholds"],
    ["Re-plan", "Adds a cost for every sensor that must move, so it does not shuffle crews for small gains", "Move cost (40)"],
    ["Memory", "Keeps circuit angles that worked, the track record of predicted against realised scores (which sets a "
     "confidence level), and weights for three wave-speed models", "Stored on the laptop"],
], [2.6, 9.4, 4.4], title="What the agent does after an earthquake.", bold_first=True, size=9)
h2("6.1 A 24-hour replay of Ridgecrest")
para(f"A past earthquake can be played forward hour by hour with a simulated clock that never uses later data. With "
     f"default settings and an empty memory, a {REPLAY['hours']}-hour Ridgecrest replay took {REPLAY['seconds']:.0f} "
     f"seconds and made {REPLAY['plans_made']} plans:")
table(["Hour", "Event", "Aftershocks used", "Sites", "Why", "Quantum agreed with exact"], [
    [s["hour"], "First plan" if s["stage"] == "first_plan" else "Re-plan",
     "simulated" if s["synthetic"] else f"{s['aftershocks_real']} real",
     "{" + ", ".join(map(str, s["sites"])) + "}",
     s["drift_reason"] or "no real aftershocks yet", "Yes" if s["quantum_agreed"] else "No (exact used)"]
    for s in REPLANS
], [1.2, 2.2, 2.8, 2.4, 5.2, 2.6], title="Plans made during the replay (run_extras.py).",
    align=["c", "l", "l", "c", "l", "c"], size=9)
para(f"The agent ended on sites {{{', '.join(map(str, REPLAY['final_sites']))}}}, the same network the full "
     f"experiment finds with 12 hours of data, after moving {REPLAY['moves_total']} sensors in total.")

# ============================================================================ 7 results
h1("7. Results on Ridgecrest")
h2("7.1 The exact score against the usual pairwise approximation")
table(["Terms kept", "Terms", "Rank correlation with true score", "Largest error", "Rank of its optimum", "Gates per layer"],
      [[f"Groups up to {o} sites", FID[o]["terms"], f"{FID[o]['spearman']:.4f}", f"{FID[o]['max_abs_error']:.1f}",
        FID[o]["rank_of_its_optimum"], FID[o]["gates_one_layer"]] for o in (2, 3, 4)],
      [3.4, 1.6, 3.4, 2.4, 2.8, 2.8], title="How well each version of the score matches the true score.",
      align=["l", "r", "r", "r", "r", "r"])
para(f"Keeping groups of up to four sites reproduces the true score of all {I['feasible_networks']} networks with zero "
     f"error. The pairwise version ranks networks well (ρ = {FID[2]['spearman']:.3f}) and shares the optimum at "
     f"λ = {I['lam']:.0f}, but at λ = 300 its optimum is only number {LAM300['rank_of_pairwise_optimum']}. The exact "
     f"version costs about {FID[4]['gates_one_layer'] / FID[2]['gates_one_layer']:.1f} times as many gates per layer. "
     "We chose correctness.")
figure("formulation_check.png", "Pairwise approximation against the true score for every network. The exact "
       "expansion lies on the diagonal.", 9.5)

h2("7.2 Does the quantum circuit work?")
rows = []
for p in LAYERS:
    po, ra = stats("xy_p_opt", p), stats("xy_ratio", p)
    rows.append([p, f"{ra[0]:.3f}", f"{pct(po[0])} ({pct(po[1])}–{pct(po[2])})", f"{po[0] / UNI:.0f}×",
                 f"{stats('xy_shots_for_95', p)[0]:.0f}", pct(stats("pen_feasible", p)[0], 0),
                 pct(stats("pen_p_opt", p)[0], 2)])
table(["Layers", "Approx. ratio", "P(best network), XY", "vs random", "Shots for 95%", "Valid, penalty",
       "P(best), penalty"], rows, [1.4, 2.0, 3.6, 1.8, 2.2, 2.4, 2.6],
      title="QAOA performance over 5 seeds per depth. The penalty circuit is the textbook alternative.",
      align=["c", "r", "r", "r", "r", "r", "r"])
para(f"A random valid network is the best one with probability 1/210 = {pct(UNI, 2)}. The XY-mixer QAOA raises "
     f"that to {pct(P_BY_LAYER[1])} with one layer and {pct(P_BY_LAYER[max(LAYERS)])} with three, and every "
     f"measurement is a valid four-site network. After re-scoring, the pipeline returned the exact optimum, sites "
     f"{SITES}, in {N_EXACT} of {N_RUNS} runs. Our own target was 20% per measurement; we did not reach it.")
para("The penalty circuit gave a valid answer only part of the time and measured the optimum less often than random "
     f"guessing among valid networks. We used one untuned penalty weight (P = {Q['penalty']:.0f} in scaled units), so a "
     "better-tuned penalty circuit could do better than ours did.")
figure("qaoa_performance.png", "Left: probability of measuring the best network (log scale; bars show the range over "
       "5 seeds). Right: probability that a measurement is a valid four-site network.", 15.5)

h2("7.3 Comparison with exact and classical methods")
para("The score is a prediction. To test it independently we simulated locating the later aftershocks: arrival times "
     f"were computed with a different wave speed ({LT['v_true']} km/s instead of the planner's 6.0) and random timing "
     "noise was added, then each aftershock was located by least squares with the permanent stations plus the four "
     "chosen sites. We did this for every one of the 210 networks.")
table(["Method", "Sites", "Rank by score", "Mean error (km)", "90th percentile (km)"],
      [["No new sensors", "–", "–", f"{LT['no_new_sensors_mean_km']:.2f}", "–"],
       ["Average of all 210 networks", "–", "–", f"{LT['all_networks_mean_km']:.2f}", "–"]] +
      [[name, ", ".join(map(str, m["sites"])), m["rank_true"], f"{m['loc_error_mean_km']:.2f}",
        f"{m['loc_error_p90_km']:.2f}"] for name, m in M.items()],
      [5.0, 2.6, 2.4, 3.0, 3.4], title=f"Simulated location error on {I['validation_events']} later aftershocks.",
      align=["l", "c", "r", "r", "r"])
para(f"The chosen network lowers the mean location error from {LT['no_new_sensors_mean_km']:.2f} km to "
     f"{QAOA['loc_error_mean_km']:.2f} km, against {EXPERT['loc_error_mean_km']:.2f} km for a field rule that closes "
     f"the largest azimuthal gap. It ranks {LT['rank_of_qaoa_pick']} of 210 in the simulated test (best: "
     f"{LT['best_network_km']:.2f} km); score and test agree reasonably (rank correlation "
     f"{-LT['spearman_d_vs_error']:.2f}). Greedy selection, backward elimination and simulated annealing "
     f"({Q['sa_found_exact']} of {Q['sa_runs']} seeds) find the same answer: this instance is easy for classical methods.")
figure("location_test.png", "Mean error when locating later aftershocks in the simulated test (lower is better).", 13.0)

h2("7.4 The trade-off between accuracy and crew risk")
para(f"Ignoring risk (λ = 0), the best network is {{0, 1, 4, 7}} with a total access risk of "
     f"{F['lam_sweep'][0]['risk']:.2f}. At λ = {I['lam']:.0f} the optimiser swaps high-risk site 0 for low-risk site 3: "
     f"risk falls to {QAOA['risk']:.2f} for a small loss in accuracy. Larger λ pushes sensors away from the rupture and "
     "accuracy degrades quickly.")
figure("tradeoff.png", "The exact optimum for different risk weights λ.", 9.5)

# ============================================================================ 8 more results
h1("8. Beyond one earthquake")
h2("8.5 Five more earthquakes")
para(f"To check that the method is not tuned to Ridgecrest, we repeated the test on five more earthquakes with "
     f"{BENCH['settings']['at_hours']:.0f} hours of real aftershocks, road-checked candidate sites, "
     f"{BENCH['settings']['layers']} circuit layers and {len(BENCH['settings']['seeds'])} seeds per variant "
     f"({BENCH['runtime_seconds'] / 60:.0f} minutes in total). Ridgecrest is repeated here with a wider station set, "
     "so its numbers differ from Chapter 7.")
rows = []
for e in EV:
    v, g = e["variants"], e["gain_over_expert"]["exact"]
    rows.append([e["name"], e["valid_events"], pct(v["mean-cold"]["p_best_mean"]), pct(v["cvar-cold"]["p_best_mean"]),
                 pct(v["cvar-warm"]["p_best_mean"]), f"{v['cvar-cold']['final_exact']}/{v['cvar-cold']['runs']}",
                 f"{g['plain_pct']:+.1f}%", f"{g['hearing_pct']:+.1f}%"])
table(["Earthquake", "Test events", "P(best) mean", "P(best) CVaR", "P(best) CVaR warm", "Exact (CVaR)",
       "vs expert", "vs expert, hearing"], rows, [3.4, 1.6, 1.8, 1.8, 2.0, 1.8, 1.8, 2.2],
      title="Benchmarks (run_benchmarks.py). Positive 'vs expert' means our optimum located aftershocks better.",
      align=["l", "r", "r", "r", "r", "c", "r", "r"], size=8.5)
para(f"CVaR training made the final pick exact in {FINAL_EXACT['cvar-cold']} of {N_BENCH_RUNS} runs, against "
     f"{FINAL_EXACT['mean-cold']} of {N_BENCH_RUNS} with the usual mean-energy training, and raised the chance per "
     f"measurement on every earthquake. The best chance per measurement in any variant was {pct(BEST_P)}; the 20% "
     "target was missed in every run.")
note("The result that did not go our way",
     f"In the simulated location test the best-scoring network beat the expert rule on only {len(WINS)} of {len(EV)} "
     f"earthquakes ({', '.join(e['name'] for e in WINS)}). On {WORST['name']} it was "
     f"{-WORST['gain_over_expert']['exact']['plain_pct']:.1f}% worse. The quantum step found the optimum of the score "
     "it was given; the score itself (the D-criterion) does not always predict location error. Better placement on "
     "these earthquakes needs a better score, not a better search." +
     (f" {SKIPPED[0]['name']} was skipped: {SKIPPED[0]['skipped']}." if SKIPPED else ""), "warn")
para("Hearing range (the right-hand column): a station whose simulated signal-to-noise ratio is under 5 gives no "
     "reading, and weak readings are noisier. It uses the Hutton & Boore (1987) attenuation law with an assumed noise "
     "level, so it is a simplification.")

h2("8.6 Simulated gate noise")
ni = NOISE["instance"]
para(f"Real quantum hardware makes errors. Without hardware access we simulated depolarising gate errors on a smaller "
     f"version ({ni['n']} sites, choose {ni['k']}, {ni['layers']} layer) with a Monte-Carlo Pauli-error method in "
     f"qiskit.quantum_info, {NOISE['trials']} trials per point.")
table(["Gate error", "P(best network)", "Valid answers"],
      [[f"{p['gate_error']:.2%}" if p["gate_error"] else "0 (noise-free)", pct(p["p_best"]), pct(p["valid"])]
       for p in NOISE_PTS],
      [4.0, 4.0, 4.0], title=f"Noise study (run_extras.py). Random guessing gives {pct(NOISE['uniform_p_best'])}.",
      align=["l", "r", "r"])
para("At 1% gate error the circuit still beats random guessing clearly, but a third of the answers are no longer valid "
     "networks. On hardware the classical check would catch these, at the cost of more shots. This is a classical "
     "simulation, not a hardware result.")

# renumber 8.x headings to 8.1/8.2 (kept as constants above for readability)
for p_ in doc.paragraphs:
    if p_.style.name == "Heading 2" and p_.text.startswith("8.5 "):
        p_.runs[0].text = p_.runs[0].text.replace("8.5 ", "8.1 ")
    if p_.style.name == "Heading 2" and p_.text.startswith("8.6 "):
        p_.runs[0].text = p_.runs[0].text.replace("8.6 ", "8.2 ")

# ============================================================================ 9 caveats
h1("9. Caveats and limitations")
para("The brief says limitations count in a team's favour. These are ours, grouped by what they affect.")
table(["Area", "Caveat", "What it means for our claims"], [
    ["Quantum advantage", "With 210 networks, brute force takes milliseconds and greedy search finds the optimum",
     "No speedup is claimed. The instance is small so every answer can be verified"],
    ["Success rate", f"The chance per measurement was {pct(P_BY_LAYER[1], 0)}–{pct(BEST_P, 0)}, below our 20% target",
     "QAOA finds the optimum by sampling many times, not with certainty"],
    ["Scaling", f"The exact score needs {FID[4]['terms']} terms instead of {FID[2]['terms']}, and the count grows fast with the budget",
     "The exact encoding does not scale to large sensor budgets"],
    ["Circuit depth", f"About {DEPTH[1]:,.0f} at one layer and {DEPTH[max(LAYERS)]:,.0f} at three, against "
     f"{PEN_DEPTH[1]:,.0f}–{PEN_DEPTH[max(LAYERS)]:,.0f} for the penalty circuit",
     "Noise-free simulation only; on current hardware this depth is a serious problem (Section 8.2)"],
    ["The score", f"The D-criterion beat the expert rule on only {len(WINS)} of {len(EV)} earthquakes in the location test",
     "The agent's value today is speed, automation and re-planning, not a better score than a field rule"],
    ["Location test", "Simulated: the same simple physics with a different wave speed and added noise, not real recordings",
     "Kilometre figures are relative indicators, not operational errors"],
    ["Physics", "Uniform wave speed, P waves only, fixed picking error, no site effects or 3D structure",
     "Which sites are better is more reliable than the exact numbers"],
    ["Hearing range", "Hutton & Boore attenuation with one assumed noise level for every site", "A simplification, opt-in"],
    ["Inputs", "Candidate sites, access risk and λ follow rules we wrote", "A response team would set these from local knowledge"],
    ["Training shortcut", "During CVaR training the circuit's output is computed by our exact simulator of the same "
     "circuit (tested against Qiskit's Statevector); final measurements run on Qiskit's sampler",
     "Same results, seconds instead of minutes per plan"],
    ["Live mode", "Tested with a recorded feed only; a run cut off by a restart is not resumed",
     "Not yet proven during a real qualifying earthquake"],
    ["Evidence", "'Siting is mostly manual' rests on published reports, not interviews; 'no earlier quantum "
     "formulation' means only that our searches found none", "We say 'first we found', never 'first ever'"],
], [2.8, 7.0, 6.6], title="Caveats.", bold_first=True, size=8.5)
h2("9.1 What did not work or was not built")
bullets([
    "The 20% per-measurement success target was missed in every run, on every earthquake.",
    f"The optimised network beat the expert rule on only {len(WINS)} of {len(EV)} earthquakes.",
    "The penalty-based QAOA did worse than random guessing among valid networks (with one untuned weight).",
    "Not built from the design: team overrides of individual sites, the nested Monte Carlo check of top designs, a "
    "full leave-one-earthquake-out replay, and a run on IBM hardware.",
    "The three wave-speed weights in memory stay equal in practice: without measured arrival times the models cannot be told apart.",
    (f"{SKIPPED[0]['name']} could not be tested: {SKIPPED[0]['skipped']}." if SKIPPED else "All six earthquakes were tested."),
])
h2("9.2 What we would do next")
bullets([
    "A score that predicts location error better than the D-criterion, chosen by held-out error across earthquakes.",
    "A layered velocity model and real access data (roads, land permits).",
    "Larger instances (20 to 30 sites) where exhaustive search stops being trivial.",
    "A run on real IBM hardware, with error mitigation, to compare against the noise study.",
])

# ============================================================================ 10 compliance
h1("10. How the submission meets the brief")
table(["Brief item", "Where it is met", "Status"], [
    ["Identify the problem and who it serves", "Chapter 1", "Done"],
    ["Formulate: variables, objective, constraints, a small test instance", "Chapter 3", "Done"],
    ["Justify the quantum algorithm", "Chapter 4", "Done"],
    ["Implement it in Qiskit", "src/qaoa_solver.py (Qiskit 2.6.2)", "Done"],
    ["Evaluate against a classical or exact baseline", "Sections 7.2, 7.3 and 8.1", "Done"],
    ["Reflect on limitations", "Chapter 9", "Done"],
    ["Architecture diagram in the report", "Figures 2 and 3", "Done"],
    ["Keep the instance small and simulator-friendly", "10 qubits, 210 networks, statevector simulation", "Done"],
    ["Make the quantum part do real work", "The circuit chooses every plan; classical code only verifies", "Done"],
    ["README with setup steps", "README.md, section 'Run it'", "Done"],
    ["Be honest about what did not work", "Sections 8.1 and 9.1", "Done"],
    ["Stay within the six domains", "Disaster Response", "Done"],
    ["No copied code; credit reused ideas", "Own implementation; ideas credited in References; GPL code deliberately not reused", "Done"],
    ["Video of 3 minutes or less", "VIDEO_SCRIPT.md, about 2:50", "Team to record"],
    ["Check every link opens; repository visible to judges", "Repository is private until submission", "Team to confirm"],
    ["No commits after the deadline", "Last commit before the cutoff", "Team to confirm"],
], [6.0, 7.4, 3.0], title="Checklist against the hackathon brief, dos and don'ts.", align=["l", "l", "c"], size=9)

# ============================================================================ 11 reproduce
h1("11. Reproducing the results")
para("All results run offline on a laptop from cached data (Windows 11, Python 3.12, Qiskit 2.6.2). Setup steps are "
     "in README.md.")
table(["Command", "What it produces", "Time"], [
    ["python -m pytest tests -q", "303 automated checks", "about 45 s"],
    ["python run_experiment.py", "Ridgecrest experiment: results/results.json and figures", f"{R['runtime_seconds'] / 60:.0f} min"],
    ["python run_benchmarks.py", "Five more earthquakes: results/benchmarks.json", f"{BENCH['runtime_seconds'] / 60:.0f} min"],
    ["python run_extras.py", "Noise study and agent replay: results/extras.json", f"{EXTRA['runtime_seconds']:.0f} s"],
    ["python report/make_diagram.py", "Figures 2 and 3", "seconds"],
    ["python report/build_report.py", "This report", "seconds"],
], [5.6, 8.0, 2.8], title="Commands.", size=9)

# ============================================================================ references
h1("References and credits")
REFS = [
    "Bärtschi, A. & Eidenbenz, S. (2019). Deterministic preparation of Dicke states. FCT 2019, LNCS 11651.",
    "Bloem, H., Curtis, A. & Maurer, H. (2020). Experimental design for fully nonlinear source location problems: which method should I choose? Geophysical Journal International 223, 944–958. doi:10.1093/gji/ggaa358",
    "Cochran, E. S. et al. (2020). The U.S. Geological Survey's rapid seismic array deployment for the 2019 Ridgecrest earthquake sequence. Seismological Research Letters 91, 1952–1960. doi:10.1785/0220190296",
    "Farhi, E., Goldstone, J. & Gutmann, S. (2014). A quantum approximate optimization algorithm. arXiv:1411.4028.",
    "Hadfield, S. et al. (2019). From the quantum approximate optimization algorithm to a quantum alternating operator ansatz. Algorithms 12(2), 34.",
    "Hardt, M. & Scherbaum, F. (1994). The design of optimum networks for aftershock recordings. Geophysical Journal International 117(3), 716–726.",
    "Hutton, L. K. & Boore, D. M. (1987). The ML scale in Southern California. Bulletin of the Seismological Society of America 77(6), 2074–2094.",
    "Keil, S., Wassermann, J., Megies, T. & Kraft, T. (2023). Optimal network design for microseismic monitoring in urban areas: a case study in Munich, Germany. Seismica 2(2). doi:10.26443/seismica.v2i2.1030",
    "Kijko, A. (1977). An algorithm for the optimum distribution of a regional seismic network I. Pure and Applied Geophysics 115, 999–1009. doi:10.1007/BF00881222",
    "Rabinowitz, N. & Steinberg, D. M. (1990). Optimal configuration of a seismographic network: a statistical approach. BSSA 80(1), 187–196.",
    "San Martín, G. et al. Quantum-based combinatorial optimization for optimal sensor placement in civil structures. arXiv:2305.08738.",
    "Strutz, D. & Curtis, A. (2024). Preprint on Bayesian optimal design of seismic monitoring networks. arXiv:2411.11015.",
    "Toledo, T., Jousset, P., Maurer, H. & Krawczyk, C. (2020). Optimized experimental network design for earthquake location problems. JVGR 391, 106433.",
    "Wells, D. L. & Coppersmith, K. J. (1994). New empirical relationships among magnitude, rupture length, rupture width, rupture area, and surface displacement. BSSA 84(4), 974–1002.",
    "U.S. Geological Survey. ANSS Comprehensive Earthquake Catalog (ComCat). Station metadata: EarthScope/IRIS FDSN station service.",
]
for ref in REFS:
    p = doc.add_paragraph(style="List Number")
    rich(p, ref, size=9.5)
note("Credits and use of AI tools", [
    "All code was written for this hackathon; no code was copied from tutorials or other teams. Published ideas "
    "(the Dicke-state circuit, the XY mixer, the D-criterion, the attenuation law and the San Martín et al. pattern) "
    "are credited above.",
    "The code and documents were written with AI assistance (Claude Code), directed and reviewed by the team. The "
    "application itself contains no AI or LLM features.",
], "key")

# ============================================================================ appendix: glossary
page_break()
h1("Appendix A. Glossary")
table(["Term", "Meaning"], [
    ["Aftershock", "A smaller earthquake that follows a large one in the same area"],
    ["Azimuthal gap", "The largest angle, seen from an earthquake, with no seismometer; a common field rule closes it"],
    ["CVaR", "Conditional value at risk: here, the average energy of the best 10% of measured networks"],
    ["D-criterion", "The log-determinant of the information matrix; larger means a smaller location error ellipsoid"],
    ["Dicke state", "A quantum state that is an equal mix of all bit strings with exactly k ones"],
    ["Hamiltonian", "The energy function the circuit minimises; its lowest state is the best network"],
    ["Hearing range", "Whether a station can detect an aftershock, from its simulated signal-to-noise ratio"],
    ["QAOA", "Quantum Approximate Optimization Algorithm: alternating cost and mixer layers tuned by a classical optimiser"],
    ["QUBO", "Quadratic unconstrained binary optimisation: a score over yes/no variables with pairwise terms"],
    ["Qubit", "A quantum bit; here, one qubit per candidate site"],
    ["Statevector simulation", "An exact classical simulation of a quantum circuit, without noise"],
    ["XY mixer", "A two-qubit gate that swaps a 1 and a 0, so the number of chosen sites stays fixed"],
], [3.6, 12.8], title="Terms used in this report.", bold_first=True, size=9)

doc.save(OUT)
print("wrote", OUT)


# ---------------------------------------------------------------------------- let Word fill the contents
def finish_with_word(path: Path) -> None:
    if sys.platform != "win32":
        return
    try:
        import win32com.client  # type: ignore
    except ImportError:
        import subprocess
        ps = (f"$w=New-Object -ComObject Word.Application; $w.Visible=$false; "
              f"$d=$w.Documents.Open('{path}'); $d.TablesOfContents(1).Update(); $d.Fields.Update() | Out-Null; "
              f"$d.Save(); $d.SaveAs2('{path.with_suffix('.pdf')}', 17); $d.Close(); $w.Quit()")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=180)
        print("Word:", "contents updated, PDF written" if r.returncode == 0 else f"skipped ({r.stderr.strip()[:200]})")
        return
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        d = word.Documents.Open(str(path))
        d.TablesOfContents(1).Update()
        d.Fields.Update()
        d.Save()
        d.SaveAs2(str(path.with_suffix(".pdf")), 17)
        d.Close()
        print("Word: contents updated, PDF written")
    finally:
        word.Quit()


finish_with_word(OUT)
