// Gramin Vaani Saathi — PWA shell.
//
// No build step and no framework. That is a deliberate choice for this stage:
// the interesting engineering in this project is the model layer and the ledger,
// and a toolchain between an edit and a reload would slow down the part that
// actually needs iteration. Everything here is plain ES modules that Django
// serves straight off disk.
//
// Three invariants the UI must never break:
//  1. Nothing that moves money happens without an explicit confirmation the user
//     has heard *and* seen.
//  2. Every queued action carries a client-minted idempotency key, so replaying
//     the offline queue after reconnect cannot double-spend.
//  3. A stale balance is always labelled with the time it was read.

import { LANGS, LANG_META, makeT } from './i18n.js';
import { SCHEMES, LESSONS, TIPS, PHRASES } from './content.js';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ─────────────────────────────────────────────────────────── state
const store = {
  get(key, fallback = null) {
    try { return JSON.parse(localStorage.getItem('gvs.' + key)) ?? fallback; }
    catch { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem('gvs.' + key, JSON.stringify(value)); } catch { /* private mode */ }
  },
  del(key) { try { localStorage.removeItem('gvs.' + key); } catch { /* ignore */ } },
};

const state = {
  lang: store.get('lang', null),
  token: store.get('token', null),
  user: store.get('user', null),
  account: store.get('account', null),
  accountAt: store.get('accountAt', null),
  contacts: store.get('contacts', []),
  transactions: [],
  screen: 'language',
  history: [],
  pending: null,      // action awaiting confirmation
  draft: { payee: null, amount: '' },
  queue: store.get('queue', []),
};

let t = makeT(state.lang || 'hi');

// Demo identities created by `python backend/manage.py seed_demo`. Sandbox
// accounts in a local database with play money — there is nothing real to
// protect here, and one tap to sign in is worth a lot during a demo.
const DEMO_USERS = [
  { username: 'sita', name: { hi: 'सीता', en: 'Sita', ta: 'சீதா', te: 'సీత' }, color: '#0E7C6B', initial: 'स' },
  { username: 'ramesh', name: { hi: 'रमेश', en: 'Ramesh', ta: 'ரமேஷ்', te: 'రమేష్' }, color: '#DD6B20', initial: 'र' },
  { username: 'lakshmi', name: { hi: 'लक्ष्मी', en: 'Lakshmi', ta: 'லட்சுமி', te: 'లక్ష్మి' }, color: '#6B46C1', initial: 'ल' },
];
const DEMO_PASSWORD = 'demo1234';

const TILES = [
  { screen: 'balance', key: 'tileBalance', emoji: '💰', bg: '#E1F1ED' },
  { screen: 'send',    key: 'tileSend',    emoji: '📤', bg: '#FCEBDD' },
  { screen: 'schemes', key: 'tileSchemes', emoji: '📋', bg: '#E7EDFA' },
  { screen: 'learn',   key: 'tileLearn',   emoji: '🎓', bg: '#FDF3D8' },
  { screen: 'scan',    key: 'tileScan',    emoji: '📷', bg: '#EDE7F8' },
  { screen: 'safety',  key: 'tileSafety',  emoji: '🛡️', bg: '#FBE6E4' },
];

