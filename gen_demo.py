# -*- coding: utf-8 -*-
"""Erzeugt 2200-Tage-Demo-Historie, verankert an den exakten Snapshot-Werten (10.06. + 07.06.2026)."""
import numpy as np, json, datetime as dt
from macro_engine import *

rng = np.random.default_rng(42)
END = dt.date(2026,6,10); N = 2200
dates = [END - dt.timedelta(days=N-1-i) for i in range(N)]
didx = {d:i for i,d in enumerate(dates)}
def ix(y,m,day=1): return didx.get(dt.date(y,m,day), max(0,(dt.date(y,m,day)-dates[0]).days))

def series(anchors, noise=3.0, smooth=0.97, seed=None):
    """Anker-Interpolation + AR(1)-Rauschen, an Ankern exakt gepinnt."""
    r = np.random.default_rng(seed)
    ai = np.array([min(N-1,max(0,ix(*a[0]) if isinstance(a[0],tuple) else a[0])) for a in anchors])
    av = np.array([a[1] for a in anchors], float)
    o = np.argsort(ai); ai, av = ai[o], av[o]
    base = np.interp(np.arange(N), ai, av)
    e = r.normal(0,1,N); n = np.zeros(N)
    for i in range(1,N): n[i] = smooth*n[i-1] + e[i]
    n *= noise/ (n.std()+1e-9)
    n -= np.interp(np.arange(N), ai, n[ai])   # an Ankern exakt 0
    return base + n

D = lambda y,m,d=1: didx[dt.date(y,m,d)] if dt.date(y,m,d) in didx else ix(y,m,d)
I30, I7, I0 = N-31, N-8, N-1
I14, I182, I365 = N-15, N-183, N-366   # 30D / 7D / heute

# ---------------- Sub-Scores (0-100) ----------------
liquidity = series([(0,55),((2021,2),70),((2021,9),72),((2022,3),60),((2022,10),30),((2023,6),45),((2024,2),60),
    ((2024,10),50),((2025,5),30),((2025,11),55),((2026,3),68),(I30,73.7),(I14,50.48),(I7,53.5),(I0,42.0)], noise=2.5, seed=1)
growth = series([(0,48),((2021,3),62),((2022,1),58),((2022,9),40),((2023,5),48),((2024,3),60),((2025,2),55),
    ((2025,8),42),((2026,2),58),(I30,60.7),(I14,53.04),(I7,55.0),(I0,52.4)], noise=2.0, seed=2)
credit = series([(0,55),((2021,6),65),((2022,7),20),((2023,3),45),((2024,5),55),((2025,4),35),((2025,12),58),
    (I30,52.8),(I14,54.5),(I7,54.5),(I0,52.5)], noise=2.5, seed=3)
risk = series([(0,50),((2021,4),68),((2022,6),30),((2023,7),55),((2024,4),65),((2025,5),35),((2026,1),62),
    (I30,62.5),(I7,62.5),(I0,59.9)], noise=2.5, seed=4)
usd_stress = series([(0,72),((2020,9),80),((2021,3),93),((2021,7),70),((2021,10),80),((2022,2),60),((2022,5),30),
    ((2022,8),12),((2022,11),42),((2023,2),32),((2023,5),58),((2023,8),70),((2023,11),48),((2024,2),75),((2024,5),55),
    ((2024,8),65),((2024,11),32),((2025,1),14),((2025,4),38),((2025,8),48),((2025,11),68),((2026,1),42),((2026,3),72),
    ((2026,4,20),85),(I30,77.44),(I14,50.48*0+68.7+4.3),(I7,68.7),(I0,58.4)], noise=4.5, seed=5)
for s in (liquidity,growth,credit,risk,usd_stress): np.clip(s,0,100,out=s)

