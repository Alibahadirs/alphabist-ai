const modulePath = process.argv[2];
const symbols = (process.argv[3] || "").split(",").filter(Boolean);
const period = process.argv[4] || "1y";
const BorsaAPI = require(modulePath);
const api = new BorsaAPI();

function emit(payload) {
  process.stdout.write(JSON.stringify(payload) + "\n");
}

(async () => {
  for (const symbol of symbols) {
    try {
      const result = await api.getHistoricalData(symbol, { period, interval: "1d" });
      const source = Array.isArray(result) ? result : (result?.quotes || result?.data || []);
      const quotes = source.filter(q => q && q.close != null && q.high != null && q.low != null).map(q => ({
        date: q.date instanceof Date ? q.date.toISOString() : q.date,
        open: q.open, high: q.high, low: q.low, close: q.close, volume: q.volume || 0,
      }));
      if (!quotes.length) throw new Error("Tarihsel veri boş.");
      emit({ symbol, ok: true, quotes });
    } catch (error) {
      emit({ symbol, ok: false, error: String(error?.message || error) });
    }
    await new Promise(resolve => setTimeout(resolve, 150));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
