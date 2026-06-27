/* Capa de acceso a la API del backend */
const API = {
  async _json(url, opts) {
    const r = await fetch(url, opts);
    const data = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(data.detail || `Error ${r.status}`);
    return data;
  },
  health() { return this._json('/health'); },
  stats() { return this._json('/stats'); },
  timeseries(days = 14) { return this._json(`/stats/timeseries?days=${days}`); },
  byClass() { return this._json('/stats/by-class'); },
  history(limit = 50) { return this._json(`/history?limit=${limit}`); },
  clearHistory() { return this._json('/history', { method: 'DELETE' }); },
  getConfig() { return this._json('/config'); },
  classes() { return this._json('/classes'); },
  saveConfig(payload) {
    return this._json('/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },
  testTelegram() { return this._json('/telegram/test', { method: 'POST' }); },
  detect(file) {
    const fd = new FormData();
    fd.append('file', file);
    return this._json('/detect', { method: 'POST', body: fd });
  },
};
