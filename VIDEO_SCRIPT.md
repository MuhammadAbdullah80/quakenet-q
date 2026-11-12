# QuakeNet-Q: 3-minute video script

About 400 words of narration (about 2:40 spoken) plus a 30–40 second demo. Hard limit: 3:00.
Every number matches the report (`report/QuakeNet-Q_Report.docx`).

| Time | On screen | Say |
|---|---|---|
| 0:00–0:15 | Title, then the landing page globe | "Imagine a massive earthquake hits a city. The shaking stops, but the danger doesn't. Aftershocks can continue for days, weeks, even months, and scientists need to know exactly where they're happening." |
| 0:15–0:40 | `figures/map.png` without the blue rings | "They track them with seismometers: instruments that measure ground vibrations. After a big quake, teams rush a few portable seismometers into the field. But they can't just install more. Every sensor costs money and time, some sites are hard to reach, and sensors placed close together record the same information twice. The real challenge isn't more sensors. It's the right locations." |
| 0:40–0:50 | Title card | "That's why we built QuakeNet-Q, for the Disaster Response domain of Qiskit Fall Fest 2026: an automated agent that uses quantum optimisation to decide where portable seismometers go." |
| 0:50–1:05 | `figures/system.png` (agent loop) | "Here's how it works. The agent watches the USGS earthquake feed. When a large quake hits, it starts by itself. It takes real aftershock data and the existing EarthScope stations, and scores every possible network with D-optimality, a measure of how much location information a network gives." |
| 1:05–1:35 | `figures/architecture.png` | "Then comes the quantum part. In our prototype we choose 4 sensors from 10 sites: 210 combinations. In Qiskit, each site is one qubit. A Dicke state and an XY mixer keep the QAOA circuit on networks of exactly four sensors, and we encode the score exactly, not approximately. A classical optimiser tunes the circuit so the best networks become more likely. Every answer is checked against an exact search. Then, every hour, the agent checks the new aftershocks and re-plans if the activity has moved." |
| 1:35–2:10 | **Demo, no narration needed:** live site, Settings (trigger magnitude), run a plan, the map, then Monitor with the replay | (Optional voice-over: "Here it is live: the trigger setting, a plan, and Ridgecrest replayed hour by hour.") |
| 2:10–2:30 | `figures/qaoa_performance.png`, then `figures/location_test.png` | "On the 2019 Ridgecrest earthquake, the quantum step found the best network in 15 of 15 runs. One measurement picks the best network up to 11% of the time, against 0.48% for random guessing. In a simulated test on later aftershocks, our network cut location error from 3 kilometres to 2.3, better than a standard field rule. And a full 24-hour replay runs in about 20 seconds." |
| 2:30–2:45 | Caveats table in the report (Chapter 9) | "We're honest about the limits. At this size a classical computer is just as fast, so we claim no quantum speedup. And on four of five other earthquakes, the simple field rule did as well or better. That tells us the next step is a better score, not a faster search." |
| 2:45–2:50 | Title card with the repository link | "QuakeNet-Q: the right sensors, in the right places, within minutes of the quake." |

## Recording checklist

- [ ] Read it aloud once with a timer; if it runs past 2:55, cut the "24-hour replay" sentence first.
- [ ] Under 3:00 in total.
- [ ] Upload to Google Drive and set access to "Anyone with the link".
- [ ] Open the link in a private browser window to confirm it plays.
