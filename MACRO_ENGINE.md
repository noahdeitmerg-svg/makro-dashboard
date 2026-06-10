# MACRO_ENGINE.md — Finale Formeln (Rebuild DeFi Circle, kalibriert 07.06. + 10.06.2026)

## MRI-Formel (verifiziert)
```
MRI = 50 + (Liquidity-50)·0.25 + (Growth-50)·0.25 + (Credit-50)·0.20
         + (RiskAppetite-50)·0.15 − (USDStress-50)·0.15      → clamp 0–100
```
10.06.2026: 42.0/52.4/52.5/59.9/58.4 → **MRI 49.33** ✓ (Original 49.3)

## Sub-Scores (Live-Modus, update_data.py)
Alle Scores = rollierende Perzentil-Normalisierung über 2200 Tage (`pct_rank`), Datenbasis volle Historie ab 1990.
Gewichte am 10.06.2026 mit Live-Daten exakt gegen die Original-Sub-Scores gelöst (Solver: `calib2.py`;
Ist: 42.0 / 52.4 / 52.5 / 59.9 / 58.4 → MRI 49.3, Regime TRANSITION ✓):
- **Liquidity** = 0.507·pct(Δ90 Global-CB) + 0.330·pct(Δ90 M2) + 0.162·pct(Level Global-CB)
- **Growth** = 0.225·pct(Payrolls YoY) + 0.247·(100−pct(Claims)) + 0.259·(100−pct(Δ180 Unemployment)) + 0.269·pct(10Y−3M)
- **Credit** = 0.135·(100−pct(HY)) + 0.085·(100−pct(IG)) + 0.78·(100−pct(Δ30 HY))  *(stark momentum-getrieben — nur so ist „neutral 52.5" bei historisch engen Spreads (HY 2.75) erreichbar)*
- **Risk Appetite** = 0.265·pct(Δ90 NASDAQ/SPX) + 0.208·pct(Δ90 SPX/Oil) + 0.527·(100−pct(VIX))
- **USD Stress** = 0.458·pct(DXY) + 0.146·pct(Δ30 DXY) + 0.396·pct(VIX)   *(im MRI subtrahiert)*

**Spread-Splice:** FRED liefert die ICE-BofA-Spreads (BAMLH0A0HYM2/BAMLC0A0CM) nur ~3 Jahre zurück.
Davor werden Moody's-Spreads (BAA10Y/AAA10Y, ab 1985) verwendet, skaliert auf das Niveau-Verhältnis
der Überlappungsperiode. FX für ECB/BoJ-Umrechnung: FRED DEXUSEU/DEXJPUS.

Hilfswerkzeug: `python calib_probe.py` gibt die aktuellen Komponenten-Perzentile aus,
falls später nachkalibriert werden soll.

## Regime-Klassifikation (kalibriert gegen beide Snapshots)
Basis-Zone aus MRI (0/25/40/55/70 → CRISIS/DEFENSIVE/TRANSITION/CONSTRUCTIVE/RISK-ON), dann Override:
```
WENN USD-Stress ≥ 65 UND USD-Stress-7D-Änderung > −5  →  eine Stufe abwerten
```
- 07.06.: MRI 52.1, Stress 68.7, 7D ≈ −2.3 → Downgrade → **DEFENSIVE** ✓
- 10.06.: MRI 49.3, Stress 58.4 (< 65) → kein Override → **TRANSITION** ✓

## Conviction (kalibriert: 10.06→50, 07.06→46)
```
devs = [L−50, G−50, C−50, R−50, 50−U];  Conviction = clamp(57.9 − 1.13·std(devs), 0, 100)
```

## Top Drivers (nur Makro-Säulen)
`Driver = Gewicht × (bullishe 14-Tage-Änderung) / 4` — Credit invertiert (fallender Druck = supportiv).
10.06.: Liquidity −0.53 ✓ · Credit +0.10 ✓ · Growth −0.04 ✓

## VIX-Support
`Support = clamp(100 − (VIX−10)·(100/21.4), 0, 100)` → VIX 18.92 → **58** ✓

## What-Changed-Labels
MRI/Liquidity/Growth: fallend = worsening · USD Stress & Credit: fallend = improving.

## Bekannte Inkonsistenz im Original (dokumentiert)
„MRI 30D −13.5 pts" ist mit den publizierten Sub-Score-30D-Deltas + Formel NICHT reproduzierbar
(Risk Appetite müsste vor 30 Tagen > 100 gewesen sein). Das Original glättet den MRI offenbar oder
berechnet Deltas anders. Lösung hier: MRI-Chartserie wird historisch eigenständig geführt; der
aktuelle Wert ist immer exakt formelkonsistent.

## Demo- vs. Live-Daten
Mitgelieferte `data.js` = rekonstruierte 2200-Tage-Historie, an JEDEM publizierten Wert beider
Snapshots exakt verankert (alle Zahlen der Checkliste matchen). `python update_data.py` ersetzt
sie durch echte API-Daten (FRED/Yahoo); die Live-Sub-Scores weichen dann naturgemäß von den
proprietären Original-Scores ab und können über die Gewichte oben nachkalibriert werden.
