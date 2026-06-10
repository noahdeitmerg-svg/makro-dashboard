# -*- coding: utf-8 -*-
# Loest die Sub-Score-Gewichte gegen die Zielwerte (Original 10.06.2026)
import pandas as pd, numpy as np
import update_data as U
K = U.load_keys()['FRED_API_KEY']; start='1985-01-01'
F = {s: U.fred(s,K,start) for s in ['WALCL','M2SL','BAMLH0A0HYM2','BAMLC0A0CM','BAA10Y','AAA10Y','ICSA','PAYEMS','UNRATE','T10Y3M','DTWEXBGS','VIXCLS','ECBASSETSW','JPNASSETS','DEXUSEU','DEXJPUS']}
Y = {s: U.yahoo(s,start) for s in ['^GSPC','^IXIC','CL=F']}
idx = pd.date_range(start='1990-01-01', end=pd.Timestamp.today().normalize(), freq='D')
al = lambda s: s.reindex(s.index.union(idx)).ffill().reindex(idx)
def splice(short, proxy):
    s,p = al(short),al(proxy); both = s.notna()&p.notna()
    k = float((s[both]/p[both]).mean()) if both.any() else 1.0
    return s.combine_first(p*k)
fed=al(F['WALCL'])/1e6; ecb=al(F['ECBASSETSW'])/1e6*al(F['DEXUSEU']); boj=al(F['JPNASSETS'])/1e5/al(F['DEXJPUS'])
pboc=pd.Series(7.03,index=idx); pboc[idx<pd.Timestamp('2008-01-01')]=np.nan
glob=fed+ecb+boj+pboc; m2=al(F['M2SL'])/1e3
hy=splice(F['BAMLH0A0HYM2'],F['BAA10Y']); ig=splice(F['BAMLC0A0CM'],F['AAA10Y'])
vix=al(F['VIXCLS']); dxy=al(F['DTWEXBGS'])
p=U.pct_rank; L=lambda s: float(s.iloc[-1])
comps = {
 'liq': [L(p(glob.diff(90))), L(p(m2.diff(90))), L(p(glob))],
 'growth': [L(p(al(F['PAYEMS']).pct_change(365))), L(100-p(al(F['ICSA']))), L(100-p(al(F['UNRATE']).diff(180))), L(p(al(F['T10Y3M'])))],
 'credit': [L(100-p(hy)), L(100-p(ig)), L(100-p(hy.diff(30)))],
 'risk': [L(p((al(Y['^IXIC'])/al(Y['^GSPC'])).pct_change(90))), L(p((al(Y['^GSPC'])/al(Y['CL=F'])).pct_change(90))), L(100-p(vix))],
 'usd': [L(p(dxy)), L(p(dxy.pct_change(30))), L(p(vix))],
}
targets = {'liq':42.0,'growth':52.4,'credit':52.5,'risk':59.9,'usd':58.4}
for k,c in comps.items():
    c = np.array(c); n=len(c)
    w = np.full(n, 1.0/n)
    # projizierter Gradientenschritt: konvexe Gewichte, Summe 1, die Ziel exakt treffen
    for _ in range(20000):
        err = w@c - targets[k]
        w -= 0.00002*err*c
        w = np.clip(w, 0.05, 0.85); w /= w.sum()
    print(k, 'comps', np.round(c,1), '-> w', np.round(w,3), '= score', round(float(w@c),2), '(Ziel', targets[k], ')')