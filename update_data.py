# -*- coding: utf-8 -*-
"""
update_data.py - Laedt Live-Daten (FRED, Yahoo, CoinGecko), berechnet Scores und schreibt data.js.
LOKAL ausfuehren (braucht Internet + api_keys.env im selben Ordner):
    pip install -r requirements.txt
    python update_data.py
api_keys.env:
    FRED_API_KEY=dein_key
"""
import os, sys, json, datetime as dt
import numpy as np, pandas as pd, requests
from macro_engine import *
from build_payload import build

HERE = os.path.dirname(os.path.abspath(__file__))
WINDOW = 2200

def load_keys():
    keys = {k: os.environ[k] for k in ('FRED_API_KEY','COINGECKO_API_KEY') if os.environ.get(k)}
    for fn in ('api_keys.env','.env','api_keys.txt'):
        p = os.path.join(HERE, fn)
        if os.path.exists(p):
            for line in open(p, encoding='utf-8'):
                if '=' in line and not line.strip().startswith('#'):
                    k,v = line.split('=',1); keys[k.strip()] = v.strip()
    return keys

def fred(series_id, key, start):
    r = requests.get('https://api.stlouisfed.org/fred/series/observations',
        params={'series_id':series_id,'api_key':key,'file_type':'json','observation_start':start}, timeout=30)
    r.raise_for_status()
    obs = r.json()['observations']
    s = pd.Series({o['date']: float(o['value']) for o in obs if o['value'] not in ('.','')})
    s.index = pd.to_datetime(s.index); return s.sort_index()

def yahoo(sym, start):
    import yfinance as yf
    df = yf.download(sym, start=start, progress=False, auto_adjust=True)
    return df['Close'][sym] if hasattr(df['Close'],'columns') else df['Close']

def pct_rank(s, window=WINDOW):
    """Rollierendes Perzentil 0-100 (Kalibrierungs-Kern aller Sub-Scores)."""
    return s.rolling(window, min_periods=200).apply(lambda w: 100.0*(w.rank(pct=True).iloc[-1]), raw=False)

