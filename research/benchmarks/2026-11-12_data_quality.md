# Benchmark earthquakes: data-quality check

Generated 2026-11-12 14:35 UTC by `research/benchmarks/data_quality.py`. Every number below comes from that script, run on the responses cached in `data/cache/` (each has a sidecar with its URL and retrieval time).

This answers risk R-2 of the design spec: are the six planned benchmark earthquakes usable?

## How to read it

- **Radius**: the study radius of spec FR-3, max(50 km, 2 x rupture length). Rupture length is the Wells & Coppersmith (1994) subsurface length for all fault types, log10 L = -2.44 + 0.59 M.
- **Aftershocks**: USGS ComCat earthquakes with M >= 2.5 inside the radius, after the mainshock. "0-12 h" is what a planner would know at decision time; "12 h-7 d" is what the plan is tested on.
- **Permanent stations**: stations of any network in the IRIS/EarthScope metadata that were operating at the mainshock time. This counts every listed station, including strong-motion sites and long-running temporary experiments, and it does not check that a station was actually recording.
- **Temporary stations**: stations whose first listed epoch starts within 30 days after the mainshock. This is how a rapid-response deployment shows up, but an unrelated experiment that happened to start in that month is counted too. Deployments that were never archived at EarthScope are missed.
- **Candidate pool**: 2 km grid points left after the filters of spec FR-6 (on land, slope under 20 degrees, within 1.5 km of a road, 6 km from permanent stations, 3 km from the rupture). The only rupture point used here is the mainshock epicentre, because no mapped rupture trace is downloaded.
- **Verdict rule** (in the script): *not usable* if a download failed, no permanent station, or fewer than 10 pool points; *usable with caveats* if under 30 early aftershocks, under 100 later ones, under 4 permanent stations, no temporary stations, or the pool was not feasibility-checked; otherwise *usable*.

## Summary

| Earthquake | USGS event ID | M | Radius (km) | Aftershocks 0-12 h | Aftershocks 12 h-7 d | Permanent stations | Temporary stations (networks) | Candidate pool | Feasibility checked | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| Ridgecrest 2019 | ci38457511 | 7.1 | 112 | 1056 | 744 | 54 | 493 (3J, 7Q, GS) | 7174 | **no** | usable with caveats |
| South Napa 2014 | nc72282711 | 6.0 | 50 | 5 | 9 | 187 | 241 (7C, GS, NC) | 506 | **no** | usable with caveats |
| Monte Cristo Range 2020 | nn00725272 | 6.5 | 50 | 161 | 410 | 18 | 10 (8P, GS, NN) | 1678 | **no** | usable with caveats |
| Anchorage 2018 | ak018fcnsk91 | 7.1 | 112 | 324 | 338 | 71 | 8 (GM) | 801 | yes | usable |
| Ferndale 2022 | nc73821036 | 6.4 | 50 | 48 | 20 | 22 | 1 (NC) | 252 | **no** | usable with caveats |
| Puerto Rico 2020 | pr2020007007 | 6.4 | 50 | 137 | 710 | 21 | 9 (GS, PR) | 552 | **no** | usable with caveats |

## Per earthquake

### Ridgecrest 2019 (ci38457511)

- ComCat: M 7.1, 2019-07-06T03:19:53.040000+00:00, lat 35.7695, lon -117.5993, depth 8 km ("Ridgecrest Earthquake Sequence"). Matches the `BENCHMARKS` registry: yes.
- Study radius: 112.2 km.
- Aftershocks M >= 2.5: 1056 in the first 12 h, 744 from 12 h to 7 days.
- Permanent stations: 54. By network: 8P (1), CI (41), LB (1), NN (4), NP (3), PB (4).
- Temporary stations: 493. By network: 3J (456), 7Q (27), GS (10).
- Candidate pool: 7174 points. Filter funnel: grid 9917 -> on_land 9691 -> slope 8391 -> station_gap 7177 -> rupture_gap 7174.
- Roads checked: **no**; terrain checked: yes.
- **Warning:** Overpass unavailable, road filter skipped (grid and terrain only): FEED_UNAVAILABLE: overpass-api.de failed after 4 attempts (HTTP 502): https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%5Btimeout%3A25%5D%3Bway%5B%22highway%22~%22%5E%28motorway%7Ctrunk%7Cprimary%7Csecondary%7Ctertiary%7Cunclassified%29%24%22%5D%2834.7603%2C-118.8431%2C36.7787%2C-116.3556%29%3Bout%20geom%20qt%3B
- **Verdict: usable with caveats.** road or terrain check did not run, pool is not feasibility-checked.

### South Napa 2014 (nc72282711)

