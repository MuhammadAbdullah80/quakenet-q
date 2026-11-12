# QuakeNet-Q: project instructions

Read `PROGRESS.md` first. It says what is built, what is only designed, and what is next.

## What this project is

A Qiskit Fall Fest 2026 hackathon entry (domain: Disaster Response). An agent decides where the first
portable seismometers go after a major earthquake. A quantum optimisation algorithm (Dicke state plus
XY-mixer QAOA) makes the choice; everything else is classical. It is a proof of concept: no quantum
speedup is claimed.

## Key documents

| File | Purpose |
|---|---|
| `PROGRESS.md` | Current status and next steps |
| `docs/specs/2026-11-12-quakenet-q-agent-design.md` | Design spec (source of truth; rebuild the HTML with `python docs/specs/build_spec_html.py`) |
| `docs/ARCHITECTURE.md` | System design: API, rate limits, frontend, geo regions, hosting, security rules |
| `docs/DECISIONS.md` | Every decision and its reason |
| `docs/OPEN_QUESTIONS.md` | Questions waiting on the team; claims still to verify |
| `research/` | Source notes behind every factual claim |

## How to work here

- **No AI or LLM features in the app.** "Agent" here means an automated program, not a chatbot.
- **No building before approval.** The team approves the spec before any code is written.
- **Explain in plain language.** The team is new to quantum computing and seismology; define terms.
- **Honesty over polish.** Report misses, state limitations, and never claim something unverified.
  Say "first we found", never "first ever".
- **Every number comes from a script** in the repo, run on cached data. No hand-entered results.
- **Check claims against sources** before they go into the spec, report or pitch.
- **Tests first** for new code. The offline test suite must stay under 60 seconds.
- **Security rules** in `docs/ARCHITECTURE.md` section 6 apply to all code. Secrets live in environment
  variables only.
- **Update the docs in the same change** as the code: `PROGRESS.md`, `DECISIONS.md`, and the spec.
- **Git:** commit or push only when asked. The repo is private under `MuhammadAbdullah80`.

## Commands

```bash
python -m pytest tests -q            # 303 checks, about 45 s
python run_experiment.py --quick     # proof of concept, under a minute
python run_experiment.py             # full run, about 45 minutes
python run_extras.py                 # noise study and agent replay (results/extras.json), about 1 min
python report/make_diagram.py        # report diagrams
python report/build_report.py        # rebuild the .docx report (and PDF if Word is installed)
python docs/specs/build_spec_html.py # rebuild the spec HTML
```

## Environment

Windows 11, Python 3.12, Qiskit 2.6.2, Node 24, Tailscale 1.104 (for the backend tunnel). No Qiskit Aer, LibreOffice or `docx` npm package.
