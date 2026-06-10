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
    keys = {k: os.environ[k] for k in ('FRED_API_KEY','COINGECKO_API_KEY','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID','TWELVEDATA_API_KEY') if os.environ.get(k)}
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

KEYS = {}

def _stooq(sym):
    m = {'^GSPC':'^spx','^IXIC':'^ndq','CL=F':'cl.f'}
    if sym not in m: return None
    r = requests.get('https://stooq.com/q/d/l/?s={}&i=d'.format(m[sym]), timeout=30)
    import io
    df = pd.read_csv(io.StringIO(r.text), index_col=0, parse_dates=True)
    return df['Close'] if 'Close' in df else None

def _coingecko(sym):
    m = {'BTC-USD':'bitcoin','ETH-USD':'ethereum'}
    if sym not in m: return None
    hdr = {'x-cg-demo-api-key': KEYS['COINGECKO_API_KEY']} if KEYS.get('COINGECKO_API_KEY') else {}
    r = requests.get('https://api.coingecko.com/api/v3/coins/{}/market_chart'.format(m[sym]),
                     params={'vs_currency':'usd','days':'max','interval':'daily'}, headers=hdr, timeout=30)
    px = r.json().get('prices', [])
    if not px: return None
    s = pd.Series({pd.Timestamp(p[0], unit='ms').normalize(): p[1] for p in px})
    return s.sort_index()

def yahoo(sym, start):
    """Yahoo mit Fallbacks: Stooq (Aktien/Oel), CoinGecko (Krypto)."""
    try:
        import yfinance as yf
        df = yf.download(sym, start=start, progress=False, auto_adjust=True)
        s = df['Close'][sym] if hasattr(df['Close'],'columns') else df['Close']
        if s is not None and len(s) > 100: return s
    except Exception as e:
        print('  Yahoo-Fehler', sym, str(e)[:60])
    for fb in (_stooq, _coingecko):
        try:
            s = fb(sym)
            if s is not None and len(s) > 100:
                print('  Fallback aktiv fuer', sym, '({})'.format(fb.__name__)); return s
        except Exception: pass
    raise RuntimeError('Keine Quelle fuer ' + sym)

def telegram(msg):
    tok, chat = KEYS.get('TELEGRAM_BOT_TOKEN'), KEYS.get('TELEGRAM_CHAT_ID')
    if not tok or not chat: return False
    try:
        r = requests.post('https://api.telegram.org/bot{}/sendMessage'.format(tok),
            json={'chat_id': chat, 'text': msg, 'parse_mode': 'HTML', 'disable_web_page_preview': True}, timeout=15)
        return r.ok
    except Exception as e:
        print('Telegram-Fehler:', str(e)[:80]); return False

def pct_rank(s, window=WINDOW):
    """Rollierendes Perzentil 0-100 (Kalibrierungs-Kern aller Sub-Scores)."""
    return s.rolling(window, min_periods=200).rank(pct=True)*100

