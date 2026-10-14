# Crypto Lock: social and app impersonation monitoring

A Digital Risk Protection app. An organisation defines what is official; the platform scans social
platforms and app stores for fake profiles, fake brand pages, scam accounts and look-alike apps, scores each
one, and explains why it was flagged.

## Run it

### Beginner setup (Windows)

1. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/). During setup, enable **Add Python to PATH**.
2. Open PowerShell in this project folder.
3. Create and activate an isolated environment:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

4. Install the required packages and start the app:

```bash
pip install -r requirements.txt
streamlit run app.py          # web UI
python cli_demo.py            # same pipeline in the terminal
python -m unittest discover -s tests
```

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that PowerShell window, then activate again.

In the UI: **Brand profile → Load demo brand (PayNova) → Run scan → Detections**.
Tick a source under "Simulate an outage" to see unavailable sources handled without stopping the scan.

## How it maps to the brief

| Brief | Where |
|---|---|
| Brand profile: assets, validation, drives detection | `drp/profile.py`, Brand profile page. Handles, package ids, domains and logo are validated. Official assets double as the exclusion list. |
| Social monitoring | `drp/detect.py` (`_social_signals`), connectors for Instagram, X, Facebook, LinkedIn. Categories: impersonation profile, fake brand page, scam account. |
| App store monitoring | `drp/detect.py` (`_app_signals`): name, logo, description, publisher mismatch, publisher imitating the brand. Google Play and App Store. |
| Official assets not flagged | `Detector.run()` drops exact matches on (kind, platform, id) before scoring. Skipped assets are listed in the UI. |
| Look-alike names (bonus) | `drp/lookalike.py`: character swaps, look-alike characters (0/o, 1/l, Cyrillic), spacing and symbols, added words, typo + added words. |
| Graceful unavailable sources | `drp/scanner.py` catches `SourceUnavailable` per connector; the UI shows a banner and a status table. |

## Architecture

```
Brand profile ──► Connectors (Instagram, X, Facebook, LinkedIn, Google Play, App Store; mock or live)
                        │ candidates
                        ▼
              Official asset exclusion  ◄── official handles / package ids from the profile
                        ▼
   Detection engine: name + look-alike │ logo (dHash) │ description (TF-IDF) │ publisher │ scam wording │ links
                        ▼
              Risk score (noisy-OR) + reasons
                        ▼
        SQLite: brands, official_assets, scans, detections, source_status, reviews
                        ▼
              Dashboard: filter, review (confirm / false positive)
```

## How scoring works

Each signal has a strength from 0 to 1 and a weight. They combine as `score = 1 - Π(1 - weight × strength)`:
one weak signal stays low, several independent ones add up fast.

* A name match on its own tops out around 55 (Medium). It takes name + logo, or name + scam wording, to reach High (70+).
* Scam wording and link signals only count when the account is already linked to the brand (similar name, logo, or brand mention).
* An app by the same publisher as your official app is discounted and labelled "may be an official app missing from your profile".
* Look-alike rules need the whole brand name (or a one-letter slip). Short brand names (under 5 letters) only match exactly.
  `NovaPay`, `PayNow` and `Nova Paint Co.` are not flagged for `PayNova`.

Severity: High ≥ 70, Medium ≥ 40, Low ≥ 20. Anything lower is not reported.

## Swapping in real data

Implement `Connector.fetch(brand) -> list[Candidate]` and raise `SourceUnavailable` when the source can't be reached.
`generate_variants(brand.name)` gives the search terms a live connector should query. `GooglePlayLiveConnector` is a working
example (needs `pip install google-play-scraper`). Social platforms restrict API access, so use an official API or a
licensed data provider rather than scraping.

## Known limits

* Social and app store sources are sample data by default; only the Google Play connector can go live.
* Logo matching uses a perceptual hash: good for copies and recolours, weak against heavy redraws.
* Descriptions use TF-IDF word overlap, not semantic embeddings.
* One brand per database in this prototype (the schema supports more).
* **Demo versus real results:** the built-in social and app-store connectors only read fictional examples. They are labeled **SAMPLE** in the UI and must never be treated as evidence about real accounts. Only the optional Google Play connector performs a live lookup, and it is labeled **LIVE**. There is no live social monitoring yet.
* **Public deployment:** do not expose this prototype to multiple users or put confidential brand data into a public instance. It has no login or access controls, stores one shared brand profile and scan history in SQLite, and most hosted app filesystems are temporary. Add authentication, per-user data separation, durable storage, and abuse controls before making it publicly usable.

## GitHub and deployment checklist

1. Keep `data/`, database files, uploaded logos, credentials, and `.streamlit/secrets.toml` out of Git; `.gitignore` covers these local files.
2. Push the project to a new GitHub repository. Do not upload real brand data or private logos.
3. Before deploying publicly, add authentication, per-user data separation, durable storage, and abuse controls. Streamlit Community Cloud apps are reachable by anyone with the app link unless access control is configured.
4. Once those controls exist, connect the repository to your chosen host and set the app entry point to `app.py`. The current prototype is suitable for local evaluation only.
