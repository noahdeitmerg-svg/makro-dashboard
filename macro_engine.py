# -*- coding: utf-8 -*-
"""DeFi Circle Macro Regime Engine - Nachbau (kalibriert gegen Snapshots 07.06. + 10.06.2026)"""
import math

WEIGHTS = {'liquidity':0.25,'growth':0.25,'credit':0.20,'risk':0.15,'usd_stress':0.15}

def compute_mri(s):
    mri = 50.0
    mri += (s['liquidity']-50)*WEIGHTS['liquidity']
    mri += (s['growth']-50)*WEIGHTS['growth']
    mri += (s['credit']-50)*WEIGHTS['credit']
    mri += (s['risk']-50)*WEIGHTS['risk']
    mri -= (s['usd_stress']-50)*WEIGHTS['usd_stress']
    return max(0.0,min(100.0,mri))

def conviction(s):
    """Kalibriert: 10.06 -> 50, 07.06 -> 46. Linear in der Streuung der gerichteten Abweichungen."""
    devs = [s['liquidity']-50, s['growth']-50, s['credit']-50, s['risk']-50, 50-s['usd_stress']]
    m = sum(devs)/len(devs)
    std = math.sqrt(sum((d-m)**2 for d in devs)/len(devs))
    return int(round(max(0,min(100, 57.9 - 1.13*std))))

def zone(mri):
    if mri < 25: return 'CRISIS'
    if mri < 40: return 'DEFENSIVE'
    if mri < 55: return 'TRANSITION'
    if mri < 70: return 'CONSTRUCTIVE'
    return 'RISK-ON'

ORDER = ['CRISIS','DEFENSIVE','TRANSITION','CONSTRUCTIVE','RISK-ON']
COLORS = {'CRISIS':'#8b0000','DEFENSIVE':'#e03131','TRANSITION':'#f5b942','CONSTRUCTIVE':'#74c476','RISK-ON':'#2f9e44'}

def classify_regime(mri, usd_stress_level, usd_stress_7d_chg):
    """Kalibrierte Regel: Basis-Zone aus MRI; Downgrade um 1 Stufe wenn
    USD-Stress hoch (>=65) und NICHT schnell fallend (7D-Aenderung > -5)."""
    z = zone(mri)
    if usd_stress_level >= 65 and usd_stress_7d_chg > -5:
        z = ORDER[max(0, ORDER.index(z)-1)]
    return z

def delta(series, days):
    return series[-1] - series[-1-days]

def pct(series, days):
    base = series[-1-days]
    return (series[-1]/base - 1)*100 if base else 0.0