def compute_crypto(btc, eth, mri, liq, usd, risk, idx):
    """Krypto-Zyklus-Analyse: BTC/ETH-Verhalten relativ zum Makro-Regime.
    Boden-/Top-Scores (0-100) aus Makro-Konstellation + BTC-Bewertung; bei jedem Update live neu berechnet.
    KEINE Anlageberatung - statistische Auswertung der eigenen Historie."""
    clip = lambda s: s.clip(0, 100)
    ma200 = btc.rolling(200, min_periods=150).mean(); mayer = btc/ma200
    dd = btc/btc.cummax() - 1                 # Drawdown vom Allzeithoch
    liq_mom = liq.diff(90)
    # Boden = sqrt(Preis-Schmerz x Makro-Kapitulation). Backtest-Treffer: Jun+Dez 2018, Maer 2020, Mai+Nov 2022.
    pain = clip(pd.concat([(-dd-0.45)*250, (0.85-mayer)*200], axis=1).max(axis=1))
    cap  = clip(pd.concat([(40-mri)*5, (usd-60)*4], axis=1).max(axis=1))
    bottom = np.sqrt(pain.clip(lower=0) * cap.clip(lower=0))
    # Top = sqrt(Preis-Hitze x Makro-Hitze), 14T-geglaettet + Preis-Hitze-Gate.
    # Backtest-Treffer: Jun 2017 (frueh), Jan 2018, Apr 2021, Okt 2021. Markiert ZONEN, keine Exakt-Tops.
    ret365 = btc.pct_change(365)*100
    price_heat = clip(pd.concat([(mayer-1.3)*90, ret365*0.25], axis=1).max(axis=1))
    gate = pd.Series(np.where(liq_mom < 5, 1.0, 0.3), index=mri.index)
    macro_heat = clip((mri-45)*4) * gate
    top_raw = np.sqrt(price_heat.clip(lower=0) * macro_heat.clip(lower=0))
    top = top_raw.rolling(14).mean()

    def sig_dates(score, thr, gap=180, extra=None, extra_thr=80):
        dates = []; last = -10**9; v = score.values
        for i in range(len(v)):
            ok_extra = extra is None or (extra.values[i] == extra.values[i] and extra.values[i] >= extra_thr)
            if v[i] == v[i] and v[i] >= thr and ok_extra and i-last >= gap:
                dates.append(idx[i].date().isoformat()); last = i
        return dates

    # Forward-Return-Statistik (90 Tage), getrennt nach Makro-Band - das ist die "Recherche", live aus den Daten
    stats = []
    for asset, px in (('BTC', btc), ('ETH', eth)):
        fwd = px.shift(-90)/px - 1
        for name, mask in (('MRI<40', mri<40), ('MRI 40-55', (mri>=40)&(mri<55)), ('MRI>55', mri>=55),
                           ('Boden-Signal', bottom>=65), ('Top-Signal', (top>=75)&(price_heat>=80))):
            m = fwd[mask & fwd.notna() & px.notna()]
            if len(m) > 20:
                stats.append({'asset': asset, 'band': name, 'avg_90d': round(float(m.mean()*100),1),
                              'hit': int(round(float((m>0).mean()*100))), 'n': int(len(m))})

    b_now, t_now = float(bottom.iloc[-1]), float(top.iloc[-1])
    mayer_now = float(mayer.iloc[-1]) if mayer.iloc[-1]==mayer.iloc[-1] else None
    dd_now = float(dd.iloc[-1])
    if b_now >= 65: phase, pcol = 'BODENZONE - historisch attraktive Kaufregion', '#43b581'
    elif t_now >= 75: phase, pcol = 'TOP-RISIKO - historisch Verkaufs-/Absicherungszone', '#f04747'
    elif t_now > b_now: phase, pcol = 'SPAETZYKLUS - neutral bis vorsichtig', '#faa61a'
    else: phase, pcol = 'FRUEHZYKLUS/NEUTRAL - abwarten, Bestaetigung suchen', '#949ba4'

    liq_dir = 'steigend' if float(liq_mom.iloc[-1] or 0) > 0 else 'fallend'
    usd_dir = 'fallend (entlastend)' if float(usd.diff(30).iloc[-1] or 0) < 0 else 'steigend (belastend)'
    erwartung = (
        'Boden-Score {:.0f}/100, Top-Score {:.0f}/100. '.format(b_now, t_now) +
        'BTC notiert {:.0f}% unter ATH, Mayer-Multiple {} (BTC/200d-MA). '.format(-dd_now*100, '{:.2f}'.format(mayer_now) if mayer_now else 'n/a') +
        'Liquiditaets-Momentum (90T) ist {}, USD-Stress (30T) {}. '.format(liq_dir, usd_dir) +
        ('Historisch folgten auf diese Konstellation eher schwache bis seitwaertige 90-Tage-Renditen; aggressives Kaufen lohnte selten vor einem Liquiditaets-Turnaround. ' if t_now>b_now and b_now<65 else '') +
        ('Historisch war diese Konstellation eine der besten Kaufzonen (Kapitulation: tiefer MRI/USD-Stress-Spitze + BTC tief unter ATH/200d-MA). ' if b_now>=65 else '') +
        ('Historisch markierte diese Konstellation Top-Naehe: ueberhitzter Preis bei heissem Makro - gestaffeltes De-Risking war profitabel. ' if t_now>=75 else '') +
        ('Aktuell fehlt fuer eine Kaufzone die Makro-Kapitulation (MRI muesste <40 oder USD-Stress >60 mit Spitze sein). ' if b_now<65 and dd_now<-0.40 else '') +
        'Kaufzonen-Trigger: BTC >45% unter ATH oder Mayer <0.85, PLUS MRI <40 oder USD-Stress-Spitze >60. '
        'Top-Risiko-Trigger: Mayer >1.4 oder extreme 1J-Rendite, PLUS MRI-Region >65 bei nicht mehr steigender Liquiditaet. '
        'Signale markieren ZONEN (gestaffelt agieren/DCA), keine Exakt-Zeitpunkte.'
    )
    # Strategie-Backtest (in-sample!): 100% BTC ab Start; Top-Signal -> Cash; Boden-Signal -> wieder 100%
    bset, tset = set(sig_dates(bottom, 65)), set(sig_dates(top, 75, extra=price_heat))
    diso = [d.date().isoformat() for d in idx]
    rets = btc.pct_change().fillna(0).values
    fv = btc.first_valid_index(); fi = idx.get_loc(fv) if fv is not None else 0
    state_pos, eq = 1.0, 100.0
    eq_strat, eq_hold = [], []
    for i in range(len(idx)):
        if i <= fi: eq_strat.append(100.0); eq_hold.append(100.0); continue
        if diso[i] in tset: state_pos = 0.0
        if diso[i] in bset: state_pos = 1.0
        eq = eq * (1 + rets[i]*state_pos)
        eq_strat.append(eq)
        eq_hold.append(100.0 * float(btc.iloc[i]/btc.iloc[fi]))
    def maxdd(a):
        peak, mdd = -1e9, 0.0
        for v in a:
            peak = max(peak, v); mdd = min(mdd, v/peak - 1)
        return round(mdd*100, 1)
    wk = list(range(fi, len(idx), 7)) + [len(idx)-1]
    equity = {'dates': [diso[i] for i in wk], 'strat': [round(eq_strat[i],1) for i in wk], 'hold': [round(eq_hold[i],1) for i in wk],
              'strat_x': round(eq_strat[-1]/100, 1), 'hold_x': round(eq_hold[-1]/100, 1),
              'strat_dd': maxdd(eq_strat[fi:]), 'hold_dd': maxdd(eq_hold[fi:])}

    r0 = lambda s: [None if x!=x else int(round(float(x))) for x in s.values]
    return {
        'equity': equity,
        'btc': r0(btc), 'eth': [None if x!=x else round(float(x),2) for x in eth.values],
        'bottom_signals': sig_dates(bottom, 65), 'top_signals': sig_dates(top, 75, extra=price_heat),
        'bottom_now': round(b_now,1), 'top_now': round(t_now,1),
        'phase': phase, 'phase_color': pcol, 'erwartung': erwartung, 'stats': stats,
        'mayer': round(mayer_now,2) if mayer_now else None, 'drawdown_pct': round(dd_now*100,1),
        'disclaimer': 'Statistische Auswertung der eigenen Datenhistorie - keine Anlageberatung.',
    }

