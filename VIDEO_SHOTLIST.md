# QuakeNet-Q: video shot list

For the team. Use this with `VIDEO_SCRIPT.md` (the narration) and `video/subtitles_en.srt` (the
subtitles, ready to import into CapCut, Premiere, DaVinci Resolve or YouTube).

**Length:** 2:50, hard limit 3:00. **Format:** 1920×1080, 30 fps. **Voice:** one narrator, recorded
separately and laid over the visuals.

## Look and feel

- **Colours (match the website):** pale mist background, dark ink text, lime accent `#c6f35c` for
  highlights, deep green `#3d6e0c` for accent text. No purple, no neon.
- **Font for on-screen text:** IBM Plex Sans (headings), IBM Plex Mono (numbers). Both are free on Google Fonts.
- **Motion:** slow push-ins (Ken Burns, 105% zoom over the shot), simple cross-fades. No spinning transitions.
- **Numbers on screen:** show every number the narrator says, large, for 2 to 3 seconds.
- **Music:** quiet ambient track at about -25 dB under the voice (YouTube Audio Library or Pixabay
  Music, both free). Fade out in the last 3 seconds.

## Where the images come from

| Source | Use for | Licence note |
|---|---|---|
| `figures/` in the repo | Map, architecture, system diagram, results charts | Ours |
| https://quakenet-q.vercel.app | Landing globe, console pages, demo | Ours. The laptop and tunnel must be on for live data |
| USGS media library (usgs.gov, search "Ridgecrest earthquake 2019") | Real damage, surface rupture, field crews installing seismometers | USGS images are generally public domain; caption "Image: USGS" and check each image's page |
| Wikimedia Commons (search "seismometer", "seismograph", "aftershock") | Close-ups of instruments and seismogram traces | Check the licence on each file and credit it |
| AI image generator (optional) | Only for the opening "city" mood shot if no free photo fits | Do not present it as a real event; keep it generic |

Avoid news-channel footage and other copyrighted video.

## Shot by shot

### Shot 1 · 0:00–0:15 · The hook
- **Show:** a city skyline at dusk, very slow push-in. A faint seismogram line runs across the bottom
  third and spikes once when the narrator says "massive earthquake". At "aftershocks", small dots pulse on the image.
- **Make it:** a free photo (Pixabay or Unsplash, search "city skyline dusk"). Add the seismogram as a
  drawn line in the editor, or crop the seismograph band from the website's header.
- **On-screen text:** "Aftershocks: days, weeks, months" (appears at 0:08).
- **Optional AI prompt:** *"Wide photograph of a modern city skyline at dusk after an earthquake, light
  dust in the air, calm and serious mood, muted blue-grey tones, no fire, no people in distress,
  documentary style, 16:9"*

### Shot 2 · 0:15–0:40 · The problem
- **0:15–0:22:** a real photo of a portable seismometer being installed (USGS), or a close-up of a seismometer (Wikimedia).
  Text: "Seismometers measure ground vibration".
- **0:22–0:32:** `figures/map.png` cropped so the blue rings are hidden (crop or mask the right side).
  As the narrator lists "costs money", "hard to reach" and "same information twice", show three small labels
  one at a time: "cost", "hard to reach", "redundant".
- **0:32–0:40:** fade to the mist background. Big text, two lines, word by word:
  "Not more sensors." then "The right locations." (the second line in lime).

### Shot 3 · 0:40–0:50 · Introduce QuakeNet-Q
- **Show:** the landing page of https://quakenet-q.vercel.app, top of the page, with the globe turning. Screen-record 10 s.
- **On-screen text:** "QuakeNet-Q · Qiskit Fall Fest 2026 · Disaster Response"
- **Lower third:** team names: Muhammad Abdullah · Muhammad Hassaan-ul-Mustafa · Rafia Ali

### Shot 4 · 0:50–1:05 · How the agent works
- **Show:** `figures/system.png`, top half only (the agent loop). Highlight each box as it is mentioned:
  "USGS live feed" → "Trigger" → "First plan" → "Plan". Use a lime rectangle or a soft glow.
- **Alternative:** screen-record the website's Live feed page, then its Settings page showing the trigger magnitude.
- **On-screen text:** "Starts by itself" · "Real USGS + EarthScope data" · "D-optimality score"

### Shot 5 · 1:05–1:35 · The quantum part
- **1:05–1:12:** a simple 10-dot grid (10 sites), with 4 dots lighting up in lime. Text: "4 of 10 sites = 210 networks".
  Make it in Canva or PowerPoint: 10 circles, animate 4.
- **1:12–1:22:** the website's circuit view (the new circuit simulation on the Quantum page), or `figures/architecture.png`
  zoomed into the middle column. Text: "1 site = 1 qubit" · "Dicke state + XY mixer: always exactly 4" · "Exact score: 385 terms".
- **1:22–1:28:** `figures/architecture.png`, full view, slow pan left to right. Text: "Checked against every possible network".
- **1:28–1:35:** `figures/system.png`, bottom loop ("Hourly check" → "Re-plan"). Text: "Re-plans every hour".

### Shot 6 · 1:35–2:10 · Live demo (screen recording)
Record this on the real site with the laptop, API and tunnel running. Rehearse once first.
1. **Settings page (5 s):** point the cursor at the trigger magnitude field. Text: "A scientist sets the trigger magnitude".
2. **Plan page (12 s):** start a Ridgecrest plan with the team passcode; show the result appearing: the chosen sites and the "quantum agreed with exact" line.
3. **Map (6 s):** the candidate sites, with the chosen four highlighted.
4. **Monitor page (12 s):** play the replay, hour by hour. Pause on hour 1 ("re-plan: centroid moved 7.9 km") and on the final hour.
- Zoom the recording to 125% in the editor so the text is readable. Hide the bookmarks bar and other tabs.
- Never show the passcode, the backend address or a terminal window.
- **If the laptop is off:** the site shows saved results. Record the Monitor page from those instead and skip step 2.

### Shot 7 · 2:10–2:30 · Results
- **2:10–2:15:** big number on the mist background: "15 / 15" with the caption "runs found the best network".
- **2:15–2:20:** `figures/qaoa_performance.png` (left chart). Text: "up to 11% per measurement · random: 0.48%".
- **2:20–2:27:** `figures/location_test.png`. Text: "3.0 km → 2.3 km location error (simulated)". Highlight the QAOA bar in lime.
- **2:27–2:30:** text: "24-hour replay: about 20 seconds".

### Shot 8 · 2:30–2:45 · Honest limits
- **Show:** the Caveats table from the report (Chapter 9) or a clean slide with three short lines:
  - "No quantum speedup at this size"
  - "Field rule as good or better on 4 of 5 other earthquakes"
  - "Next: a better score, not a faster search"
- Keep it calm and plain: the brief rewards honesty, so give it a full 15 seconds.

### Shot 9 · 2:45–2:50 · Close
- **Show:** the mist background with the line "The right sensors, in the right places, within minutes of the quake."
- Then the repository link and the live site link, small, for the last 2 seconds.

## Final checks before upload

- [ ] Total length under 3:00.
- [ ] Subtitles imported from `video/subtitles_en.srt` and aligned with the voice (nudge the timings if your read is faster or slower).
- [ ] Every number on screen matches the narration.
- [ ] No passcode, token, tunnel address or terminal visible.
- [ ] Photo credits ("Image: USGS", Wikimedia authors) in the last frame or the video description.
- [ ] Upload to Google Drive, set "Anyone with the link", and test the link in a private window.
