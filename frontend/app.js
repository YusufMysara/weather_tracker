// Minimal client for the Weather Tracker API. No framework, no build step.

const state = { access: null, refresh: null, username: null, city: null, favorites: [] };

try {
  Object.assign(state, JSON.parse(localStorage.getItem('wt-auth') || '{}'));
} catch (e) { /* ignore corrupt storage */ }

const $ = (id) => document.getElementById(id);

// ---------- helpers ----------

function saveAuth() {
  localStorage.setItem('wt-auth', JSON.stringify({
    access: state.access, refresh: state.refresh, username: state.username,
  }));
}

// Shown as a toast notification that floats over the page and dismisses itself.
let toastTimer;

function showMessage(text, isInfo = false) {
  const box = $('message');
  clearTimeout(toastTimer);
  box.textContent = text;
  box.className = isInfo ? 'info' : '';
  box.hidden = !text;
  if (text) toastTimer = setTimeout(() => { box.hidden = true; }, isInfo ? 4000 : 6000);
}

$('message').addEventListener('click', () => showMessage(''));

// Turn any DRF error body into one readable string.
function errorText(data, status) {
  if (!data) return `Request failed (${status})`;
  if (typeof data === 'string') return data;
  if (data.error) return data.error;
  if (data.detail) return data.detail;
  return Object.entries(data)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(' ') : v}`)
    .join(' | ');
}

// Trade the long-lived refresh token for a new short-lived access token.
async function refreshAccess() {
  if (!state.refresh) return false;
  try {
    const res = await fetch('/api/token/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: state.refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    state.access = data.access;
    if (data.refresh) state.refresh = data.refresh;
    saveAuth();
    return true;
  } catch (e) { return false; }
}

async function api(path, { method = 'GET', body, auth = false, raw = false } = {}) {
  if (auth && !state.access) throw new Error('Please log in (or use "Try demo") to use this feature.');
  const send = () => {
    const headers = {};
    if (body) headers['Content-Type'] = 'application/json';
    if (auth) headers['Authorization'] = `Bearer ${state.access}`;
    return fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  };
  let res = await send();
  // Access token expired: refresh once and retry before giving up.
  if (res.status === 401 && auth && await refreshAccess()) res = await send();
  if (raw && res.ok) return res;
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (res.status === 401 && auth) {
    logout();
    throw new Error('Your session expired. Please log in again.');
  }
  if (!res.ok) throw new Error(errorText(data, res.status));
  return data;
}

// Build DOM nodes safely (textContent only, so AI text can never inject HTML).
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...children);
  return node;
}

function row(table, cells, onClick) {
  const tr = el('tr');
  cells.forEach((c) => tr.append(el('td', { textContent: c ?? '—' })));
  if (onClick) tr.addEventListener('click', onClick);
  table.querySelector('tbody').append(tr);
}

function fmtDiff(d) {
  if (d === null || d === undefined) return '—';
  return (d > 0 ? '+' : '') + d;
}

function fmtDate(iso) {
  return new Date(iso).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
}

// Shows the exact API call behind a result, with its raw JSON collapsed underneath.
function apiTrace(method, path, data, { auth = false, body } = {}) {
  const label = `${auth ? '🔒 ' : ''}${method} ${decodeURIComponent(path)}`;
  const payload = body ? `// request body\n${JSON.stringify(body)}\n\n// response\n` : '';
  return el('details', { className: 'trace' },
    el('summary', {}, el('code', { textContent: label }), ' — raw JSON'),
    el('pre', { textContent: payload + JSON.stringify(data, null, 2) }),
  );
}

function card(title, ...lines) {
  const c = el('div', { className: 'card' }, el('h4', { textContent: title }));
  lines.forEach((l) => {
    if (Array.isArray(l)) c.append(el('ul', {}, ...l.map((i) => el('li', { textContent: i }))));
    else if (l) c.append(el('p', { textContent: l }));
  });
  return c;
}

async function guarded(button, fn) {
  showMessage('');
  const label = button.textContent;
  button.disabled = true;
  button.textContent = 'Loading…';
  try {
    await fn();
  } catch (e) {
    showMessage(e.message);
  } finally {
    button.disabled = false;
    button.textContent = label;
  }
}

// ---------- tabs ----------

function showTab(name) {
  document.querySelectorAll('nav button').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('main > section').forEach((s) => { s.hidden = s.id !== `tab-${name}`; });
  showMessage('');
  if (name === 'favorites') loadFavorites();
}

document.querySelectorAll('nav button').forEach((b) => b.addEventListener('click', () => showTab(b.dataset.tab)));

// ---------- auth ----------

function renderAuth() {
  const box = $('auth');
  box.replaceChildren();
  if (state.access) {
    box.append(
      el('span', { className: 'muted', textContent: `Signed in as ${state.username}` }),
      el('button', { textContent: 'Log out', onclick: logout }),
    );
  } else {
    box.append(
      el('button', { textContent: 'Try demo', onclick: demoLogin }),
      el('button', { textContent: 'Log in', onclick: () => openAuth('login') }),
      el('button', { textContent: 'Register', onclick: () => openAuth('register') }),
    );
  }
}

