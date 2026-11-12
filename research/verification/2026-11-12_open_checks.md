# Open checks, 2026-11-12

Method note: quotes come from WebFetch/WebSearch output (a summarising model sat between me and the pages). Re-check exact wording before citing in a paper. Items I could not verify are marked "unverified".

## 1. Nodal seismometers record to internal memory and are collected later
Verdict: PARTLY CONFIRMED (continuous on-board recording is supported; explicit "no telemetry / internal memory" wording not found in a primary source; exceptions not verified).
- USGS data release (Goldman, Catchings, Celebi et al., DOI 10.5066/P1S2HOXT): 127 SmartSolo IGU-16HR nodes "recorded continuously using GPS for time-correction"; grid array recorded about July to December 2023. https://www.usgs.gov/data/nodal-seismometer-recordings-aftershocks-2023-kahramanmaras-turkiye-earthquake-sequence (via search snippet; the page itself fetched empty)
- AFAD-affiliated abstract: "many of them were retrieved by early December 2023" (paraphrase from search result; supports later collection). https://seismosoc.secure-platform.com/a/solicitations/35/sessiongallery/901/application/11188
- Ridgecrest (Catchings et al., SRL 91(6), 10.1785/0220200203): nodes "recorded continuously, allowing us to collect ~14TB of data, which are available at the IRIS DMC". https://central.scec.org/node/45861
- Not found: any sentence saying nodes lacked telemetry; manufacturer or PASSCAL spec for internal storage; any telemetered broadband example in these deployments (the EAST array abstract lists 10 broadband stations but telemetry status is unstated). The USGS Ridgecrest rapid-deployment paper (pubs.usgs.gov/publication/70212873) returned 403.
- Project should say: "Rapid-deployment nodal arrays (e.g. Ridgecrest 2019, Kahramanmaras 2023) record continuously and their data were archived after the instruments were retrieved; we assume no real-time telemetry for nodes." Flag "a few telemetered broadband stations send live" as unverified.

## 2. Timing of USGS focal mechanism / moment tensor in ComCat
Verdict: UNVERIFIED as an official figure. Only indirect evidence.
- USGS products page defines the products but gives no latency: "Seismic moment-tensor solutions and centroid parameters describing the earthquake source." https://earthquake.usgs.gov/data/products/
- Sipkin 1994 (USGS): "an estimate of the moment tensor can usually be produced within 20 minutes of the arrival of the broadband P-waveform data". https://www.usgs.gov/publications/rapid-determination-global-moment-tensor-solutions
- W-phase paper (2009, NEIC): reliable results for Mw > 7.0 "within ~20 minutes". https://www.usgs.gov/publications/source-inversion-w-phase-realtime-implementation-and-extension-low-magnitudes
- Case: Tohoku 2011 W-phase reported about 22 min; later automatic solution about 62 min (Ritsema et al. Elements; single event). Monte Cristo 2020 study could not get aftershock moment tensors within 2 h of the mainshock because of coda (arXiv 2102.08509).
- Project should say: "Moment tensors for large global events typically appear tens of minutes to about an hour after origin; for smaller or regional events they may take longer or never appear. No USGS-guaranteed latency." Do not state a fixed number.

## 3. USGS GeoJSON feeds and FDSN event API limits
Verdict: CONFIRMED for update rate and per-query limit; polling guidance UNVERIFIED (policy page 404 at earthquake.usgs.gov/earthquakes/feed/policy.php).
- Feeds: "Updated every minute." https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php (no polling guidance on that page).
- FDSN event: "The service limits queries to 20000, and any that exceed this limit will generate a HTTP response code "400 Bad Request"." https://earthquake.usgs.gov/fdsnws/event/1/
- Same page: time/area limits "are being evaluated and are not enforced yet"; no request-rate limit stated; automated applications should use real-time feeds "whenever possible".
- Project should say: "Feeds refresh every minute; we poll no faster than that (our choice, not a USGS rule). Event API caps at 20,000 events per query; no documented request rate limit."

