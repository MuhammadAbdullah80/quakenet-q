# C01 USGS ComCat FDSN Event API
- URL: https://earthquake.usgs.gov/fdsnws/event/1/
- Type: official API doc + live test | Scores (1-5): reliability 5, relevance 5, ease 5
- Verbatim (WebFetch of doc): "The service limits queries to 20000." (HTTP 400 beyond). Doc page mentions no API key/authentication. Params: starttime,endtime,minlatitude,maxlatitude,minlongitude,maxlongitude,minmagnitude,limit,offset,orderby; `count` method same params.
- Live test (run 2026-11-12, no key):
  https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2019-07-06&endtime=2019-07-08&minlatitude=35.4&maxlatitude=36.1&minlongitude=-117.9&maxlongitude=-117.2&minmagnitude=3.5
  -> HTTP 200, metadata.count = 261 events, 196 KB. First: "M 3.9 - 23km N of Ridgecrest, CA", coords [-117.6685, 35.8303333, 4.97] (lon,lat,depth km).
- count endpoint: .../fdsnws/event/1/count?starttime=2019-07-04&endtime=2019-07-12&minlatitude=35.4&maxlatitude=36.1&minlongitude=-117.9&maxlongitude=-117.2&minmagnitude=3.0 -> 908
- Turkey 2023 test: starttime=2023-02-06&endtime=2023-02-09, lat 36-39, lon 35-39, minmag 4.5 -> 132 events.
- Relevance: aftershock catalogue (demand points weighted by magnitude) is trivially obtainable.