def main():
    keys = load_keys(); KEYS.update(keys)
    if 'FRED_API_KEY' not in keys:
        sys.exit('FEHLER: FRED_API_KEY fehlt in api_keys.env (kostenlos: https://fred.stlouisfed.org/docs/api/api_key.html)')
    K = keys['FRED_API_KEY']
    start = '1985-01-01'  # volle Historie; Charts beginnen wo die jeweilige Serie beginnt
    print('Lade FRED...')
    F = {sid: fred(sid, K, start) for sid in
         ['WALCL','WTREGEN','RRPONTSYD','M2SL','BAMLH0A0HYM2','BAMLC0A0CM','BAA10Y','AAA10Y','ICSA','PAYEMS','UNRATE',
          'CPIAUCSL','CPILFESL','T10Y3M','DFII10','DTWEXBGS','VIXCLS','ECBASSETSW','JPNASSETS','DEXUSEU','DEXJPUS']}
    print('Lade Yahoo...')
    Y = {s: yahoo(s, start) for s in ['^GSPC','^IXIC','CL=F','BTC-USD','ETH-USD']}

    # Tagesschluss-Fix: nur bis GESTERN rechnen, damit Deltas nicht intraday springen
    idx = pd.date_range(start='1990-01-01', end=pd.Timestamp.today().normalize() - pd.Timedelta(days=1), freq='D')
    al = lambda s: s.reindex(s.index.union(idx)).ffill().reindex(idx)

    # Zentralbanken in T USD
    fed_t  = al(F['WALCL'])/1e6                       # Mio USD -> T
    ecb_t  = al(F['ECBASSETSW'])/1e6 * al(F['DEXUSEU'])
    boj_t  = al(F['JPNASSETS'])/1e5 / al(F['DEXJPUS'])  # 100-Mio-JPY-Einheiten -> T USD
    pboc_p = os.path.join(HERE,'pboc_assets.csv')     # optional: Datum,Wert(T USD)
    if os.path.exists(pboc_p):
        pb = pd.read_csv(pboc_p, index_col=0, parse_dates=True).iloc[:,0]; pboc_t = al(pb); dq_pboc = True
    else:
        pboc_t = pd.Series(7.03, index=idx); dq_pboc = False  # Fallback: letzter bekannter Wert
        pboc_t[idx < pd.Timestamp('2008-01-01')] = np.nan     # keine Fake-Historie vor ECB-Datenbeginn
    glob = fed_t+ecb_t+boj_t+pboc_t
    tga_rrp = (al(F['WTREGEN'])+al(F['RRPONTSYD']))/1e3  # Mrd -> T
    m2 = al(F['M2SL'])/1e3
    vix, dxy = al(F['VIXCLS']), al(F['DTWEXBGS'])
    # ICE-BofA-Spreads liefert FRED nur ~3J zurueck -> Splice mit Moody's-Spreads (volle Historie ab 1985)
    def splice(short, proxy):
        s, p = al(short), al(proxy)
        both = s.notna() & p.notna()
        k = float((s[both]/p[both]).mean()) if both.any() else 1.0
        return s.combine_first(p*k)
    hy = splice(F['BAMLH0A0HYM2'], F['BAA10Y'])
    ig = splice(F['BAMLC0A0CM'], F['AAA10Y'])

    # ---- Sub-Scores (rollierende Perzentil-Normalisierung; Gewichte = Kalibrierungs-Konstanten) ----
    # Gewichte kalibriert am 10.06.2026 (volle Historie + Splice) gegen die Original-Sub-Scores (42.0/52.4/52.5/59.9/58.4)
    liq = 0.507*pct_rank(glob.diff(90)) + 0.330*pct_rank(m2.diff(90)) + 0.162*pct_rank(glob)
    growth = (0.225*pct_rank(al(F['PAYEMS']).pct_change(365)) + 0.247*(100-pct_rank(al(F['ICSA']))) +
              0.259*(100-pct_rank(al(F['UNRATE']).diff(180))) + 0.269*pct_rank(al(F['T10Y3M'])))
    credit = (100-pct_rank(hy))*0.135 + (100-pct_rank(ig))*0.085 + (100-pct_rank(hy.diff(30)))*0.78
    ndx_spx = al(Y['^IXIC'])/al(Y['^GSPC']); spx_oil = al(Y['^GSPC'])/al(Y['CL=F'])
    risk = 0.265*pct_rank(ndx_spx.pct_change(90)) + 0.208*pct_rank(spx_oil.pct_change(90)) + 0.527*(100-pct_rank(vix))
    usd_stress = 0.458*pct_rank(dxy) + 0.146*pct_rank(dxy.pct_change(30)) + 0.396*pct_rank(vix)
    credit_timing = (100-pct_rank(hy.diff(60)))*0.6 + (100-pct_rank(hy))*0.4
    cross = (risk + credit)/2
    # Leadership: tanh-Skalierung auf +/-30 (saettigt weich statt am Limit zu kleben), 5T-geglaettet
    lead = lambda a,b: (np.tanh((a/b).pct_change(90).rolling(5).mean()*100/40)*30)
    eth_spx = lead(al(Y['ETH-USD']), al(Y['^GSPC'])); btc_spx = lead(al(Y['BTC-USD']), al(Y['^GSPC']))
    spxoil_l = lead(al(Y['^GSPC']), al(Y['CL=F'])); eth_btc = lead(al(Y['ETH-USD']), al(Y['BTC-USD']))

    subs_last = {'liquidity':liq.iloc[-1],'growth':growth.iloc[-1],'credit':credit.iloc[-1],'risk':risk.iloc[-1],'usd_stress':usd_stress.iloc[-1]}
    mri = (50 + (liq-50)*0.25 + (growth-50)*0.25 + (credit-50)*0.20 + (risk-50)*0.15 - (usd_stress-50)*0.15).clip(0,100)

    series = {k: v.ffill().values for k,v in {
        'mri':mri,'liquidity':liq,'growth':growth,'credit':credit,'risk':risk,'usd_stress':usd_stress,
        'credit_timing':credit_timing,'fed':fed_t,'ecb':ecb_t,'boj':boj_t,'pboc':pboc_t,'glob':glob,
        'm2':m2,'tga_rrp':tga_rrp,'vix':vix,'dxy':dxy,'hy':hy,'cross':cross,
        'eth_spx':eth_spx,'btc_spx':btc_spx,'spx_oil':spxoil_l,'eth_btc':eth_btc}.items()}
    dates = [d.date().isoformat() for d in idx]
    # Fuehrende Leerzeit abschneiden: Charts beginnen, wo die frueheste geplottete Serie beginnt
    plot_keys = ['mri','credit_timing','usd_stress','fed','ecb','boj','glob','cross','eth_spx','btc_spx','spx_oil','eth_btc']
    firsts = [np.where(~np.isnan(series[k]))[0] for k in plot_keys]
    cut = int(min(f[0] for f in firsts if len(f)))
    series = {k: v[cut:] for k,v in series.items()}; dates = dates[cut:]

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
    # Krypto-Zyklus-Analyse (auf den getrimmten Zeitraum ausgerichtet)
    cut_idx = idx[-len(dates):]
    aligned = lambda s: pd.Series(s, index=idx).reindex(cut_idx)
    payload['crypto'] = compute_crypto(
        al(Y['BTC-USD']).reindex(cut_idx), al(Y['ETH-USD']).reindex(cut_idx),
        pd.Series(series['mri'], index=cut_idx), pd.Series(series['liquidity'], index=cut_idx),
        pd.Series(series['usd_stress'], index=cut_idx), pd.Series(series['risk'], index=cut_idx), cut_idx)
    payload['updated'] = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    out = os.path.join(HERE,'data.js')
    open(out,'w',encoding='utf-8').write('window.MACRO_DATA = ' + json.dumps(payload, ensure_ascii=False) + ';')
    h = payload['headline']; c = payload['crypto']

    # ---- Track-Record: history.csv (1 Zeile pro Handelstag, dedupliziert) ----
    hist_p = os.path.join(HERE,'history.csv')
    header = 'date,mri,liquidity,growth,credit,risk,usd_stress,regime,conviction,bottom_score,top_score,btc,eth'
    pulse_vals = [p['value'] for p in payload['pulse']]
    row = ','.join(str(x) for x in [dates[-1], h['mri'], *pulse_vals, h['regime'], h['conviction'],
                                    c['bottom_now'], c['top_now'], c['btc'][-1], c['eth'][-1]])
    lines = [l for l in open(hist_p, encoding='utf-8').read().splitlines() if l.strip()] if os.path.exists(hist_p) else [header]
    lines = [l for l in lines if not l.startswith(dates[-1] + ',')]
    lines.append(row)
    open(hist_p, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')

    # ---- Alerts: Regime-Wechsel + Signal-Zonen (Telegram, falls Token vorhanden) ----
    state_p = os.path.join(HERE,'state.json')
    prev = json.load(open(state_p, encoding='utf-8')) if os.path.exists(state_p) else {}
    cur = {'regime': h['regime'], 'bottom_zone': c['bottom_now'] >= 65, 'top_zone': c['top_now'] >= 75, 'mri': h['mri']}
    msgs = []
    if prev:
        if prev.get('regime') != cur['regime']:
            msgs.append('Regime-Wechsel: {} → <b>{}</b> (MRI {})'.format(prev.get('regime'), cur['regime'], h['mri']))
        if not prev.get('bottom_zone') and cur['bottom_zone']:
            msgs.append('🟢 <b>KAUFZONE aktiv</b> — Boden-Score {}/100. {}'.format(c['bottom_now'], c['phase']))
        if prev.get('bottom_zone') and not cur['bottom_zone']:
            msgs.append('Kaufzone beendet (Boden-Score {}/100).'.format(c['bottom_now']))
        if not prev.get('top_zone') and cur['top_zone']:
            msgs.append('🔴 <b>TOP-RISIKO aktiv</b> — Top-Score {}/100. Gestaffeltes De-Risking pruefen.'.format(c['top_now']))
        if prev.get('top_zone') and not cur['top_zone']:
            msgs.append('Top-Risiko-Zone beendet (Top-Score {}/100).'.format(c['top_now']))
    if msgs:
        sent = telegram('<b>AlphaCycle Alert</b> ({})\n'.format(dates[-1]) + '\n'.join(msgs) +
                 '\n\nMRI {} • Boden {} • Top {}\nhttps://noahdeitmerg-svg.github.io/makro-dashboard/'.format(h['mri'], c['bottom_now'], c['top_now']))
        print('Alerts:', len(msgs), '| Telegram gesendet:', sent)
    json.dump(cur, open(state_p, 'w', encoding='utf-8'))
    print('OK ->', out)
    print('Regime:', h['regime'], '| MRI:', h['mri'], '| Sub-Scores:', {k:round(v,1) for k,v in subs_last.items()})
    if not dq_pboc: print('Hinweis: PBoC ohne Live-Quelle (pboc_assets.csv anlegen fuer 100/100 Data Quality).')

if __name__ == '__main__':
    main()