# MRI: eigene Anzeige-Serie (Chart 1) -- am aktuellen Rand exakt formelkonsistent
mri = series([(0,55),((2020,9),62),((2021,2),73),((2021,7),65),((2021,11),70),((2022,2),58),((2022,6),38),((2022,10),33),
    ((2023,2),60),((2023,6),50),((2023,11),46),((2024,2),73),((2024,7),53),((2024,11),60),((2025,2),63),((2025,6),27),
    ((2025,9),55),((2025,12),60),((2026,3),60),((2026,4,26),61),(I30,62.84),(I7,52.1),(I0,49.33)], noise=2.2, seed=6)
np.clip(mri,0,100,out=mri)

# Credit Conditions Timing (Chart 2): Latest 60.1 | 30D -0.5%
credit_timing = series([(0,60),((2021,3),78),((2021,9),55),((2022,4),25),((2022,8),10),((2023,1),40),((2023,7),55),
    ((2023,12),45),((2024,6),60),((2024,10),85),((2025,2),60),((2025,7),22),((2025,11),78),((2026,2),55),((2026,4,15),24),
    (I30,60.4),(I7,60.7),(I0,60.1)], noise=5.0, seed=7)
np.clip(credit_timing,0,100,out=credit_timing)

# ---------------- Zentralbank-Bilanzen (T USD) ----------------
fed = series([(0,7.05),((2021,1),7.4),((2021,7),8.1),((2022,1),8.8),((2022,5),8.97),((2023,1),8.5),((2023,4),8.75),
    ((2024,1),7.7),((2024,7),7.2),((2025,1),6.85),((2025,7),6.6),((2026,1),6.55),(I365,6.64),(I182,6.51),(I30,6.69),(I0,6.71)], noise=0.03, seed=8)
ecb = series([(0,6.35),((2020,12),7.9),((2021,7),8.9),((2021,12),9.65),((2022,3),9.75),((2022,9),9.0),((2023,3),8.5),
    ((2023,9),8.0),((2024,3),7.4),((2024,9),7.0),((2025,3),6.7),((2025,7),7.3),((2025,11),7.35),(I365,7.10),(I182,7.10),((2026,3),7.25),(I30,7.16),(I0,7.08)], noise=0.06, seed=9)
boj = series([(0,6.1),((2020,11),6.5),((2021,5),6.85),((2021,10),6.6),((2022,2),6.4),((2022,6),5.6),((2022,10),5.0),
    ((2023,2),5.65),((2023,7),5.3),((2024,1),5.35),((2024,7),4.9),((2025,1),5.1),(I365,4.95),(I182,4.55),((2026,1),4.45),(I30,4.36),(I0,4.28)], noise=0.07, seed=10)
pboc = series([(0,5.1),((2020,12),5.7),((2021,6),6.05),((2021,12),5.95),((2022,3),6.4),((2022,8),5.6),((2023,2),5.95),
    ((2023,8),6.1),((2024,2),6.5),((2024,8),6.1),((2025,2),6.4),(I365,6.43),(I182,6.69),((2026,1),7.2),(I30,7.09),(I0,7.03)], noise=0.07, seed=11)
glob = fed+ecb+boj+pboc   # 25.10 am 10.06 (per Konstruktion)

m2 = series([(0,18.2),((2021,6),20.4),((2022,4),21.7),((2023,4),20.7),((2024,6),21.0),((2025,1),21.6),(I365,22.04),(I182,22.48),(I0,22.7)], noise=0.04, seed=12)
tga_rrp = series([(0,1.6),((2021,12),2.3),((2023,6),2.6),((2024,6),1.4),((2025,6),1.0),(I0,0.87)], noise=0.04, seed=13)

vix = series([(0,28),((2020,11),38),((2021,6),17),((2022,3),33),((2022,10),32),((2023,6),14),((2024,8),28),((2025,4),35),
    ((2025,12),15),((2026,4,20),26),(I30,18.42),(I7,16.02),(I0,18.92)], noise=2.0, seed=14)