// ─────────────────────────────────────────────────────────── api
async function api(path, { method = 'GET', body = null } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (state.token) headers.Authorization = `Token ${state.token}`;

  const res = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  });

  if (res.status === 401) { signOut(); throw new Error('unauthorised'); }

  let data = null;
  try { data = await res.json(); } catch { /* empty or non-JSON body */ }
  if (!res.ok) {
    const err = new Error(data?.detail || `HTTP ${res.status}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

// ─────────────────────────────────────────────────────────── speech out
let voices = [];
function loadVoices() { voices = window.speechSynthesis?.getVoices?.() || []; }
loadVoices();
if (window.speechSynthesis) window.speechSynthesis.onvoiceschanged = loadVoices;

function speak(text, lang = state.lang) {
  if (!text || !window.speechSynthesis) return;
  const tag = LANG_META[lang]?.speech || 'hi-IN';
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = tag;
  // Prefer an exact regional voice, then any voice for the base language. If
  // neither exists the browser falls back on its default, which mispronounces
  // Indic text but still reads the digits correctly — better than silence.
  const base = tag.split('-')[0];
  utterance.voice =
    voices.find((v) => v.lang === tag) ||
    voices.find((v) => v.lang?.startsWith(base)) ||
    null;
  utterance.rate = 0.92; // slightly slow: these are unfamiliar financial terms
  window.speechSynthesis.speak(utterance);
}

// ─────────────────────────────────────────────────────────── speech in
const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let listening = false;

function startListening() {
  if (!SpeechRecognitionCtor) { showTypeFallback(t('noMic')); return; }
  if (listening) { recognition?.stop(); return; }

  recognition = new SpeechRecognitionCtor();
  recognition.lang = LANG_META[state.lang]?.speech || 'hi-IN';
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  let finalText = '';
  recognition.onstart = () => {
    listening = true;
    $('#mic').classList.add('listening');
    $('#mic-hint').textContent = t('listening');
  };
  recognition.onresult = (event) => {
    let interim = '';
    for (const result of event.results) {
      if (result.isFinal) finalText += result[0].transcript;
      else interim += result[0].transcript;
    }
    showHeard(finalText || interim);
  };
  recognition.onerror = (event) => {
    listening = false;
    $('#mic').classList.remove('listening');
    $('#mic-hint').textContent = t('tapToSpeak');
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
      showTypeFallback(t('micDenied'));
    }
  };
  recognition.onend = () => {
    listening = false;
    $('#mic').classList.remove('listening');
    $('#mic-hint').textContent = t('tapToSpeak');
    const said = finalText.trim();
    if (said) sendUtterance(said);
  };

  recognition.start();
}

function showTypeFallback(message) {
  toast(message);
  $('#type-form').hidden = false;
  $('#type-input').focus();
}

function showHeard(said, reply = null) {
  const box = $('#heard');
  box.hidden = false;
  box.innerHTML = '';
  const you = document.createElement('span');
  you.className = 'heard-you';
  you.textContent = t('youSaid');
  const text = document.createElement('span');
  text.textContent = said;
  box.append(you, text);
  if (reply) {
    const r = document.createElement('span');
    r.className = 'heard-reply';
    r.textContent = reply;
    box.append(r);
  }
}

// ─────────────────────────────────────────────────────────── dialog turn
async function sendUtterance(text) {
  if (!state.token) { toast(t('networkError')); return; }
  $('#mic').classList.add('busy');
  $('#mic-hint').textContent = t('thinking');
  try {
    const result = await api('/api/voice/text/', {
      method: 'POST',
      body: { text, language: state.lang, pending: state.pending },
    });
    handleDialogResult(text, result);
  } catch (err) {
    console.error(err);
    toast(t('networkError'), true);
  } finally {
    $('#mic').classList.remove('busy');
    $('#mic-hint').textContent = t('tapToSpeak');
  }
}

function handleDialogResult(said, result) {
  showHeard(said, result.reply_text);
  speak(result.reply_text, result.language || state.lang);

  if (result.language && result.language !== state.lang && LANGS.includes(result.language)) {
    setLanguage(result.language, { silent: true });
  }

  if (result.needs_confirmation && result.pending) {
    state.pending = result.pending;
    openConfirm(result.reply_text);
    return;
  }

  state.pending = null;
  closeConfirm();

  if (result.action_taken === 'transfer_executed' || result.action_taken === 'transfer_replayed') {
    refreshAccount();
  }
  if (result.screen) go(result.screen);
}

// ─────────────────────────────────────────────────────────── confirmation
function openConfirm(text) {
  $('#confirm-text').textContent = text;
  $('#confirm-sheet').hidden = false;
}
function closeConfirm() { $('#confirm-sheet').hidden = true; }

async function confirmPending() {
  const pending = state.pending;
  if (!pending) return closeConfirm();
  closeConfirm();

  if (!navigator.onLine) { enqueue(pending); return; }

  try {
    const result = await api('/api/voice/confirm/', {
      method: 'POST',
      body: { pending, language: state.lang },
    });
    state.pending = null;
    state.draft = { payee: null, amount: '' };
    showHeard(t('yes'), result.reply_text);
    speak(result.reply_text);
    await refreshAccount();
    go('balance');
  } catch (err) {
    console.error(err);
    // A network failure between confirm and response is exactly the case the
    // idempotency key exists for: queue it, and replay is safe.
    enqueue(pending);
  }
}

function cancelPending() {
  state.pending = null;
  state.draft = { payee: null, amount: '' };
  closeConfirm();
  const message = { hi: 'ठीक है, रद्द कर दिया।', en: 'Cancelled. No money was sent.',
                    ta: 'ரத்து செய்யப்பட்டது.', te: 'రద్దు చేశాను.' }[state.lang];
  showHeard(t('no'), message);
  speak(message);
}

// ─────────────────────────────────────────────────────────── offline queue
function enqueue(pending) {
  state.queue.push({ pending, language: state.lang, at: Date.now() });
  store.set('queue', state.queue);
  state.pending = null;
  renderOffline();
  const message = { hi: 'नेटवर्क नहीं है। जुड़ते ही यह काम भेज दिया जाएगा।',
                    en: 'No network. This will be sent as soon as you reconnect.',
                    ta: 'இணைப்பு இல்லை. இணைந்ததும் இது அனுப்பப்படும்.',
                    te: 'నెట్‌వర్క్ లేదు. కనెక్ట్ అయిన వెంటనే పంపబడుతుంది.' }[state.lang];
  showHeard('', message);
  speak(message);
}

async function drainQueue() {
  if (!state.queue.length || !navigator.onLine || !state.token) return;
  const remaining = [];
  for (const item of state.queue) {
    try {
      // Same idempotency key as the original attempt. If the first request did
      // reach the server before the connection dropped, this returns the
      // original transaction instead of making a second one.
      await api('/api/voice/confirm/', {
        method: 'POST',
        body: { pending: item.pending, language: item.language },
      });
    } catch (err) {
      if (!err.status) { remaining.push(item); }  // network error: keep it
    }
  }
  state.queue = remaining;
  store.set('queue', state.queue);
  renderOffline();
  await refreshAccount();
}

function renderOffline() {
  const offline = !navigator.onLine;
  $('#offline-banner').hidden = !offline && state.queue.length === 0;
  $('[data-i18n="offline"]').textContent = offline ? t('offline') : t('queued', { n: state.queue.length });
  const badge = $('#queue-count');
  badge.hidden = state.queue.length === 0;
  badge.textContent = state.queue.length;
}

// ─────────────────────────────────────────────────────────── auth
async function signIn(username, password) {
  const data = await api('/api/accounts/login/', {
    method: 'POST', body: { username, password },
  });
  state.token = data.token;
  state.user = data.user;
  store.set('token', state.token);
  store.set('user', state.user);
  if (data.profile?.language && LANGS.includes(data.profile.language)) {
    setLanguage(data.profile.language, { silent: true });
  }
  await refreshAccount();
  go('home', { reset: true });
}

function signOut() {
  state.token = null; state.user = null; state.account = null;
  state.contacts = []; state.transactions = []; state.pending = null;
  ['token', 'user', 'account', 'accountAt', 'contacts'].forEach(store.del);
  go('auth', { reset: true });
}

async function refreshAccount() {
  if (!state.token) return;
  try {
    const me = await api('/api/accounts/me/');
    state.account = me.account;
    state.contacts = me.contacts || [];
    state.accountAt = Date.now();
    store.set('account', state.account);
    store.set('accountAt', state.accountAt);
    store.set('contacts', state.contacts);
  } catch { /* offline: keep the cached figure, stamped with its age */ }

  try {
    const txns = await api('/api/banking/transactions/?limit=10');
    state.transactions = txns.results || [];
  } catch { /* offline */ }

  renderBalance();
}

// ─────────────────────────────────────────────────────────── navigation
function go(screen, { reset = false, push = true } = {}) {
  if (reset) state.history = [];
  else if (push && state.screen && state.screen !== screen) state.history.push(state.screen);

  state.screen = screen;
  $$('.screen').forEach((el) => { el.hidden = el.dataset.screen !== screen; });

  const chromeless = screen === 'language' || screen === 'auth';
  $('#micbar').hidden = chromeless || !state.token;
  $('#btn-back').hidden = state.history.length === 0 || screen === 'home';
  $('#btn-lang').hidden = screen === 'language';

  window.scrollTo({ top: 0, behavior: 'instant' });
  renderScreen(screen);
}

function back() {
  const previous = state.history.pop();
  go(previous || 'home', { push: false });
}

// ─────────────────────────────────────────────────────────── language
function setLanguage(lang, { silent = false } = {}) {
  state.lang = lang;
  store.set('lang', lang);
  t = makeT(lang);
  document.documentElement.lang = lang;
  // The last exchange is in the old language; leaving it on screen next to
  // freshly translated chrome reads as a bug.
  $('#heard').hidden = true;
  applyStrings();
  renderScreen(state.screen);
  if (!silent) speak(LANG_META[lang].native, lang);
}

function applyStrings() {
  $$('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $$('[data-i18n-ph]').forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  $('#lang-label').textContent = LANG_META[state.lang]?.chip || 'हिं';
  $('#brand-name').textContent = t('appName');
  renderOffline();
}

// ─────────────────────────────────────────────────────────── rendering
function money(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('en-IN', { maximumFractionDigits: n % 1 ? 2 : 0 });
}

function renderBalance() {
  const amount = state.account ? money(state.account.balance) : '—';
  $('#home-balance').textContent = amount;
  $('#detail-balance').textContent = amount;
  $('#detail-vpa').textContent = state.account
    ? `${state.account.vpa} · ${state.account.bank_name}`
    : '';

  // Never present a cached figure as live. The stamp is the honesty guarantee.
  const stamp = $('#balance-stamp');
  if (state.accountAt && !navigator.onLine) {
    stamp.textContent = t('asOf', {
      time: new Date(state.accountAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    });
  } else {
    stamp.textContent = '';
  }
}

function personCard({ initial, color, name, sub, onClick }) {
  const card = document.createElement('button');
  card.className = 'person-card';
  const avatar = document.createElement('span');
  avatar.className = 'avatar';
  avatar.style.background = color;
  avatar.textContent = initial;
  const label = document.createElement('span');
  label.className = 'person-name';
  label.textContent = name;
  card.append(avatar, label);
  if (sub) {
    const s = document.createElement('span');
    s.className = 'person-sub';
    s.textContent = sub;
    card.append(s);
  }
  card.addEventListener('click', onClick);
  return card;
}

function infoCard({ emoji, title, text, onSpeak }) {
  const card = document.createElement('div');
  card.className = 'info-card';
  card.innerHTML = `
    <span class="info-emoji" aria-hidden="true"></span>
    <span class="info-body">
      <span class="info-title"></span>
      <span class="info-text"></span>
    </span>
    <button class="info-speak" aria-label="Listen">🔊</button>`;
  $('.info-emoji', card).textContent = emoji;
  $('.info-title', card).textContent = title;
  $('.info-text', card).textContent = text;
  $('.info-speak', card).addEventListener('click', onSpeak);
  return card;
}

// Greet people in their own script. The seeded users carry a Latin first_name
// for the ledger; the name a person expects to see is the local one.
function displayName() {
  const demo = DEMO_USERS.find((u) => u.username === state.user?.username);
  return demo ? demo.name[state.lang] : (state.user?.first_name || state.user?.username || '');
}

function renderTiles() {
  const grid = $('#tile-grid');
  grid.innerHTML = '';
  for (const tile of TILES) {
    const label = t(tile.key);
    const button = document.createElement('button');
    button.className = 'tile';
    button.innerHTML = `
      <span class="tile-emoji" aria-hidden="true"></span>
      <span class="tile-label"></span>
      <span class="tile-speak" role="button" tabindex="0" aria-label="Listen">🔊</span>`;
    const emoji = $('.tile-emoji', button);
    emoji.textContent = tile.emoji;
    emoji.style.background = tile.bg;
    $('.tile-label', button).textContent = label;

    // The speaker reads the label without navigating: a user who cannot read
    // needs to identify a tile before committing to it.
    $('.tile-speak', button).addEventListener('click', (event) => {
      event.stopPropagation();
      speak(label);
    });
    button.addEventListener('click', () => { speak(label); go(tile.screen); });
    grid.append(button);
  }
}

function renderTransactions() {
  const list = $('#txn-list');
  list.innerHTML = '';
  if (!state.transactions.length) {
    const empty = document.createElement('li');
    empty.className = 'txn';
    empty.textContent = t('noTxns');
    list.append(empty);
    return;
  }
  for (const txn of state.transactions) {
    const out = txn.direction === 'debit';
    const row = document.createElement('li');
    row.className = 'txn' + (txn.status === 'failed' ? ' failed' : '');
    row.innerHTML = `
      <span class="txn-arrow ${out ? 'out' : 'in'}" aria-hidden="true">${out ? '↑' : '↓'}</span>
      <span class="txn-body">
        <span class="txn-who"></span>
        <span class="txn-when"></span>
      </span>
      <span class="txn-amt"></span>`;
    $('.txn-who', row).textContent = txn.counterparty_name || txn.counterparty_vpa || '—';
    $('.txn-when', row).textContent = new Date(txn.created_at).toLocaleString([], {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    });
    $('.txn-amt', row).textContent = `${out ? '−' : '+'}₹${money(txn.amount)}`;
    if (txn.status === 'failed') {
      const tag = document.createElement('span');
      tag.className = 'txn-failed-tag';
      tag.textContent = ' ' + (txn.failure_reason || 'failed');
      $('.txn-when', row).append(tag);
    }
    list.append(row);
  }
}

// ── send-money flow: contact, then amount, then the confirmation sheet
function renderSend() {
  const grid = $('#contact-grid');
  grid.innerHTML = '';
  const palette = ['#0E7C6B', '#DD6B20', '#6B46C1', '#2F7D32', '#B3261E', '#1D4ED8'];

  state.contacts.forEach((contact, i) => {
    const display = contact.name_local || contact.name;
    grid.append(personCard({
      initial: display.slice(0, 1),
      color: palette[i % palette.length],
      name: display,
      sub: contact.vpa,
      onClick: () => {
        state.draft = { payee: contact, amount: '' };
        speak(display);
        renderAmountStep();
      },
    }));
  });

  $('#amount-block').hidden = true;
}

function renderAmountStep() {
  const block = $('#amount-block');
  block.hidden = false;
  $('#amount-payee').textContent = state.draft.payee?.name_local || state.draft.payee?.name || '';
  $('#amount-value').textContent = state.draft.amount || '0';

  const quick = $('#quick-amounts');
  quick.innerHTML = '';
  for (const value of [100, 200, 500, 1000]) {
    const chip = document.createElement('button');
    chip.className = 'chip';
    chip.textContent = `₹${value}`;
    chip.addEventListener('click', () => {
      state.draft.amount = String(value);
      $('#amount-value').textContent = state.draft.amount;
    });
    quick.append(chip);
  }

  const keypad = $('#keypad');
  keypad.innerHTML = '';
  for (const key of ['1', '2', '3', '4', '5', '6', '7', '8', '9', '00', '0', '⌫']) {
    const button = document.createElement('button');
    button.className = 'key';
    button.textContent = key;
    button.addEventListener('click', () => {
      if (key === '⌫') state.draft.amount = state.draft.amount.slice(0, -1);
      else if (state.draft.amount.length < 6) state.draft.amount += key;
      $('#amount-value').textContent = state.draft.amount || '0';
    });
    keypad.append(button);
  }

  block.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function reviewTransfer() {
  const { payee, amount } = state.draft;
  const value = Number(amount);
  if (!payee || !Number.isFinite(value) || value < 1) return;

  const name = payee.name_local || payee.name;
  // The key is minted here, before the network is involved, so the same action
  // keeps its identity whether it is sent now or replayed from the queue later.
  state.pending = {
    action: 'send_money',
    amount: String(value),
    payee_vpa: payee.vpa,
    payee_name: name,
    idempotency_key: `tap-${crypto.randomUUID()}`,
  };
  const question = {
    hi: `${name} को ${value} रुपये भेजें?`,
    en: `Send ${value} rupees to ${name}?`,
    ta: `${name} க்கு ${value} ரூபாய் அனுப்பவா?`,
    te: `${name} కి ${value} రూపాయలు పంపాలా?`,
  }[state.lang];
  openConfirm(question);
  speak(question);
}

function renderSchemes() {
  const list = $('#scheme-list');
  list.innerHTML = '';
  for (const scheme of SCHEMES) {
    const title = scheme.title[state.lang];
    const text = scheme.text[state.lang];
    list.append(infoCard({
      emoji: scheme.emoji, title, text,
      onSpeak: () => speak(`${title}. ${text}`),
    }));
  }
}

function renderLessons() {
  const list = $('#lesson-list');
  list.innerHTML = '';
  for (const lesson of LESSONS) {
    const title = lesson.title[state.lang];
    const text = lesson.text[state.lang];
    list.append(infoCard({
      emoji: lesson.emoji, title, text,
      onSpeak: () => speak(`${title}. ${text}`),
    }));
  }
}

function renderTips() {
  const list = $('#tip-list');
  list.innerHTML = '';
  for (const tip of TIPS) {
    const title = tip.title[state.lang];
    const text = tip.text[state.lang];
    list.append(infoCard({
      emoji: tip.emoji, title, text,
      onSpeak: () => speak(`${title}. ${text}`),
    }));
  }
}

function renderPhrases() {
  const list = $('#phrase-list');
  list.innerHTML = '';
  for (const phrase of PHRASES[state.lang] || []) {
    // Tapping a phrase runs it through the same NLU endpoint speech uses, so
    // the help screen doubles as a live test harness during development.
    list.append(infoCard({
      emoji: '💬', title: phrase, text: '',
      onSpeak: () => speak(phrase),
    }));
    list.lastElementChild.addEventListener('click', (event) => {
      if (event.target.closest('.info-speak')) return;
      go('home');
      sendUtterance(phrase);
    });
    list.lastElementChild.style.cursor = 'pointer';
  }
}

function renderAuth() {
  const grid = $('#demo-users');
  grid.innerHTML = '';
  for (const person of DEMO_USERS) {
    grid.append(personCard({
      initial: person.initial,
      color: person.color,
      name: person.name[state.lang],
      sub: '@' + person.username,
      onClick: async () => {
        try { await signIn(person.username, DEMO_PASSWORD); }
        catch (err) {
          console.error(err);
          toast(err.status === 400 ? 'Run: python backend/manage.py seed_demo' : t('networkError'), true);
        }
      },
    }));
  }
}

function renderScreen(screen) {
  switch (screen) {
    case 'auth':    renderAuth(); break;
    case 'home':
      renderTiles();
      renderBalance();
      $('#greeting-text').textContent = t('greeting', { name: displayName() });
      break;
    case 'balance': renderBalance(); renderTransactions(); break;
    case 'send':    renderSend(); break;
    case 'schemes': renderSchemes(); break;
    case 'learn':   renderLessons(); break;
    case 'safety':  renderTips(); break;
    case 'help':    renderPhrases(); break;
    default: break;
  }
  $$('.lang-card').forEach((card) => {
    card.setAttribute('aria-pressed', String(card.dataset.lang === state.lang));
  });
}

// ─────────────────────────────────────────────────────────── toast
let toastTimer = null;
function toast(message, isError = false) {
  const el = $('#toast');
  el.textContent = message;
  el.className = 'toast' + (isError ? ' error' : '');
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 4200);
}

// ─────────────────────────────────────────────────────────── camera
let cameraStream = null;
async function openCamera(mode) {
  const wrap = $('#camera-wrap');
  const status = $('#scan-status');
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: 'environment' } },
    });
    $('#camera').srcObject = cameraStream;
    await $('#camera').play();
    wrap.hidden = false;
    status.textContent = mode === 'qr'
      ? 'QR reading is wired up on Day 5 (OpenCV + pyzbar on the server).'
      : 'Note recognition is wired up on Day 5 (MobileNetV3 on the server).';
  } catch (err) {
    console.error(err);
    status.textContent = 'Camera not available on this device or permission was denied.';
  }
}

function closeCamera() {
  cameraStream?.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  $('#camera-wrap').hidden = true;
}

// ─────────────────────────────────────────────────────────── wiring
function wire() {
  $$('.lang-card').forEach((card) => {
    card.addEventListener('click', () => {
      setLanguage(card.dataset.lang);
      go(state.token ? 'home' : 'auth', { reset: true });
    });
  });

  $('#btn-lang').addEventListener('click', () => go('language'));
  $('#btn-back').addEventListener('click', back);
  $('#btn-home').addEventListener('click', () => go('home', { reset: true }));
  $('#btn-signout').addEventListener('click', signOut);

  $('#login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const form = new FormData(event.target);
    try {
      await signIn(form.get('username'), form.get('password'));
    } catch (err) {
      toast(err.status === 400 ? t('loginFailed') : t('networkError'), true);
    }
  });

  $('#mic').addEventListener('click', startListening);
  $('#btn-type').addEventListener('click', () => {
    const form = $('#type-form');
    form.hidden = !form.hidden;
    if (!form.hidden) $('#type-input').focus();
  });
  $('#type-form').addEventListener('submit', (event) => {
    event.preventDefault();
    const input = $('#type-input');
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    sendUtterance(text);
  });

  $('#btn-yes').addEventListener('click', confirmPending);
  $('#btn-no').addEventListener('click', cancelPending);
  $('#confirm-sheet').addEventListener('click', (event) => {
    if (event.target.id === 'confirm-sheet') cancelPending();
  });

  $('#btn-review').addEventListener('click', reviewTransfer);
  $$('[data-go]').forEach((el) => el.addEventListener('click', () => go(el.dataset.go)));

  $$('[data-scan]').forEach((el) => el.addEventListener('click', () => openCamera(el.dataset.scan)));
  $('#btn-capture').addEventListener('click', () => {
    toast('Capture lands on Day 5, with the OpenCV endpoints.');
  });

  $('#btn-scam-check').addEventListener('click', async () => {
    const text = $('#scam-input').value.trim();
    const box = $('#scam-result');
    if (!text) return;
    box.hidden = false;
    box.className = 'verdict pending';
    box.textContent = t('scamPending');
    speak(t('scamPending'));
    // Day 4 replaces this with POST /api/fraud/check and the model's reasons.
  });

  $$('[data-speak]').forEach((el) => el.addEventListener('click', () => {
    const target = $(el.dataset.speak);
    if (target) speak(`${t('balanceLabel')} ${target.textContent} ₹`);
  }));

  window.addEventListener('online', () => { renderOffline(); drainQueue(); });
  window.addEventListener('offline', renderOffline);

  // Leaving the scan screen must release the camera, or the indicator light
  // stays on and the user reasonably assumes they are still being recorded.
  document.addEventListener('click', () => {
    if (state.screen !== 'scan' && cameraStream) closeCamera();
  }, true);
}

// ─────────────────────────────────────────────────────────── boot
async function boot() {
  wire();

  if (!state.lang || !LANGS.includes(state.lang)) {
    state.lang = 'hi';
    t = makeT('hi');
    applyStrings();
    go('language', { reset: true });
  } else {
    t = makeT(state.lang);
    document.documentElement.lang = state.lang;
    applyStrings();
    go(state.token ? 'home' : 'auth', { reset: true });
  }

  renderOffline();
  if (state.token) { await refreshAccount(); await drainQueue(); }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch((err) => console.warn('SW failed', err));
  }
}

boot();
