(() => {
  const m = window.TradingViewApi._activeChartWidgetWV.value()._chartWidget.model();
  const bars = m.mainSeries().bars();
  const st = m.dataSources().find(s => s.metaInfo && s.metaInfo().description && s.metaInfo().description.indexOf('Turtle') === 0);
  const lbls = st._graphics._primitivesCollection.dwglabels.get('labels');
  const all = [...lbls.get(false)._primitivesDataById.values()];
  const sig = all.filter(l => /^(BUY|SELL)/.test(l.t || '')).map(l => ({t: l.t, tt: l.tt}));
  const b = [];
  for (let i = bars.firstIndex(); i <= bars.lastIndex(); i++) { const v = bars.valueAt(i); if (v) b.push([v[0], v[1], v[2], v[3], v[4], v[5]]); }
  return JSON.stringify({sig, bars: b});
})()
