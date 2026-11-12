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

**Update, later on 2026-11-12: road retry.** The Overpass query was retried once for each of the five
failed earthquakes (one attempt with a 120 s timeout; after a failure a 30 s pause and one more attempt;
then stop). Ridgecrest and South Napa got HTTP 502 on the first attempt and an answer on the second;
Monte Cristo Range, Ferndale and Puerto Rico answered on the first. Answer sizes: Ridgecrest 13.2 MB,
South Napa 42.7 MB, Monte Cristo Range 1.5 MB, Ferndale 4.2 MB, Puerto Rico 12.0 MB. All six pools are
now road-checked; the tables above were regenerated from the cache after the retry. The road query box is
built from the registry's 4-decimal epicentre (ComCat's own coordinates differ in the 5th decimal, about
10 m, which would otherwise change the query text and miss the cache). The earlier statement that
"behaviour on the largest box (Ridgecrest) is untested" no longer holds: it answered in 51 s.
