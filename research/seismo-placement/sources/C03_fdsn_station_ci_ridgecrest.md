# C03 FDSN station service (IRIS/EarthScope and SCEDC)
- URLs: https://service.iris.edu/fdsnws/station/1/query ; https://service.scedc.caltech.edu/fdsnws/station/1/query
- Type: live API test | Scores: reliability 5, relevance 5
- Working URL (both IRIS and SCEDC returned HTTP 200, identical output, no key):
  .../fdsnws/station/1/query?network=CI&level=station&format=text&minlatitude=35.4&maxlatitude=36.1&minlongitude=-117.9&maxlongitude=-117.2&starttime=2019-07-04&endtime=2019-07-12   (SCEDC needs full timestamps e.g. 2019-07-04T00:00:00; date-only start/endtime accepted at IRIS test; SCEDC date-only for startbefore/endafter gave 400 and I did not retest starttime date-only there)
- Output: 14 CI stations, pipe-delimited text: Network|Station|Lat|Lon|Elev|SiteName|Start|End, e.g.
  CI|CLC|35.81574|-117.59751|775.0|China Lake|1948-07-08 ; CI|SRT|35.69235|-117.75051 ; CI|WBM|35.60839|-117.89049 ; CI|SLA|35.89095|-117.28332 ; CI|CCC|35.52495|-117.36453 ; CI|LRL|35.47954|-117.68212 ; CI|MPM|36.05799|-117.48901 ; CI|WVP2|35.94939|-117.81769 ...
- Note: Box includes dense stations; east (lon>-117.4) and south-east are sparse -> natural "gaps". Several (TOW2, WCS2, WRC2, WRV2, WVP2) started July 2014, JRC2 2004.