function setTokens(tokens, username) {
  state.access = tokens.access;
  state.refresh = tokens.refresh;
  state.username = username;
  saveAuth();
  renderAuth();
}

function logout() {
  state.access = state.refresh = state.username = null;
  state.favorites = [];
  localStorage.removeItem('wt-auth');
  renderAuth();
}

async function demoLogin() {
  try {
    setTokens(await api('/api/demo-login/', { method: 'POST' }), 'demo');
    showMessage('Logged in as the shared demo user.', true);
  } catch (e) { showMessage(e.message); }
}

let authMode = 'login';

function openAuth(mode) {
  authMode = mode;
  const register = mode === 'register';
  $('auth-title').textContent = register ? 'Register' : 'Log in';
  $('auth-email').hidden = !register;
  $('auth-switch').textContent = register ? 'Have an account? Log in' : 'Need an account? Register';
  $('auth-password').autocomplete = register ? 'new-password' : 'current-password';
  $('auth-dialog').showModal();
}

$('auth-switch').addEventListener('click', (e) => {
  e.preventDefault();
  openAuth(authMode === 'login' ? 'register' : 'login');
});
$('auth-cancel').addEventListener('click', () => $('auth-dialog').close());

$('auth-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = $('auth-username').value.trim();
  const password = $('auth-password').value;
  try {
    if (authMode === 'register') {
      await api('/api/register/', { method: 'POST', body: { username, email: $('auth-email').value, password } });
    }
    setTokens(await api('/api/token/', { method: 'POST', body: { username, password } }), username);
    $('auth-dialog').close();
    $('auth-form').reset();
    showMessage(authMode === 'register' ? 'Account created. You are logged in.' : '', true);
  } catch (err) {
    showMessage(err.message);
    $('auth-dialog').close();
  }
});

// ---------- dashboard ----------

let latestRecords = [];

const SORTS = {
  'city': (a, b) => a.city.localeCompare(b.city),
  'temp-desc': (a, b) => b.temperature - a.temperature,
  'temp-asc': (a, b) => a.temperature - b.temperature,
  'humidity-desc': (a, b) => b.humidity - a.humidity,
  'wind-desc': (a, b) => b.wind_speed - a.wind_speed,
};

