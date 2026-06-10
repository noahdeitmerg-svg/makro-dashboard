# -*- coding: utf-8 -*-
# Gibt die aktuellen Perzentile aller Score-Komponenten aus (fuer Kalibrierung)
import update_data as U, pandas as pd, datetime as dt
keys = U.load_keys(); K = keys['FRED_API_KEY']
start = (dt.date.today() - dt.timedelta(days=U.WINDOW+900)).isoformat()
F = {s: U.fred(s, K, start) for s in ['WALCL','WTREGEN','RRPONTSYD','M2SL','BAMLH0A0HYM2','BAMLC0A0CM','ICSA','PAYEMS','UNRATE','T10Y3M','DTWEXBGS','VIXCLS','ECBASSETSW','JPNASSETS']}
Y = {s: U.yahoo(s, start) for s in ['^GSPC','^IXIC','CL=F','EURUSD=X','JPY=X']}
idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=U.WINDOW, freq='D')
al = lambda s: s.reindex(s.index.union(idx)).ffill().reindex(idx)
fed=al(F['WALCL'])/1e6; ecb=al(F['ECBASSETSW'])/1e6*al(Y['EURUSD=X']); boj=al(F['JPNASSETS'])/1e5/al(Y['JPY=X'])
glob=fed+ecb+boj+pd.Series(7.03,index=idx); m2=al(F['M2SL'])/1e3
hy=al(F['BAMLH0A0HYM2']); ig=al(F['BAMLC0A0CM']); vix=al(F['VIXCLS']); dxy=al(F['DTWEXBGS'])
p=U.pct_rank; L=lambda s: round(float(s.iloc[-1]),1)
print('LIQ: d90glob',L(p(glob.diff(90))),'d90m2',L(p(m2.diff(90))),'level',L(p(glob)))
print('GROWTH: payrolls',L(p(al(F['PAYEMS']).pct_change(365))),'claims_inv',L(100-p(al(F['ICSA']))),'unemp_inv',L(100-p(al(F['UNRATE']).diff(180))),'curve',L(p(al(F['T10Y3M']))))
print('CREDIT: hy_inv',L(100-p(hy)),'ig_inv',L(100-p(ig)),'d30hy_inv',L(100-p(hy.diff(30))),'d90hy_inv',L(100-p(hy.diff(90))))
ndx=al(Y['^IXIC'])/al(Y['^GSPC']); so=al(Y['^GSPC'])/al(Y['CL=F'])
print('RISK: ndxspx',L(p(ndx.pct_change(90))),'spxoil',L(p(so.pct_change(90))),'vix_inv',L(100-p(vix)))
print('USD: dxy_lvl',L(p(dxy)),'dxy_d30',L(p(dxy.pct_change(30))),'vix_lvl',L(p(vix)))