# C04 Travel-time model / ObsPy
- Local check: `import obspy` -> ModuleNotFoundError (not installed).
- Conclusion (my reasoning, not a fetched source): for a hackathon, constant Vp ~6.0 km/s (Vs ~3.5) with hypocentral distance sqrt(horizontal^2 + depth^2) using ComCat depth is adequate with numpy only; haversine/equirectangular for lat/lon. Hadley-Kanamori layered model not verified online here; no ObsPy needed. Scores: relevance 4, reliability n/a (not externally verified).