function timeAgo(iso) {
  const mins = Math.round((Date.now() - new Date(iso)) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  return hours < 48 ? `${hours} h ago` : `${Math.round(hours / 24)} days ago`;
}

function stat(label, key, unit, pick) {
  const best = latestRecords.reduce((a, b) => (pick(b[key], a[key]) ? b : a));
  return el('div', { className: 'stat' },
    el('div', { className: 'label', textContent: label }),
    el('div', { className: 'value', textContent: `${best[key]}${unit}` }),
    el('div', { className: 'where', textContent: best.city.replace(', Egypt', '') }),
  );
}

function renderSummary() {
  const summary = $('summary');
  summary.replaceChildren();
  if (!latestRecords.length) { $('updated').textContent = ''; return; }
  summary.append(
    stat('Hottest', 'temperature', '°C', (x, y) => x > y),
    stat('Coolest', 'temperature', '°C', (x, y) => x < y),
    stat('Most humid', 'humidity', '%', (x, y) => x > y),
    stat('Windiest', 'wind_speed', ' km/h', (x, y) => x > y),
  );
  const newest = latestRecords.reduce((a, b) => (new Date(b.recorded_at) > new Date(a.recorded_at) ? b : a));
  $('updated').textContent = `Last reading ${timeAgo(newest.recorded_at)} · ${latestRecords.length} cities`;
}

function renderCities() {
  const grid = $('city-grid');
  const term = $('search').value.trim().toLowerCase();
  const shown = latestRecords
    .filter((r) => r.city.toLowerCase().includes(term))
    .sort(SORTS[$('sort').value]);
  grid.replaceChildren();
  if (!shown.length) {
    grid.append(el('p', { className: 'empty', textContent: latestRecords.length ? 'No cities match your search.' : '' }));
    return;
  }
  shown.forEach((r) => {
    const d = r.temperature_diff;
    const diff = d ? el('span', { className: `diff ${d > 0 ? 'up' : 'down'}`, textContent: `${d > 0 ? '▲' : '▼'} ${Math.abs(d)}` }) : '';
    grid.append(el('button', { className: 'city-card', onclick: () => openCity(r.city) },
      el('div', { className: 'name', textContent: r.city.replace(', Egypt', '') }),
      el('div', {}, el('span', { className: 'temp', textContent: `${r.temperature}°C` }), diff),
      el('div', { className: 'meta', textContent: `💧 ${r.humidity}%  ·  🌬 ${r.wind_speed} km/h` }),
    ));
  });
}

async function loadLatest() {
  try {
    latestRecords = await api('/api/weather/latest/');
    if (!latestRecords.length) {
      showMessage('No weather data yet. Run the fetch task to collect readings.', true);
    }
    renderSummary();
    renderCities();
    $('latest-trace').replaceChildren(apiTrace('GET', '/api/weather/latest/', latestRecords));
  } catch (e) { showMessage(e.message); }
}

$('search').addEventListener('input', renderCities);
$('sort').addEventListener('change', renderCities);

async function openCity(city) {
  state.city = city;
  $('city-title').textContent = city;
  $('ai-output').replaceChildren();
  $('city-detail').hidden = false;
  const table = $('history-table');
  table.querySelector('tbody').replaceChildren();
  try {
    const data = await api(`/api/weather/?city=${encodeURIComponent(city)}`);
    data.results.forEach((r) => row(table, [fmtDate(r.recorded_at), r.temperature, fmtDiff(r.temperature_diff), r.humidity, r.wind_speed]));
  } catch (e) { showMessage(e.message); }
  $('city-detail').scrollIntoView({ behavior: 'smooth' });
}

$('insights-btn').addEventListener('click', (e) => guarded(e.target, async () => {
  const path = `/api/weather/insights/?city=${encodeURIComponent(state.city)}`;
  const d = await api(path, { auth: true });
  $('ai-output').replaceChildren(
    card('Summary', d.summary),
    card('Suggested activities', d.activities),
    card('Warnings', d.warnings),
    card('Compared to the 7-day average', d.anomaly),
    apiTrace('GET', path, d, { auth: true }),
  );
}));

$('forecast-btn').addEventListener('click', (e) => guarded(e.target, async () => {
  const path = `/api/weather/forecast/?city=${encodeURIComponent(state.city)}`;
  const d = await api(path, { auth: true });
  $('ai-output').replaceChildren(
    card('Forecast', d.forecast_summary, d.recommendation),
    card('Raw data', d.raw_forecast.map((f) => `${f.date}: high ${f.high}°C, low ${f.low}°C, rain ${f.precipitation_mm} mm`)),
    apiTrace('GET', path, d, { auth: true }),
  );
}));

$('fav-btn').addEventListener('click', (e) => guarded(e.target, async () => {
  await api('/api/favorite-cities/', { method: 'POST', body: { city: state.city }, auth: true });
  showMessage(`${state.city} added to favorites.`, true);
}));

$('export-btn').addEventListener('click', (e) => guarded(e.target, async () => {
  const res = await api('/api/weather/export/', { auth: true, raw: true });
  const url = URL.createObjectURL(await res.blob());
  el('a', { href: url, download: 'weather_records.xlsx' }).click();
  URL.revokeObjectURL(url);
}));

// ---------- ask ----------

$('ask-form').addEventListener('submit', (e) => {
  e.preventDefault();
  guarded(e.submitter, async () => {
    const body = { question: $('ask-input').value };
    const d = await api('/api/weather/ask/', { method: 'POST', body, auth: true });
    const r = d.raw_result;
    $('ask-output').replaceChildren(
      card('Answer', d.answer),
      r ? card('Raw result', `${r.aggregation} ${r.metric} for ${r.city}: ${r.value}`) : null,
      apiTrace('POST', '/api/weather/ask/', d, { auth: true, body }),
    );
  });
});

// ---------- compare ----------

async function loadCities() {
  try {
    const cities = await api('/api/cities/');
    $('compare-cities').replaceChildren(...cities.map((c) => {
      const box = el('input', { type: 'checkbox', value: c });
      box.style.width = 'auto';
      return el('label', {}, box, ' ' + c);
    }));
  } catch (e) { showMessage(e.message); }
}

$('compare-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const cities = [...document.querySelectorAll('#compare-cities input:checked')].map((i) => i.value);
  guarded(e.submitter, async () => {
    const qs = cities.map((c) => `cities=${encodeURIComponent(c)}`).join('&');
    const path = `/api/weather/compare/?${qs}`;
    const d = await api(path, { auth: true });
    $('compare-output').replaceChildren(
      card('Takeaway', d.comparison),
      ...d.cities.map((c) => card(c.city, `${c.temperature}°C, ${c.humidity}% humidity, ${c.wind_speed} km/h wind`)),
      apiTrace('GET', path, d, { auth: true }),
    );
  });
});

// ---------- favorites ----------

async function loadFavorites() {
  const list = $('fav-list');
  list.replaceChildren();
  if (!state.access) {
    list.append(el('li', { textContent: 'Log in (or use "Try demo") to see your favorites.' }));
    return;
  }
  try {
    const data = await api('/api/favorite-cities/', { auth: true });
    if (!data.results.length) list.append(el('li', { textContent: 'No favorites yet. Open a city and click "Add to favorites".' }));
    data.results.forEach((f) => list.append(el('li', {},
      el('a', { href: '#', textContent: f.city, onclick: (e) => { e.preventDefault(); showTab('dashboard'); openCity(f.city); } }),
      el('button', {
        textContent: 'Remove',
        onclick: async () => {
          try { await api(`/api/favorite-cities/${f.id}/`, { method: 'DELETE', auth: true }); loadFavorites(); }
          catch (err) { showMessage(err.message); }
        },
      }),
    )));
  } catch (e) { showMessage(e.message); }
}

// ---------- init ----------

renderAuth();
loadLatest();
loadCities();