- ComCat: M 6.02, 2014-08-24T10:20:44.070000+00:00, lat 38.2152, lon -122.3123, depth 11.12 km ("The 2014 South Napa, California Earthquake"). Matches the `BENCHMARKS` registry: yes.
- Study radius: 50.0 km.
- Aftershocks M >= 2.5: 5 in the first 12 h, 9 from 12 h to 7 days.
- Permanent stations: 187. By network: BK (18), NC (89), NP (70), PB (2), YK (7), YU (1).
- Temporary stations: 241. By network: 7C (223), GS (6), NC (12).
- Candidate pool: 506 points. Filter funnel: grid 1961 -> on_land 1687 -> slope 1630 -> station_gap 507 -> rupture_gap 506.
- Roads checked: **no**; terrain checked: yes.
- **Warning:** Overpass unavailable, road filter skipped (grid and terrain only): FEED_UNAVAILABLE: overpass-api.de failed after 4 attempts (TimeoutError: The read operation timed out): https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%5Btimeout%3A25%5D%3Bway%5B%22highway%22~%22%5E%28motorway%7Ctrunk%7Cprimary%7Csecondary%7Ctertiary%7Cunclassified%29%24%22%5D%2837.7655%2C-122.8847%2C38.6648%2C-121.7400%29%3Bout%20geom%20qt%3B
- **Verdict: usable with caveats.** only 5 aftershocks in the first 12 h (under 30: the plan must blend in synthetic events, EC-3); only 9 later aftershocks to validate on (under 100); road or terrain check did not run, pool is not feasibility-checked.

### Monte Cristo Range 2020 (nn00725272)

- ComCat: M 6.5, 2020-05-15T11:03:27.176000+00:00, lat 38.1689, lon -117.8497, depth 2.7 km ("Monte Cristo Range, NV Earthquake"). Matches the `BENCHMARKS` registry: yes.
- Study radius: 50.0 km.
- Aftershocks M >= 2.5: 161 in the first 12 h, 410 from 12 h to 7 days.
- Permanent stations: 18. By network: IM (11), NN (6), NP (1).
- Temporary stations: 10. By network: 8P (2), GS (1), NN (7).
- Candidate pool: 1678 points. Filter funnel: grid 1961 -> on_land 1961 -> slope 1891 -> station_gap 1685 -> rupture_gap 1678.
- Roads checked: **no**; terrain checked: yes.
- **Warning:** Overpass unavailable, road filter skipped (grid and terrain only): FEED_UNAVAILABLE: overpass-api.de failed after 4 attempts (TimeoutError: The read operation timed out): https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%5Btimeout%3A25%5D%3Bway%5B%22highway%22~%22%5E%28motorway%7Ctrunk%7Cprimary%7Csecondary%7Ctertiary%7Cunclassified%29%24%22%5D%2837.7192%2C-118.4217%2C38.6186%2C-117.2777%29%3Bout%20geom%20qt%3B
- **Verdict: usable with caveats.** road or terrain check did not run, pool is not feasibility-checked.

### Anchorage 2018 (ak018fcnsk91)

- ComCat: M 7.1, 2018-11-30T17:29:29.330000+00:00, lat 61.3464, lon -149.9552, depth 46.7 km ("1 km SE of Point MacKenzie, Alaska"). Matches the `BENCHMARKS` registry: yes.
- Study radius: 112.2 km.
- Aftershocks M >= 2.5: 324 in the first 12 h, 338 from 12 h to 7 days.
- Permanent stations: 71. By network: AK (28), AT (1), AV (3), GD (1), NP (35), PN (1), TA (2).
- Temporary stations: 8. By network: GM (8).
- Candidate pool: 801 points. Filter funnel: grid 9917 -> on_land 9016 -> slope 7549 -> near_road 1086 -> station_gap 808 -> rupture_gap 801.
- Roads checked: yes (Overpass answer 7.2 MB); terrain checked: yes.
- **Verdict: usable.**

### Ferndale 2022 (nc73821036)

- ComCat: M 6.4, 2022-12-20T10:34:24.770000+00:00, lat 40.5250, lon -124.4230, depth 17.91 km ("15km WSW of Ferndale, CA"). Matches the `BENCHMARKS` registry: yes.
- Study radius: 50.0 km.
- Aftershocks M >= 2.5: 48 in the first 12 h, 20 from 12 h to 7 days.
- Permanent stations: 22. By network: BK (6), NC (5), NP (7), PB (4).
- Temporary stations: 1. By network: NC (1).
- Candidate pool: 252 points. Filter funnel: grid 1961 -> on_land 681 -> slope 547 -> station_gap 252 -> rupture_gap 252.
- Roads checked: **no**; terrain checked: yes.
- **Warning:** Overpass unavailable, road filter skipped (grid and terrain only): FEED_UNAVAILABLE: overpass-api.de failed after 4 attempts (TimeoutError: The read operation timed out): https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%5Btimeout%3A25%5D%3Bway%5B%22highway%22~%22%5E%28motorway%7Ctrunk%7Cprimary%7Csecondary%7Ctertiary%7Cunclassified%29%24%22%5D%2840.0753%2C-125.0146%2C40.9747%2C-123.8314%29%3Bout%20geom%20qt%3B
- **Verdict: usable with caveats.** only 20 later aftershocks to validate on (under 100); road or terrain check did not run, pool is not feasibility-checked.