np.clip(vix,9,90,out=vix)
dxy = series([(0,112),((2021,6),105),((2022,10),124),((2023,7),113),((2024,10),116),((2025,4),122),((2025,12),115),
    (I30,118.07),(I0,120.08)], noise=0.8, seed=15)  # 30D +1.7%
hy = series([(0,5.8),((2021,7),3.1),((2022,7),5.9),((2023,11),3.9),((2024,11),2.8),((2025,5),4.4),((2026,1),2.9),(I0,2.75)], noise=0.12, seed=16)

# Cross Asset Regime (Chart 7) + Relative Leadership (Chart 8, +/-30 normiert)
cross = series([(0,45),((2021,3),65),((2022,6),25),((2023,6),50),((2024,3),68),((2025,5),28),((2026,1),58),(I0,52)], noise=4, seed=17)
np.clip(cross,0,100,out=cross)
eth_spx = series([(0,5),((2021,5),28),((2022,6),-25),((2023,6),-5),((2024,3),18),((2025,5),-22),((2026,2),-10),(I0,-28.9*0.9)], noise=4, seed=18)
btc_spx = series([(0,8),((2021,4),26),((2022,7),-27),((2023,7),10),((2024,3),24),((2025,5),-15),((2026,2),-5),(I0,-21.3*0.9)], noise=4, seed=19)
spx_oil = series([(0,-5),((2021,6),-15),((2022,6),-28),((2023,6),10),((2024,6),12),((2025,6),-5),(I0,10.3*0.9)], noise=4, seed=20)
eth_btc = series([(0,2),((2021,5),20),((2022,6),-10),((2023,6),-12),((2024,12),-20),((2025,8),5),(I0,-9.7*0.9)], noise=3, seed=21)
for s in (eth_spx,btc_spx,spx_oil,eth_btc): np.clip(s,-30,30,out=s)

np.save('/tmp/build/_series.npy', np.array([mri,liquidity,growth,credit,risk,usd_stress,credit_timing,fed,ecb,boj,pboc,glob,m2,tga_rrp,vix,dxy,hy,cross,eth_spx,btc_spx,spx_oil,eth_btc]))
json.dump([d.isoformat() for d in dates], open('/tmp/build/_dates.json','w'))
print('gen ok'); 
# Schnell-Checks
print('MRI heute (Serie/Formel):', round(mri[-1],2), round(compute_mri({'liquidity':liquidity[-1],'growth':growth[-1],'credit':credit[-1],'risk':risk[-1],'usd_stress':usd_stress[-1]}),2))
print('7D/30D MRI:', round(delta(list(mri),7),1), round(delta(list(mri),30),1), '| 30D%:', round(pct(list(mri),30),1))
print('USD 7D/30D:', round(delta(list(usd_stress),7),1), round(delta(list(usd_stress),30),1), '| 30D%:', round(pct(list(usd_stress),30),1))
print('Liq 30D:', round(delta(list(liquidity),30),1), 'Growth 30D:', round(delta(list(growth),30),1))
print('Credit 7D/30D:', round(delta(list(credit),7),1), round(delta(list(credit),30),1), 'Risk 7D:', round(delta(list(risk),7),1))
print('CB heute:', round(fed[-1],2), round(ecb[-1],2), round(boj[-1],2), round(pboc[-1],2), 'glob:', round(glob[-1],2), 'glob30D%:', round(pct(list(glob),30),2))
print('VIX:', round(vix[-1],2), round(delta(list(vix),7),1), round(delta(list(vix),30),1), 'DXY:', round(dxy[-1],2), round(pct(list(dxy),30),1))
print('Conviction heute:', conviction({'liquidity':42.0,'growth':52.4,'credit':52.5,'risk':59.9,'usd_stress':58.4}))
print('Conviction 07.06:', conviction({'liquidity':53.5,'growth':55.0,'credit':54.5,'risk':62.5,'usd_stress':68.7}))
print('Regime 10.06:', classify_regime(49.33, 58.4, -10.3), '| Regime 07.06:', classify_regime(52.1, 68.7, -2.3))
