# QuakeNet-Q: 3-minute video script

Target length 2:50. Speak slowly; about 440 words in total; trim the 0:25–0:50 line if it runs long.

| Time | On screen | Say |
|---|---|---|
| 0:00–0:25 | Title, then `figures/map.png` without the blue rings | "On 6 July 2019 a magnitude 7.1 earthquake hit Ridgecrest, California. In the next 12 hours there were more than 500 aftershocks. Response teams rush portable seismometers into the field, but they only have a few, and where they put them decides how clearly we can see which faults are still active." |
| 0:25–0:50 | Phone-tower sketch, or point at the stations on the map | "It works like your phone's location. If all the towers are on one side of you, your position is blurry. Today this siting is mostly expert judgement under time pressure. We turned it into an optimisation problem for rescue teams: pick 4 sites out of 10." |
| 0:50–1:20 | README formulation table | "There are three goals that pull against each other: make aftershock locations as sharp as possible, don't waste sensors on sites that see the same thing, and keep crews away from the dangerous rupture zone, which is exactly where the best sites are. Each site is one qubit: yes or no. The score comes from a standard seismology criterion, built from real USGS data." |
| 1:20–1:50 | `figures/architecture.png` | "It's a hybrid pipeline. A classical step turns the data into scores. A quantum circuit in Qiskit chooses the sites. We start in a state containing only valid answers, exactly 4 sites, and use a mixer that can only swap sites, so the circuit can never give an invalid answer. A classical optimiser tunes it, and a classical step checks the result." |
| 1:50–2:10 | The live site: Settings (trigger magnitude), then Monitor with the hour slider moving | "And it runs on its own. It watches the USGS earthquake feed, and any quake above a magnitude a scientist sets here starts it. Within minutes it has a first plan, then it checks every hour and moves sensors when the aftershocks shift. Here is Ridgecrest replayed: it re-plans at hour 1 and hour 23, and the circuit picks sites 1, 3, 4 and 7." |
| 2:10–2:35 | `figures/location_test.png`, then `figures/qaoa_performance.png` | "We tested on 217 aftershocks that happened later, which the planner never saw. The average location error drops from 3.0 kilometres to 2.3, against 2.6 for a common field rule. Brute force over all 210 options confirms this is the best-scoring answer, and with three layers the circuit gives it in 11 percent of measurements, about 23 times more often than random guessing." |
| 2:35–2:55 | Limitations list in the README | "To be honest about limits: at this size classical methods find the same answer instantly, so we claim no speedup. On five other earthquakes the circuit found the best-scoring network, but that network beat a simple field rule only once, so the next step is a better score. Our physics is simplified, the location test is a simulation, and we only ran on a simulator. What we contribute is a tested formulation of a real disaster-response decision. Thank you." |

## Recording checklist

- [ ] Under 3:00.
- [ ] Upload to Google Drive and set access to "Anyone with the link".
- [ ] Open the link in a private browser window to confirm it plays.