### Puerto Rico 2020 (pr2020007007)

- ComCat: M 6.4, 2020-01-07T08:24:27.370000+00:00, lat 17.9578, lon -66.8113, depth 6 km ("4 km SSE of Indios, Puerto Rico"). Matches the `BENCHMARKS` registry: yes.
- Study radius: 50.0 km.
- Aftershocks M >= 2.5: 137 in the first 12 h, 710 from 12 h to 7 days.
- Permanent stations: 21. By network: PR (21).
- Temporary stations: 9. By network: GS (6), PR (3).
- Candidate pool: 552 points. Filter funnel: grid 1961 -> on_land 932 -> slope 853 -> station_gap 556 -> rupture_gap 552.
- Roads checked: **no**; terrain checked: yes.
- **Warning:** Overpass unavailable, road filter skipped (grid and terrain only): FEED_UNAVAILABLE: overpass-api.de failed after 4 attempts (HTTP 502): https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%5Btimeout%3A25%5D%3Bway%5B%22highway%22~%22%5E%28motorway%7Ctrunk%7Cprimary%7Csecondary%7Ctertiary%7Cunclassified%29%24%22%5D%2817.5081%2C-67.2840%2C18.4075%2C-66.3386%29%3Bout%20geom%20qt%3B
- **Verdict: usable with caveats.** road or terrain check did not run, pool is not feasibility-checked.
## Notes written by hand (interpretation, not measurements)

**Service failures on this run (2026-11-12).**
- **Overpass (roads) failed for five of the six earthquakes**, in two separate passes about 15 minutes
  apart: HTTP 502 or a read timeout after the gateway's 4 attempts each time. The server was slow all
  afternoon (its tiny `/api/status` page took 29 to 34 s on three of four probes, against our 30 s timeout).
  Only Anchorage got a road answer (7.2 MB). We stopped retrying after the second pass rather than keep
  loading a public service. Failed responses are not cached, so re-running the script retries only those five.
- For those five, the pool is **grid plus terrain only** and `feasibility_checked = False`, exactly the
  EC-5 fallback. Their pool sizes are therefore **upper bounds, not usable numbers**. Anchorage shows how
  large the gap can be: the road filter cut 7,549 points to 1,086 (about 86% removed).
- USGS ComCat, the IRIS/EarthScope station service (through its redirect to `service.earthscope.org`)
  and the AWS terrain tiles answered every request. No ComCat query came near the 20,000-row limit.

**Where the data is thin.**
- **South Napa 2014: 5 aftershocks of M >= 2.5 in the first 12 h and 9 afterwards.** That is far too few to
  plan on or to validate against. It is usable only with a lower magnitude cut-off (not tested here) or as
  a synthetic-aftershock case. The script's rule labels it "usable with caveats"; we would read that as
  weak.
- **Ferndale 2022: 48 early and 20 later aftershocks**, and only about a third of the grid is on land. The
  20 validation events make any held-out score noisy.
- **Temporary stations are a rough proxy.** Ridgecrest's 493 are mostly network 3J (456 stations, which
  looks like a dense short-term array, not a classic rapid-response deployment); South Napa's 7C (223) is
  similar. Network codes were not looked up, so what each deployment was is **unverified**. Ferndale (1)
  and Anchorage (8, all GM) offer little for a comparison with a real deployment.
- **Permanent-station counts include every listed station** (strong-motion sites included), so "187
  permanent stations" for South Napa overstates the network a locator would use.

**Not verified.**
- The Overpass path has run end to end for real only twice: Anchorage (full radius) and the small South
  Napa test fixture. Behaviour on the largest box (Ridgecrest, 112 km radius) is untested; the query asks
  the server for a 25 s limit and may need splitting or a longer limit there.
- "On land" means elevation above 0 m in the tiles. Lakes pass; land below sea level fails. Tile
  elevations over water were not checked against a coastline dataset.
- The 30 s gateway timeout is what the spec asks for, but it is shorter than Overpass needed today.
