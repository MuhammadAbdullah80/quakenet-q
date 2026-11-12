# QuakeNet-Q: Open Questions

Updated 2026-11-12. Questions marked **BLOCKS BUILD** need an answer before spec v2 can be written.

## For the team

| # | Question | Why it matters | My recommendation |
|---|---|---|---|
| Q4 | **BLOCKS BUILD.** What is the real deadline? | The brief says 12 Nov 2026, 23:59. The scope must fit the time | Confirm with the organisers. If it is tonight, we polish the proof of concept and do not start the agent |
| Q7 | Do you approve the eight technique changes (decisions 12–18 in `DECISIONS.md`, plus the usability claim in `PROGRESS.md`)? | They change the scoring and site filters | Yes |
| Q8 | Which parts may be cut if time runs short? | 29 requirements plus a web system is a lot | Cut in this order: hardware demo, live mode, benchmark earthquakes 3–6 |
| Q9 | Team name and members for the report | The report has a placeholder | Send them when ready |
| Q10 | Should the repo become public, and when? | Judges cannot open a private repo | Make it public just before submitting |
| Q12 | May anyone who opens the site start a run on the laptop, or only people with a team passcode? | The site is public, and each run uses the laptop's processor | Passcode while we build; decide before submission whether to open it for judges. Runs are capped either way |
| Q11 | Push the two local commits and these documents to GitHub? | They are only on this computer | Yes, once you have read them |

## Still to verify (mine to check)

| # | Claim | Affects |
|---|---|---|
| V1 | Each benchmark earthquake has enough early aftershocks and station data | Evaluation plan |
| V2 | Station locations of real temporary deployments are available (for example Ridgecrest 2019) | Comparison with what field teams did |
| V3 | USGS publishes focal mechanisms fast enough for the first plan | Simulated aftershocks |
| V4 | Nodal sensors typically do not send data in real time | Problem statement and pitch |
| V5 | Rate limits and usage policies of the USGS feed, FDSN services and Overpass | `ARCHITECTURE.md` section 3 |
| V6 | Other regions' data providers (EMSC, ORFEUS-EIDA and others) | Geo-based design |
| V7 | Strutz & Curtis (2024) journal status | Citation |
| V8 | Tailscale Funnel: how to switch it on, allowed ports, request and bandwidth limits | Hosting |

## Answered

| # | Question | Answer |
|---|---|---|
| A8 | Where will it run? | Frontend on Vercel; backend on the team laptop through a secure tunnel (see `ARCHITECTURE.md` section 4) |
| A7 | Which AI provider and key? | None needed: no AI features |
| A6 | What should "all 430 skills" mean? | Nothing in the app. They are build-time instructions only |
| A5 | What should the AI layer do, and what is GCF? | No AI layer. GCF (Graph Context Form, a token-saving technique for AI agents) is therefore not needed |
| A1 | Do tools like ours already exist? | For planning ahead, yes (SENSI, SN-CAST, NetOpt3D, Strutz & Curtis). None is built for aftershocks, starts itself, or re-plans |
| A2 | Is our score the best available? | Not proven. DN is reported better in one study; we test both |
| A3 | Is a proof of concept with no speedup acceptable? | Yes. The brief says speedup and hardware are not required |
| A4 | Why 4 of 10? | Every answer can be verified exactly, and the score can be made exact |
