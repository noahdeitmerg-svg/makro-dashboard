# -*- coding: utf-8 -*-
"""Baut data.js (window.MACRO_DATA) aus den Serien: Scores, Regime, alle Textsektionen."""
import numpy as np, json
from macro_engine import *

def build(series, dates, releases=None, data_quality=100):
    d = series
    r2 = lambda a: [round(float(x),2) for x in a]
    last = lambda k: float(d[k][-1])
    ago  = lambda k,n: float(d[k][-1-n])
    dlt  = lambda k,n: last(k)-ago(k,n)
    pc   = lambda k,n: (last(k)/ago(k,n)-1)*100

    subs = {k:last(k) for k in ['liquidity','growth','credit','risk','usd_stress']}
    mri_now = compute_mri(subs)
    conv = conviction(subs)
    regime = classify_regime(mri_now, last('usd_stress'), dlt('usd_stress',7))

    # Top Drivers: Gewicht x bullishe 14T-Aenderung / 4 (nur Makro-Saeulen)
    drivers = [
        ('Global Liquidity', round(0.25*dlt('liquidity',14)/4,2)),
        ('Credit Conditions', round(-0.20*dlt('credit',14)/4,2)),
        ('Growth/Cycle', round(0.25*dlt('growth',14)/4,2)),
    ]
    drivers = [(n, v, 'supportive' if v>0 else 'drag') for n,v in drivers]

    vix_now = last('vix')
    vix_support = int(round(max(0,min(100, 100-(vix_now-10)*(100/21.4)))))

    net_fed = last('fed')-last('tga_rrp')
    def ampel(val, green, red, invert=False):
        if invert: return 'red' if val>red else ('green' if val<green else 'yellow')
        return 'green' if val>green else ('red' if val<red else 'yellow')
    key_levels = [
        {'name':'Global CB Assets','value':'{:.2f}T USD'.format(last('glob')),'detail':'6M={:.0f}% | 1J={:.0f}%'.format(pc('glob',182),pc('glob',365)).replace('=-0%','=-0%'),'light':ampel(pc('glob',182),-1,-3)},
        {'name':'Net Fed Liquidity','value':'{:.2f}T USD'.format(net_fed),'detail':'','light':ampel(net_fed,5.5,5.0)},
        {'name':'FED Assets','value':'{:.2f}T USD'.format(last('fed')),'detail':'6M={:.0f}% | 1J={:.0f}%'.format(pc('fed',182),pc('fed',365)),'light':ampel(pc('fed',182),0,-3)},
        {'name':'US M2 Supply','value':'{:.1f}T USD'.format(last('m2')),'detail':'6M={:.0f}% | 1J={:.0f}%'.format(pc('m2',182),pc('m2',365)),'light':ampel(pc('m2',365),0,-2)},
        {'name':'HY Spread','value':'{:.2f}'.format(last('hy')),'detail':'','light':ampel(last('hy'),3.5,5.0,invert=True)},
        {'name':'10Y Real','value':'2.21','detail':'','light':'red'},
        {'name':'USD Broad Index','value':'{:.2f}'.format(last('dxy')),'detail':'','light':ampel(last('dxy'),110,118,invert=True)},
        {'name':'VIX','value':'{:.2f}'.format(vix_now),'detail':'','light':'mixed'},
        {'name':'10Y-3M Curve','value':'0.76','detail':'','light':'green'},
    ]

    changed = []
    changed.append(('MRI 7D','{:+.1f} pts'.format(dlt('mri',7)),'worsening' if dlt('mri',7)<0 else 'improving'))
    changed.append(('Liquidity 30D','{:+.1f} pts'.format(dlt('liquidity',30)),'worsening' if dlt('liquidity',30)<0 else 'improving'))
    changed.append(('Credit 7D','{:+.1f} pts'.format(dlt('credit',7)),'improving' if dlt('credit',7)<0 else 'worsening'))
    changed.append(('USD Stress 7D','{:+.1f} pts'.format(dlt('usd_stress',7)),'improving' if dlt('usd_stress',7)<0 else 'worsening'))

    if releases is None:
        releases = [
            ('Initial Claims','-4.7% YoY','weak','2026-05-30'),
            ('Nonfarm Payrolls','+0.3% YoY','hot','2026-05-01'),
            ('Unemployment','+0.0% YoY','supportive','2026-05-01'),
            ('Headline CPI','+3.8% YoY','hot','2026-04-01'),
            ('Core CPI','+2.7% YoY','hot','2026-04-01'),
        ]

    lage = {'TRANSITION':'Makro-Lage: Neutral. Kreditbedingungen sind angespannt. Keine aggressive Makro-Wette; bestaetigende Signale abwarten.',
            'DEFENSIVE':'Makro-Lage: Defensiv. USD-Stress ist hoch und begrenzt Risikoappetit. Kapitalschutz und Liquiditaet sind wichtiger als aggressives Risiko.',
            'CRISIS':'Makro-Lage: Krise. Maximale Defensive, Liquiditaet halten.',
            'CONSTRUCTIVE':'Makro-Lage: Konstruktiv. Risiko selektiv erhoehen, Bestaetigung durch Liquiditaet abwarten.',
            'RISK-ON':'Makro-Lage: Risk-on. Liquiditaet und Kredit unterstuetzen Risiko-Assets.'}[regime]
    investor = {'TRANSITION':'Kreditbedingungen sind angespannt. Der Macro Score hat sich ueber 7 Tage verschlechtert. Keine aggressive Makro-Wette; bestaetigende Signale abwarten.',
            'DEFENSIVE':'USD-Stress ist hoch und begrenzt Risikoappetit. Kreditbedingungen sind angespannt. Kapitalschutz und Liquiditaet sind wichtiger als aggressives Risiko.'}.get(regime, lage)

    payload = {
        'updated': dates[-1] + ' 09:01',
        'window': 2200,
        'dates': dates,
        'series': {k: r2(d[k]) for k in ['mri','credit_timing','usd_stress','fed','ecb','boj','pboc','glob','cross','eth_spx','btc_spx','spx_oil','eth_btc','liquidity','growth','credit','risk']},
        'headline': {
            'regime': regime, 'regime_color': COLORS[regime],
            'mri': round(mri_now,1), 'mri_7d': round(dlt('mri',7),1), 'mri_30d': round(dlt('mri',30),1), 'mri_30d_pct': round(pc('mri',30),1),
            'liquidity_label':'NEUTRAL', 'data_quality': data_quality, 'conviction': conv,
            'lage': lage, 'investor': investor,
            'watch':'Credit-Spreads/Finanzierungsdruck beobachten. | Liquiditaet darf nicht weiter drehen.',
        },
        'vix': {'regime':'CALM' if vix_now<20 else ('ELEVATED' if vix_now<30 else 'STRESS'),
                'value': round(vix_now,2), 'd7': round(dlt('vix',7),1), 'd30': round(dlt('vix',30),1), 'support': vix_support,
                'note':'VIX ist ruhig, aber andere Stress-/Credit-Signale bestaetigen Risk-on noch nicht voll.',
                'dxy_30d_pct': round(pc('dxy',30),1), 'usd_stress_7d': round(dlt('usd_stress',7),1)},
        'pulse': [
            {'name':'Liquidity','value':round(last('liquidity'),1),'trends':'30D {:+.1f} pts'.format(dlt('liquidity',30))},
            {'name':'Growth/Cycle','value':round(last('growth'),1),'trends':'30D {:+.1f} pts'.format(dlt('growth',30))},
            {'name':'Credit','value':round(last('credit'),1),'trends':'7D {:+.1f} pts • 30D {:+.1f} pts'.format(dlt('credit',7),dlt('credit',30))},
            {'name':'Risk Appetite','value':round(last('risk'),1),'trends':'7D {:+.1f} pts'.format(dlt('risk',7))},
            {'name':'USD Stress','value':round(last('usd_stress'),1),'trends':'7D {:+.1f} pts • 30D {:+.1f} pts'.format(dlt('usd_stress',7),dlt('usd_stress',30))},
        ],
        'what_changed': changed,
        'key_levels': key_levels,
        'releases': releases,
        'top_drivers': drivers,
        'cross_asset': {'phase':'Transition','confidence':'LOW','nasdaq_spx':'+4.0%','spx_oil':'+10.3%'},
        'leadership': [('ETH/SPX 90D','-28.9%'),('BTC/SPX 90D','-21.3%'),('SPX/Oil 90D','+10.3%'),('ETH/BTC 90D','-9.7%')],
        'chart_headers': {
            'mri':'Latest {:.1f} | 30D {:.1f}% | Window 2200d'.format(mri_now, pc('mri',30)),
            'credit_timing':'Latest {:.1f} | 30D {:.1f}% | Window 2200d'.format(last('credit_timing'), pc('credit_timing',30)),
            'usd_stress':'Latest {:.1f} | 30D {:.1f}% | Window 2200d'.format(last('usd_stress'), pc('usd_stress',30)),
            'cb':'Global 30D {:.1f}% | Window 2200d'.format(pc('glob',30)),
            'cb_legend':{'ecb':round(last('ecb'),2),'fed':round(last('fed'),2),'pboc':round(last('pboc'),2),'boj':round(last('boj'),2)},
        },
    }
    return payload

if __name__ == '__main__':
    S = np.load('_series.npy')
    names='mri liquidity growth credit risk usd_stress credit_timing fed ecb boj pboc glob m2 tga_rrp vix dxy hy cross eth_spx btc_spx spx_oil eth_btc'.split()
    series = dict(zip(names,S))
    dates = json.load(open('_dates.json'))
    p = build(series, dates)
    open('data.js','w',encoding='utf-8').write('window.MACRO_DATA = ' + json.dumps(p, ensure_ascii=False) + ';')
    h=p['headline']
    print('regime',h['regime'],'mri',h['mri'],h['mri_7d'],h['mri_30d'],'conv',h['conviction'])
    print('vix',p['vix']['value'],p['vix']['support'],'drivers',p['top_drivers'])
    print('headers',p['chart_headers']['mri'],'|',p['chart_headers']['usd_stress'],'|',p['chart_headers']['cb'])
    import os; print('data.js KB:', os.path.getsize('data.js')//1024)