## 4. IRIS/EarthScope FDSN station service
Verdict: PARTLY CONFIRMED (general guidelines exist, from the older ds.iris.edu page; no station-specific numeric limit found).
- "Users should limit usage to no more than 5 concurrent connections to any combination of web services." https://ds.iris.edu/ds/nodes/dmc/services/usage/
- "Users should limit their clients to no more than 10 connections per second". Same URL.
- Notice found in search: station service moving to service.earthscope.org, redirects from service.iris.edu starting 29 June 2026; clients must follow redirects (from search summary; not opened). https://ngf.earthscope.org/news/fdsnws-station-web-service-moving
- Project should say: "Keep to at most 5 concurrent connections and 10 connections per second; follow redirects to service.earthscope.org."

## 5. Overpass API public instance
Verdict: CONFIRMED.
- "less than 10,000 queries per day" and "download less than 1 GB data per day"; total processing "no more than 10 minutes"; regular use: "divide those numbers by 100". https://wiki.openstreetmap.org/wiki/Overpass_API
- Headers: add "`User-Agent` or `Referer` headers to requests that uniquely identify your app." On HTTP 429 or 406 "pause for 30 seconds before making a new request."
- Project should say: "Identify the app via User-Agent, cache results, stay far below 10k queries/day and 1 GB/day, back off 30 s on 429/406."

## 6. Tailscale Funnel
Verdict: CONFIRMED.
- Enable: Access controls page, "Expand the Funnel section and select Add Funnel to policy" (adds a nodeAttrs entry with `"attr": ["funnel"]`). Also needs MagicDNS and HTTPS certificates enabled (third-party guide; version 1.38.3+). https://tailscale.com/kb/1223/funnel
- Ports: "Funnel can only listen on ports 443, 8443, and 10000." Same page.
- Limits: "Traffic sent over a Funnel is subject to non-configurable bandwidth limits." No numeric request limit documented.
- CT logs: "All TLS certificates on the web are recorded in the Certificate Transparency (CT) append-only public ledger... Notably, this includes the fully qualified domain name of your devices." and "the machine names are still published in the public ledger." https://tailscale.com/docs/how-to/set-up-https-certificates.md
- Project should say: "Enabling HTTPS publishes the machine name (machine.tailnet.ts.net) in public CT logs; pick a non-sensitive hostname. Funnel uses 443/8443/10000 with unpublished bandwidth caps."

## 7. Strutz & Curtis (arXiv 2411.11015)
Verdict: CONFIRMED, published.
- Strutz, D., & Curtis, A. (2025). Near-real-time design of experiments for seismic monitoring of volcanoes. Seismica, 4(1). https://doi.org/10.26443/seismica.v4i1.1452 (published 2025-02-14). https://seismica.library.mcgill.ca/article/view/1452
- Project should say: cite the Seismica version, not the arXiv preprint.

## 8. Existing operational tool recommending temporary sites
Verdict: NO CONTRADICTION FOUND (none found, not proven absent).
- Searched USGS, GFZ, INGV, GeoNet, NIED/JMA, EarthScope RAMP. Found only research or manual procedures: Hardt & Scherbaum 1994 (simulated-annealing aftershock network design); INGV SNES method (EGU 2011, site ranking by location-error reduction; research method); CTBTO automated network optimisation abstract; USGS "Rapid station and network quality analysis for temporary deployments" (https://pubs.usgs.gov/publication/70204925; assesses deployed stations, not recommends sites); manual site-scouting procedures (France MACIV, Austria).
- RAMP: only the 2003 USGS OFR 03-15 agreement found; no automated recommendation tool. EarthScope RAMP current docs not retrieved.
- Project should say: "We found no operational tool or agency procedure that automatically recommends temporary sites; prior art exists as research (Hardt & Scherbaum 1994; INGV SNES) and the closest operational analogue is USGS post-deployment quality analysis." Cite the prior art to avoid overclaiming novelty.