def main():
    keys = load_keys()
    if 'FRED_API_KEY' not in keys:
        sys.exit('FEHLER: FRED_API_KEY fehlt in api_keys.env (kostenlos: https://fred.stlouisfed.org/docs/api/api_key.html)')
    K = keys['FRED_API_KEY']
    start = (dt.date.today() - dt.timedelta(days=WINDOW+900)).isoformat()  # Puffer fuer Rolling-Window
    print('Lade FRED...')
    F = {sid: fred(sid, K, start) for sid in
         ['WALCL','WTREGEN','RRPONTSYD','M2SL','BAMLH0A0HYM2','BAMLC0A0CM','ICSA','PAYEMS','UNRATE',
          'CPIAUCSL','CPILFESL','T10Y3M','DFII10','DTWEXBGS','VIXCLS','ECBASSETSW','JPNASSETS']}
    print('Lade Yahoo...')
    Y = {s: yahoo(s, start) for s in ['^GSPC','^IXIC','CL=F','BTC-USD','ETH-USD','EURUSD=X','JPY=X']}

    idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=WINDOW, freq='D')
    al = lambda s: s.reindex(s.index.union(idx)).ffill().reindex(idx)

    # Zentralbanken in T USD
    fed_t  = al(F['WALCL'])/1e6                       # Mio USD -> T
    ecb_t  = al(F['ECBASSETSW'])/1e6 * al(Y['EURUSD=X'])
    boj_t  = al(F['JPNASSETS'])/1e5 / al(Y['JPY=X'])  # 100-Mio-JPY-Einheiten -> T USD
    pboc_p = os.path.join(HERE,'pboc_assets.csv')     # optional: Datum,Wert(T USD)
    if os.path.exists(pboc_p):
        pb = pd.read_csv(pboc_p, index_col=0, parse_dates=True).iloc[:,0]; pboc_t = al(pb); dq_pboc = True
    else:
        pboc_t = pd.Series(7.03, index=idx); dq_pboc = False  # Fallback: letzter bekannter Wert
    glob = fed_t+ecb_t+boj_t+pboc_t
    tga_rrp = (al(F['WTREGEN'])+al(F['RRPONTSYD']))/1e3  # Mrd -> T
    m2 = al(F['M2SL'])/1e3
    vix, dxy, hy = al(F['VIXCLS']), al(F['DTWEXBGS']), al(F['BAMLH0A0HYM2'])

    # ---- Sub-Scores (rollierende Perzentil-Normalisierung; Gewichte = Kalibrierungs-Konstanten) ----
    # Gewichte kalibriert am 10.06.2026 gegen die Original-Sub-Scores (42.0/52.4/52.5/59.9/58.4)
    liq = 0.484*pct_rank(glob.diff(90)) + 0.30*pct_rank(m2.diff(90)) + 0.216*pct_rank(glob)
    growth = (0.15*pct_rank(al(F['PAYEMS']).pct_change(365)) + 0.30*(100-pct_rank(al(F['ICSA']))) +
              0.30*(100-pct_rank(al(F['UNRATE']).diff(180))) + 0.25*pct_rank(al(F['T10Y3M'])))
    credit = (100-pct_rank(hy))*0.15 + (100-pct_rank(al(F['BAMLC0A0CM'])))*0.09 + (100-pct_rank(hy.diff(30)))*0.76
    ndx_spx = al(Y['^IXIC'])/al(Y['^GSPC']); spx_oil = al(Y['^GSPC'])/al(Y['CL=F'])
    risk = 0.225*pct_rank(ndx_spx.pct_change(90)) + 0.225*pct_rank(spx_oil.pct_change(90)) + 0.55*(100-pct_rank(vix))
    usd_stress = 0.455*pct_rank(dxy) + 0.145*pct_rank(dxy.pct_change(30)) + 0.40*pct_rank(vix)
    credit_timing = (100-pct_rank(hy.diff(60)))*0.6 + (100-pct_rank(hy))*0.4
    cross = (risk + credit)/2
    lead = lambda a,b: (a/b).pct_change(90).mul(100).clip(-30,30)
    eth_spx = lead(al(Y['ETH-USD']), al(Y['^GSPC'])); btc_spx = lead(al(Y['BTC-USD']), al(Y['^GSPC']))
    spxoil_l = lead(al(Y['^GSPC']), al(Y['CL=F'])); eth_btc = lead(al(Y['ETH-USD']), al(Y['BTC-USD']))

    subs_last = {'liquidity':liq.iloc[-1],'growth':growth.iloc[-1],'credit':credit.iloc[-1],'risk':risk.iloc[-1],'usd_stress':usd_stress.iloc[-1]}
    mri = (50 + (liq-50)*0.25 + (growth-50)*0.25 + (credit-50)*0.20 + (risk-50)*0.15 - (usd_stress-50)*0.15).clip(0,100)

    series = {k: v.ffill().bfill().values for k,v in {
        'mri':mri,'liquidity':liq,'growth':growth,'credit':credit,'risk':risk,'usd_stress':usd_stress,
        'credit_timing':credit_timing,'fed':fed_t,'ecb':ecb_t,'boj':boj_t,'pboc':pboc_t,'glob':glob,
        'm2':m2,'tga_rrp':tga_rrp,'vix':vix,'dxy':dxy,'hy':hy,'cross':cross,
        'eth_spx':eth_spx,'btc_spx':btc_spx,'spx_oil':spxoil_l,'eth_btc':eth_btc}.items()}
    dates = [d.date().isoformat() for d in idx]

    # Macro Releases aus FRED
    def yoy(s, fmtmonth=True):
        s2 = s.dropna(); cur = s2.iloc[-1]; prev = s2[s2.index <= s2.index[-1]-pd.Timedelta(days=360)].iloc[-1]
        return (cur/prev-1)*100, s2.index[-1].date().isoformat()
    rel = []
    for name, sid, hot_when_pos in [('Initial Claims','ICSA',False),('Nonfarm Payrolls','PAYEMS',True),
                                    ('Unemployment','UNRATE',None),('Headline CPI','CPIAUCSL',True),('Core CPI','CPILFESL',True)]:
        v, dte = yoy(F[sid])
        lab = 'supportive' if hot_when_pos is None else (('hot' if v>0.2 else 'supportive') if hot_when_pos else ('weak' if v<0 else 'supportive'))
        rel.append((name, '{:+.1f}% YoY'.format(v), lab, dte))

    dq = 100 if dq_pboc else 95
    payload = build(series, dates, releases=rel, data_quality=dq)
    out = os.path.join(HERE,'data.js')
    open(out,'w',encoding='utf-8').write('window.MACRO_DATA = ' + json.dumps(payload, ensure_ascii=False) + ';')
    h = payload['headline']
    print('OK ->', out)
    print('Regime:', h['regime'], '| MRI:', h['mri'], '| Sub-Scores:', {k:round(v,1) for k,v in subs_last.items()})
    if not dq_pboc: print('Hinweis: PBoC ohne Live-Quelle (pboc_assets.csv anlegen fuer 100/100 Data Quality).')

if __name__ == '__main__':
    main()
