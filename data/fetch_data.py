"""Fetch and cache the real-world inputs for QuakeNet-Q.

Sources (public, no API key):
  * USGS ComCat FDSN event service  -> aftershocks of the 2019 Ridgecrest sequence
  * IRIS/EarthScope FDSN station service -> permanent CI (SCSN) stations in the area

Cached JSON files are committed to the repo so the experiment runs offline and
reproducibly. Re-run this script only to refresh the cache:

    python data/fetch_data.py
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent

# Study box around the M7.1 rupture (Ridgecrest, California).
BOX = dict(minlatitude=35.4, maxlatitude=36.1, minlongitude=-117.9, maxlongitude=-117.2)

# One week from the day of the M7.1 mainshock (2019-07-06 03:19 UTC), M >= 3.0.
EVENT_URL = (
    "https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson"
    "&starttime=2019-07-06&endtime=2019-07-13"
    "&minlatitude={minlatitude}&maxlatitude={maxlatitude}"
    "&minlongitude={minlongitude}&maxlongitude={maxlongitude}"
    "&minmagnitude=3.0&orderby=time-asc"
).format(**BOX)

STATION_URL = (
    "https://service.iris.edu/fdsnws/station/1/query?network=CI&level=station&format=text"
    "&minlatitude={minlatitude}&maxlatitude={maxlatitude}"
    "&minlongitude={minlongitude}&maxlongitude={maxlongitude}"
    "&starttime=2019-07-04&endtime=2019-07-12"
).format(**BOX)


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "quakenet-q-hackathon"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


def fetch_events() -> list[dict]:
    gj = json.loads(_get(EVENT_URL))
    out = []
    for f in gj["features"]:
        lon, lat, depth = f["geometry"]["coordinates"]
        out.append(
            dict(id=f["id"], time_ms=f["properties"]["time"], mag=f["properties"]["mag"],
                 lat=lat, lon=lon, depth_km=depth)
        )
    return out


def fetch_stations() -> list[dict]:
    lines = [l for l in _get(STATION_URL).splitlines() if l and not l.startswith("#")]
    seen, out = set(), []
    for l in lines:
        net, sta, lat, lon, elev, name, *_ = l.split("|")
        if sta in seen:  # a station can appear once per epoch
            continue
        seen.add(sta)
        out.append(dict(net=net, sta=sta, lat=float(lat), lon=float(lon), name=name))
    return out


def main() -> None:
    events = fetch_events()
    stations = fetch_stations()
    meta = dict(event_url=EVENT_URL, station_url=STATION_URL,
                licence="USGS ComCat data are U.S. public domain; station metadata via IRIS/EarthScope FDSN.")
    (DATA_DIR / "events.json").write_text(json.dumps(dict(meta=meta, events=events), indent=1))
    (DATA_DIR / "stations.json").write_text(json.dumps(dict(meta=meta, stations=stations), indent=1))
    print(f"cached {len(events)} events and {len(stations)} stations")


if __name__ == "__main__":
    main()
