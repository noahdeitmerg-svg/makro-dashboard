# -*- coding: utf-8 -*-
# Erzeugt pboc_assets.csv: PBoC-Bilanzsumme in T USD, monatlich interpoliert.
# Anker: offizielle Jahresend-/Monatswerte (PBoC via TradingEconomics/MacroMicro), FX = Jahresdurchschnitt USDCNY.
# APPROXIMATION zwischen den Ankern - dokumentiert in MACRO_ENGINE.md.
import pandas as pd, numpy as np
anchors = [  # (Datum, Bilanz T CNY, USDCNY)
 ('2007-12-31',16.9,7.30),('2008-12-31',20.7,6.83),('2009-12-31',22.8,6.83),('2010-12-31',25.9,6.62),
 ('2011-12-31',28.1,6.30),('2012-12-31',29.5,6.23),('2013-12-31',31.7,6.05),('2014-12-31',33.8,6.21),
 ('2015-12-31',31.8,6.49),('2016-12-31',34.4,6.95),('2017-12-31',36.3,6.51),('2018-12-31',37.2,6.88),
 ('2019-12-31',37.1,6.96),('2020-12-31',38.7,6.52),('2021-12-31',39.6,6.36),('2022-12-31',41.7,6.96),
 ('2023-12-31',45.7,7.10),('2024-12-31',45.9,7.30),('2025-06-30',47.2,7.16),('2025-12-31',48.6,7.05),
 ('2026-02-28',49.99,7.02),('2026-03-31',49.14,7.01),('2026-06-09',49.3,7.01),
]
a = pd.DataFrame(anchors, columns=['date','cny','fx']); a['date']=pd.to_datetime(a['date']); a=a.set_index('date')
idx = pd.date_range('2008-01-31','2026-06-09',freq='ME').union(pd.DatetimeIndex([a.index[-1]]))
cny = a['cny'].reindex(a.index.union(idx)).interpolate(method='time').reindex(idx)
fx  = a['fx'].reindex(a.index.union(idx)).interpolate(method='time').reindex(idx)
usd = (cny/fx).round(3)
usd.to_csv('pboc_assets.csv', header=['pboc_t_usd'], index_label='date')
print('pboc_assets.csv:', len(usd), 'Zeilen | 2020-12:', usd['2020-12-31'], '| letzter Wert:', usd.iloc[-1])