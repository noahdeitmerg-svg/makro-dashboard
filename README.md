# Makro Dashboard (DeFi Circle Rebuild)

## Sofort ansehen
`dashboard.html` doppelklicken — läuft mit der mitgelieferten, exakt kalibrierten Historie (Stand 10.06.2026).

## Auf Live-Daten umstellen
1. `api_keys.env.example` → umbenennen in `api_keys.env`, FRED-Key eintragen (kostenlos: fred.stlouisfed.org → API Keys)
2. `pip install -r requirements.txt`
3. `python update_data.py`  → schreibt `data.js` neu, Dashboard einfach neu laden
4. Optional: `pboc_assets.csv` (Datum,Wert in T USD) für PBoC-Livedaten → Data Quality 100/100
5. Täglich automatisch: Windows-Aufgabenplanung → `python update_data.py` z.B. 09:00

## Dateien
- `dashboard.html` — komplettes Dashboard (8 Chart-Panels + alle Textsektionen)
- `data.js` — Datenpaket (wird vom Updater überschrieben)
- `update_data.py` — Live-Daten-Pipeline (FRED, Yahoo, optional CSV)
- `macro_engine.py` — MRI-Formel, Regime-Logik, Conviction
- `build_payload.py` — baut data.js aus Serien (von Demo-Generator UND Live-Updater genutzt)
- `gen_demo.py` — Generator der kalibrierten Demo-Historie
- `MACRO_ENGINE.md` — alle finalen Formeln + Kalibrierungs-Doku
