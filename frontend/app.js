// Gramin Vaani Saathi — PWA.
//
// No build step and no framework: plain ES modules that Django serves off
// disk. The interesting engineering in this project is the model layer and
// the ledger; a toolchain between an edit and a reload would slow down the
// part that actually needs iteration.
//
// Three invariants the UI must never break:
//  1. Nothing that moves money happens without an explicit confirmation the
//     user has heard *and* seen.
//  2. Every queued action carries a client-minted idempotency key, so
//     replaying the offline queue after reconnect cannot double-spend.
//  3. A stale balance is always labelled with the time it was read.

import { LANGS, LANG_META, makeT } from './i18n.js';
import { TIPS, PHRASES } from './content.js';
import { initCursor } from './cursor.js';
import { iconSvg, setIcon } from './icons.js';
import { queueAll, queuePut, queueDelete, migrateLegacy } from './db.js';

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

// ─────────────────────────────────────────────────────────── persistence
// localStorage for preferences and read caches only. The payment queue lives
// in IndexedDB (db.js), because it is the one thing that must not be lost.
const store = {
  get(key, fallback = null) {
    try { return JSON.parse(localStorage.getItem('gvs.' + key)) ?? fallback; } catch { return fallback; }
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
  profile: store.get('profile', null),
  transactions: store.get('transactions', []),
  view: 'overview',
  authScreen: 'language',
  pending: null,                         // action awaiting confirmation
  draft: { payee: null, amount: '' },
  signup: null,
  queueCount: 0,
  txnFilter: 'all',
  schemes: null,                         // { summary, results } for state.lang
  schemeFilter: 'all',
  schemeSearch: null,                    // { query, results } or null
  schemeSelected: null,
  lessons: null,                         // { completed, total, results }
  lessonSelected: null,
  quiz: null,                            // { lessonId, answers: [], result }
  scanMode: 'qr',
  scanResult: null,
  scamVerdict: null,
  checks: [],
  reportKind: null,
  reportSteps: null,
  askResult: null,                       // { answered, best, related } from /api/fraud/ask/
  askShown: null,                        // the entry shown as the answer (best, or a related one picked)
  suggestions: [],
};

let t = makeT(state.lang || 'hi');

const DEMO_USERS = [
  { username: 'sita', name: { hi: 'सीता', en: 'Sita', ta: 'சீதா', te: 'సీత' }, color: '#0A6152' },
  { username: 'ramesh', name: { hi: 'रमेश', en: 'Ramesh', ta: 'ரமேஷ்', te: 'రమేష్' }, color: '#B4610F' },
  { username: 'lakshmi', name: { hi: 'लक्ष्मी', en: 'Lakshmi', ta: 'லட்சுமி', te: 'లక్ష్మి' }, color: '#5B3FA3' },
];
const DEMO_PASSWORD = 'demo1234';
const PALETTE = ['#0A6152', '#B4610F', '#5B3FA3', '#1F7A45', '#B3261E', '#1D4E8A'];

// Every function, named twice: a two-word label and a sentence saying what it
// does. The person this is for may not know what "schemes" means; "find
// schemes you qualify for" tells them.
const NAV = [
  { view: 'overview', icon: 'grid',   tone: 'var(--primary)',     label: 'navOverview', sub: 'navOverviewSub' },
  { view: 'balance',  icon: 'wallet', tone: 'var(--tone-money)',  label: 'navBalance',  sub: 'tileBalanceSub' },
  { view: 'send',     icon: 'send',   tone: 'var(--tone-send)',   label: 'navSend',     sub: 'tileSendSub' },
  { view: 'schemes',  icon: 'scheme', tone: 'var(--tone-scheme)', label: 'navSchemes',  sub: 'tileSchemesSub' },
  { view: 'learn',    icon: 'learn',  tone: 'var(--tone-learn)',  label: 'navLearn',    sub: 'tileLearnSub' },
  { view: 'scan',     icon: 'scan',   tone: 'var(--tone-scan)',   label: 'navScan',     sub: 'tileScanSub' },
  { view: 'safety',   icon: 'shield', tone: 'var(--tone-safety)', label: 'navSafety',   sub: 'tileSafetySub' },
  { sep: true },
  { view: 'profile',  icon: 'user',   tone: 'var(--primary)',     label: 'navProfile',  sub: 'navProfileSub' },
  { view: 'help',     icon: 'help',   tone: 'var(--primary)',     label: 'navHelp',     sub: 'navHelpSub' },
];
const VIEWS = NAV.filter((n) => n.view).map((n) => n.view);

// The dialog layer names screens from the old single-column app; map them.
const SCREEN_TO_VIEW = { home: 'overview', history: 'balance' };

// ─────────────────────────────────────────────────────────── api
async function api(path, { method = 'GET', body = null, form = null } = {}) {
  const headers = {};
  if (!form) headers['Content-Type'] = 'application/json';
  if (state.token) headers.Authorization = `Token ${state.token}`;
  const res = await fetch(path, { method, headers, body: form || (body ? JSON.stringify(body) : null) });
  if (res.status === 401 && state.token) { signOut(); throw new Error('unauthorised'); }
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
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
  const u = new SpeechSynthesisUtterance(text);
  u.lang = tag;
  // Exact regional voice, then any voice for the language, then the default:
  // a default voice mispronounces Indic text but still reads the digits.
  const base = tag.split('-')[0];
  u.voice = voices.find((v) => v.lang === tag) || voices.find((v) => v.lang?.startsWith(base)) || null;
  u.rate = 0.92;   // slightly slow: these are unfamiliar financial terms
  window.speechSynthesis.speak(u);
}

// ─────────────────────────────────────────────────────────── speech in
const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;
let listening = false;

function startListening() {
  if (!Recognition) { toast(t('noMic')); $('#ask-input').focus(); return; }
  if (listening) { recognition?.stop(); return; }
  recognition = new Recognition();
  recognition.lang = LANG_META[state.lang]?.speech || 'hi-IN';
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;
  let finalText = '';
  const mic = $('#mic');
  const input = $('#ask-input');
  recognition.onstart = () => { listening = true; mic.classList.add('listening'); input.placeholder = t('listening'); };
  recognition.onresult = (event) => {
    let interim = '';
    for (const r of event.results) { if (r.isFinal) finalText += r[0].transcript; else interim += r[0].transcript; }
    input.value = finalText || interim;
  };
  const done = () => { listening = false; mic.classList.remove('listening'); input.placeholder = t('askPlaceholder'); };
  recognition.onerror = (event) => {
    done();
    if (event.error === 'not-allowed' || event.error === 'service-not-allowed') { toast(t('micDenied')); input.focus(); }
  };
  recognition.onend = () => {
    done();
    const said = finalText.trim();
    if (said) { input.value = ''; sendUtterance(said); }
  };
  recognition.start();
}

// ─────────────────────────────────────────────────────────── answer panel
function showReply(said, reply, { low = false, icon = 'chat' } = {}) {
  const box = $('#reply');
  box.hidden = false;
  box.classList.toggle('low', low);
  setIcon($('#reply-icon'), icon && iconSvg(icon) ? icon : 'chat');
  $('#reply-you').textContent = said ? `${t('youSaid')}: “${said}”` : '';
  $('#reply-text').textContent = reply || '';
  box.dataset.speak = reply || '';
}
function hideReply() { $('#reply').hidden = true; }

// ─────────────────────────────────────────────────────────── dialog turn
async function sendUtterance(text) {
  if (!state.token) return;
  const mic = $('#mic');
  mic.classList.add('busy');
  showReply(text, t('thinking'));
  try {
    const result = await api('/api/voice/text/', {
      method: 'POST', body: { text, language: state.lang, pending: state.pending },
    });
    handleDialogResult(text, result);
  } catch (err) {
    console.error(err);
    showReply(text, t('networkError'), { low: true, icon: 'wifiOff' });
  } finally {
    mic.classList.remove('busy');
  }
}

function handleDialogResult(said, result) {
  showReply(said, result.reply_text, { low: result.low_confidence, icon: result.icon });
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

  const slots = result.slots || {};
  if (['transfer_executed', 'transfer_replayed'].includes(result.action_taken)) refreshAccount();

  // Carry what the dialog found onto the screen it opens, so the spoken answer
  // and the visible one are the same answer.
  if (result.action_taken === 'scheme_search' && Array.isArray(slots.schemes)) {
    showSchemeSearch(said, slots.schemes);
  }
  if (slots.lesson_id) { state.lessonSelected = slots.lesson_id; state.quiz = null; }
  if (slots.scam) { state.scamVerdict = slots.scam; $('#scam-input').value = said; loadChecks(); }
  if (slots.ask) {
    state.askResult = slots.ask;
    state.askShown = slots.ask.best;
    state.scamVerdict = null;
    $('#scam-input').value = said;
  }
  if (slots.open === 'report') state.reportKind = null;
  if (slots.payee && result.action_taken === 'ask_amount') {
    const c = state.contacts.find((x) => x.vpa === slots.payee.vpa);
    if (c) state.draft = { payee: c, amount: '' };
  }

  const view = SCREEN_TO_VIEW[result.screen] || result.screen;
  if (view && VIEWS.includes(view)) go(view);
  else if (view === undefined || view === null) renderView();
}

// ─────────────────────────────────────────────────────────── confirmation
function openConfirm(text) {
  $('#confirm-text').textContent = text;
  $('#confirm-sheet').hidden = false;
  $('#btn-yes').focus();
}
function closeConfirm() { $('#confirm-sheet').hidden = true; }

async function confirmPending() {
  const pending = state.pending;
  if (!pending) { closeConfirm(); return; }
  closeConfirm();
  if (!navigator.onLine) { await enqueue(pending); return; }
  try {
    const result = await api('/api/voice/confirm/', { method: 'POST', body: { pending, language: state.lang } });
    state.pending = null;
    state.draft = { payee: null, amount: '' };
    showReply(t('yes'), result.reply_text, { icon: 'check' });
    speak(result.reply_text);
    await refreshAccount();
    go('balance');
  } catch (err) {
    console.error(err);
    // A failure between confirm and response is exactly what the idempotency
    // key is for: queue it, and replay cannot pay twice.
    if (!err.status) await enqueue(pending);
    else showReply(t('yes'), t('errGeneric'), { low: true, icon: 'alert' });
  }
}

function cancelPending() {
  state.pending = null;
  closeConfirm();
  const msg = { hi: 'ठीक है, रद्द कर दिया। कोई पैसा नहीं गया।', en: 'Cancelled. No money was sent.',
                ta: 'ரத்து செய்யப்பட்டது. பணம் அனுப்பப்படவில்லை.', te: 'రద్దు చేశాను. డబ్బు పంపలేదు.' }[state.lang];
  showReply(t('no'), msg, { icon: 'close' });
  speak(msg);
}

// ─────────────────────────────────────────────────────────── offline queue
async function enqueue(pending) {
  await queuePut({ pending, language: state.lang, queued_at: Date.now() });
  state.pending = null;
  await refreshQueueCount();
  const msg = { hi: 'नेटवर्क नहीं है। जुड़ते ही यह काम एक ही बार भेजा जाएगा।',
                en: 'No network. This will be sent exactly once when you reconnect.',
                ta: 'இணைப்பு இல்லை. இணைந்ததும் இது ஒருமுறை மட்டும் அனுப்பப்படும்.',
                te: 'నెట్‌వర్క్ లేదు. కనెక్ట్ అయ్యాక ఇది ఒక్కసారే పంపబడుతుంది.' }[state.lang];
  showReply('', msg, { low: true, icon: 'wifiOff' });
  speak(msg);
}

async function refreshQueueCount() {
  state.queueCount = (await queueAll()).length;
  renderStatus();
  renderNav();
}

async function drainQueue() {
  if (!navigator.onLine || !state.token) return;
  const items = await queueAll();
  if (!items.length) return;
  try {
    const res = await api('/api/sync/replay/', { method: 'POST', body: { items } });
    // Every item got a definite answer (executed, replayed, or failed for a
    // reason replay will not fix), so all of them leave the queue.
    await queueDelete(res.results.map((r) => r.idempotency_key));
    const done = res.executed + res.replayed;
    if (done) toast(t('synced', { n: done }));
    const failed = res.results.find((r) => r.status === 'failed');
    if (failed) showReply('', failed.reply_text, { low: true, icon: 'alert' });
  } catch (err) {
    console.warn('replay failed; queue kept', err);
  }
  await refreshQueueCount();
  await refreshAccount();
}

function renderStatus() {
  const pill = $('#status-pill');
  const offline = !navigator.onLine;
  pill.classList.toggle('offline', offline);
  pill.classList.toggle('queued', !offline && state.queueCount > 0);
  $('#status-text').textContent = state.queueCount
    ? t('queuedTitle', { n: state.queueCount })
    : offline ? t('offlineShort') : t('online');
}

// ─────────────────────────────────────────────────────────── auth
async function signIn(username, password) {
  const data = await api('/api/accounts/login/', { method: 'POST', body: { username, password } });
  state.token = data.token;
  state.user = data.user;
  store.set('token', state.token);
  store.set('user', state.user);
  if (data.profile?.language && LANGS.includes(data.profile.language) && !store.get('langChosen')) {
    setLanguage(data.profile.language, { silent: true });
  }
  await enterApp();
}

function signOut() {
  Object.assign(state, {
    token: null, user: null, account: null, contacts: [], transactions: [], profile: null,
    pending: null, schemes: null, lessons: null, checks: [], scamVerdict: null, scanResult: null,
    schemeSearch: null, schemeSelected: null, lessonSelected: null, quiz: null,
  });
  ['token', 'user', 'account', 'accountAt', 'contacts', 'profile', 'transactions'].forEach(store.del);
  closeCamera();
  closeDrawer();
  hideReply();
  showAuth('auth');
}

async function enterApp() {
  $('#auth-shell').hidden = true;
  $('#app-shell').hidden = false;
  renderNav();
  const fromHash = location.hash.replace('#/', '');
  go(VIEWS.includes(fromHash) ? fromHash : 'overview', { replace: true });
  await Promise.all([refreshAccount(), loadSchemes(), loadLessons(), loadSuggestions()]);
  await refreshQueueCount();
  drainQueue();
}

async function refreshAccount() {
  if (!state.token) return;
  try {
    const me = await api('/api/accounts/me/');
    state.account = me.account;
    state.contacts = me.contacts || [];
    state.profile = me.profile || null;
    state.user = me.user || state.user;
    state.accountAt = Date.now();
    ['account', 'accountAt', 'contacts', 'profile', 'user'].forEach((k) => store.set(k, state[k]));
  } catch { /* offline: keep the cached figure, stamped with its age */ }
  try {
    const txns = await api('/api/banking/transactions/?limit=30');
    state.transactions = txns.results || [];
    store.set('transactions', state.transactions);
  } catch { /* offline */ }
  renderShellUser();
  renderView();
}

async function loadSchemes() {
  const key = `schemes.${state.lang}`;
  try {
    state.schemes = await api(`/api/schemes/?lang=${state.lang}`);
    store.set(key, state.schemes);
  } catch { state.schemes = store.get(key, state.schemes); }
  if (state.schemeSearch) await refreshSchemeSearch();
  renderView();
}

async function loadLessons() {
  const key = `lessons.${state.lang}`;
  try {
    state.lessons = await api(`/api/literacy/lessons/?lang=${state.lang}`);
    store.set(key, state.lessons);
  } catch { state.lessons = store.get(key, state.lessons); }
  renderView();
}

async function loadChecks() {
  try { state.checks = (await api('/api/fraud/history/')).results || []; } catch { /* offline */ }
  if (state.view === 'safety') renderSafety();
}

// ─────────────────────────────────────────────────────────── signup + OTP
// Three screens: pick a contact, enter the code, choose a name and password.
// The server keeps no "half signed up" session -- a correct code buys a signed
// verification token the client holds and presents at registration, so web
// replicas stay interchangeable.
//
// SAFETY: no SMS gateway or email provider is wired up. The code is printed to
// the server log and, in DEBUG, echoed by the API; the screen says so.

const OTP_ERRORS = {
  bad_phone: 'errBadPhone', bad_email: 'errBadEmail', bad_channel: 'errGeneric',
  already_registered: 'errAlreadyRegistered', cooldown: 'errCooldown', too_many: 'errTooMany',
  wrong_code: 'errWrongCode', expired: 'errExpired', already_used: 'errExpired', locked: 'errLocked',
  not_found: 'errNotFound', verification_expired: 'errVerificationExpired', verification_invalid: 'errNotFound',
};

function otpMessage(err) {
  const data = err?.data || {};
  if (data.error === 'wrong_code' && Number.isFinite(data.attempts_remaining)) {
    return t('errWrongCodeLeft', { n: data.attempts_remaining });
  }
  const key = OTP_ERRORS[data.error];
  if (key === 'errCooldown') return t('errCooldown', { n: data.retry_after ?? 30 });
  if (key) return t(key);
  if (!err?.status) return t('networkError');
  return data.detail || t('errGeneric');
}

function startSignup() {
  state.signup = { channel: 'phone', destination: '', challengeId: null, verificationToken: null,
                   expiresAt: 0, resendAt: 0, devCode: null };
  showAuth('signup');
}

function renderSignup() {
  const s = state.signup;
  if (!s) { showAuth('auth'); return; }
  const phone = s.channel === 'phone';
  $$('.seg-btn').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.channel === s.channel)));
  $('#dest-label').textContent = t(phone ? 'phoneLabel' : 'emailLabel');
  $('#dest-hint').textContent = t(phone ? 'phoneHint' : 'emailHint');
  const input = $('#dest-input');
  input.value = s.destination;
  input.placeholder = t(phone ? 'phonePlaceholder' : 'emailPlaceholder');
  input.type = phone ? 'tel' : 'email';
  input.inputMode = phone ? 'numeric' : 'email';
  input.autocomplete = phone ? 'tel' : 'email';
  input.maxLength = phone ? 15 : 254;
  $('#dest-error').hidden = true;
}

async function requestCode({ resend = false } = {}) {
  const s = state.signup;
  const destination = resend ? s.destination : $('#dest-input').value.trim();
  const errorBox = resend ? $('#otp-error') : $('#dest-error');
  if (!destination) return;
  s.destination = destination;
  errorBox.hidden = true;
  const button = resend ? $('#btn-resend') : $('#signup-form button[type="submit"]');
  button.disabled = true;
  try {
    const data = await api('/api/accounts/otp/request/', { method: 'POST', body: { channel: s.channel, destination } });
    s.challengeId = data.challenge_id;
    s.masked = data.destination_masked;
    s.expiresAt = Date.now() + (data.expires_in ?? 300) * 1000;
    s.resendAt = Date.now() + (data.resend_in ?? 30) * 1000;
    s.devCode = data.dev_code ?? null;
    if (resend) { renderOtp(); toast(t('sendCode')); } else showAuth('otp');
  } catch (err) {
    errorBox.textContent = otpMessage(err);
    errorBox.hidden = false;
    speak(errorBox.textContent);
    if (err?.data?.error === 'already_registered') setTimeout(() => showAuth('auth'), 2200);
  } finally {
    button.disabled = false;
  }
}

let otpTimer = null;
function stopOtpTimer() { clearInterval(otpTimer); otpTimer = null; }

function renderOtp() {
  const s = state.signup;
  if (!s?.challengeId) { showAuth('signup'); return; }
  setIcon($('#otp-icon'), s.channel === 'phone' ? 'phone' : 'mail');
  $('#otp-destination').textContent = s.masked || s.destination;
  $('#otp-error').hidden = true;
  const grid = $('#otp-grid');
  grid.innerHTML = '';
  const boxes = [];
  for (let i = 0; i < 6; i += 1) {
    const box = document.createElement('input');
    box.className = 'otp-box';
    box.inputMode = 'numeric';
    box.maxLength = 1;
    box.setAttribute('aria-label', `${i + 1}`);
    if (i === 0) box.autocomplete = 'one-time-code';
    boxes.push(box);
    grid.append(box);
  }
  const focusFirstEmpty = () => (boxes.find((b) => !b.value) || boxes[5]).focus();
  boxes.forEach((box, i) => {
    box.addEventListener('input', () => {
      box.value = box.value.replace(/\D/g, '').slice(-1);
      box.classList.toggle('filled', Boolean(box.value));
      if (box.value && i < 5) boxes[i + 1].focus();
      if (boxes.every((b) => b.value)) verifyCode();
    });
    box.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !box.value && i > 0) {
        boxes[i - 1].value = ''; boxes[i - 1].classList.remove('filled'); boxes[i - 1].focus(); e.preventDefault();
      }
      if (e.key === 'ArrowLeft' && i > 0) boxes[i - 1].focus();
      if (e.key === 'ArrowRight' && i < 5) boxes[i + 1].focus();
    });
    box.addEventListener('paste', (e) => {
      const digits = (e.clipboardData?.getData('text') || '').replace(/\D/g, '').slice(0, 6);
      if (!digits) return;
      e.preventDefault();
      digits.split('').forEach((d, k) => { boxes[k].value = d; boxes[k].classList.add('filled'); });
      focusFirstEmpty();
      if (boxes.every((b) => b.value)) verifyCode();
    });
  });
  $('#dev-code').hidden = !s.devCode;
  if (s.devCode) $('#dev-code-value').textContent = s.devCode;
  stopOtpTimer();
  tickOtp();
  otpTimer = setInterval(tickOtp, 1000);
  boxes[0].focus();
}

function tickOtp() {
  const s = state.signup;
  if (!s) { stopOtpTimer(); return; }
  const left = Math.max(0, Math.round((s.expiresAt - Date.now()) / 1000));
  const clock = `${Math.floor(left / 60)}:${String(left % 60).padStart(2, '0')}`;
  $('#otp-countdown').textContent = left > 0 ? t('expiresIn', { time: clock }) : t('codeExpired');
  const cooling = Math.max(0, Math.ceil((s.resendAt - Date.now()) / 1000));
  const resend = $('#btn-resend');
  resend.disabled = cooling > 0;
  resend.textContent = cooling > 0 ? t('resendIn', { n: cooling }) : t('resendCode');
  if (left === 0) $('#btn-verify').disabled = true;
}

let verifying = false;
async function verifyCode() {
  const s = state.signup;
  if (!s?.challengeId || verifying) return;
  const boxes = $$('.otp-box');
  const code = boxes.map((b) => b.value).join('');
  if (code.length < 6) { $('#otp-error').textContent = t('errWrongCode'); $('#otp-error').hidden = false; return; }
  verifying = true;
  $('#btn-verify').disabled = true;
  try {
    const data = await api('/api/accounts/otp/verify/', { method: 'POST', body: { challenge_id: s.challengeId, code } });
    s.verificationToken = data.verification_token;
    stopOtpTimer();
    showAuth('details');
  } catch (err) {
    const message = otpMessage(err);
    $('#otp-error').textContent = message;
    $('#otp-error').hidden = false;
    speak(message);
    const grid = $('#otp-grid');
    grid.classList.remove('shake'); void grid.offsetWidth; grid.classList.add('shake');
    boxes.forEach((b) => { b.value = ''; b.classList.remove('filled'); });
    boxes[0].focus();
  } finally {
    verifying = false;
    $('#btn-verify').disabled = false;
  }
}

async function completeRegistration(event) {
  event.preventDefault();
  const s = state.signup;
  const errorBox = $('#details-error');
  errorBox.hidden = true;
  if (!s?.verificationToken) { showAuth('signup'); return; }
  const name = $('#reg-name').value.trim();
  const password = $('#reg-password').value;
  if (!name || password.length < 4) return;
  const button = $('#details-form button[type="submit"]');
  button.disabled = true;
  try {
    const data = await api('/api/accounts/register/', {
      method: 'POST',
      body: { verification_token: s.verificationToken, display_name: name, password, language: state.lang },
    });
    state.token = data.token;
    state.user = data.user;
    store.set('token', state.token);
    store.set('user', state.user);
    state.signup = null;
    await enterApp();
    const greeting = t('welcome', { name });
    toast(greeting);
    speak(greeting);
  } catch (err) {
    errorBox.textContent = otpMessage(err);
    errorBox.hidden = false;
  } finally {
    button.disabled = false;
  }
}

// ─────────────────────────────────────────────────────────── navigation
function showAuth(screen) {
  state.authScreen = screen;
  document.title = `${t('appName')} · Gramin Vaani Saathi`;
  $('#app-shell').hidden = true;
  $('#auth-shell').hidden = false;
  $$('.auth-screen').forEach((el) => { el.hidden = el.dataset.screen !== screen; });
  if (screen !== 'otp') stopOtpTimer();
  if (screen === 'auth') renderAuth();
  if (screen === 'signup') renderSignup();
  if (screen === 'otp') renderOtp();
  if (screen === 'details') { $('#details-error').hidden = true; $('#reg-name').focus(); }
  $$('.lang-card').forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.lang === state.lang)));
  $$('.lang-current').forEach((el) => { el.textContent = LANG_META[state.lang]?.native || ''; });
}

function go(view, { replace = false } = {}) {
  if (!VIEWS.includes(view)) view = 'overview';
  if (state.view === 'scan' && view !== 'scan') closeCamera();
  state.view = view;
  const hash = `#/${view}`;
  if (location.hash !== hash) {
    if (replace) history.replaceState(null, '', hash); else history.pushState(null, '', hash);
  }
  $$('.view').forEach((el) => { el.hidden = el.dataset.view !== view; });
  closeDrawer();
  renderNav();
  renderTitle();
  renderView();
  $('#content').scrollTop = 0;
  if (view === 'safety') loadChecks();
}

function openDrawer() { $('#sidebar').classList.add('open'); $('#scrim').hidden = false; }
function closeDrawer() { $('#sidebar').classList.remove('open'); $('#scrim').hidden = true; }

// ─────────────────────────────────────────────────────────── language
function setLanguage(lang, { silent = false } = {}) {
  if (!LANGS.includes(lang)) return;
  const changed = lang !== state.lang;
  state.lang = lang;
  store.set('lang', lang);
  t = makeT(lang);
  document.documentElement.lang = lang;
  applyStrings();
  if (!silent) speak(LANG_META[lang].native, lang);
  if (state.token && changed) {
    // Scheme names, reasons and lessons come from the server in one language;
    // fetch them again (cached copies per language make this instant offline).
    // Results the server phrased in the old language would sit beside chrome in
    // the new one. Drop them rather than show two scripts in one card.
    state.scamVerdict = null;
    state.scanResult = null;
    state.reportSteps = null;
    state.reportKind = null;
    state.askResult = null;
    state.askShown = null;
    hideReply();
    state.schemes = store.get(`schemes.${lang}`, null);
    state.lessons = store.get(`lessons.${lang}`, null);
    loadSchemes();
    loadLessons();
    loadSuggestions();
    api('/api/accounts/profile/', { method: 'PATCH', body: { language: lang } }).catch(() => {});
  }
  if (!$('#app-shell').hidden) { renderNav(); renderTitle(); renderShellUser(); renderView(); }
  else showAuth(state.authScreen);
}

function applyStrings() {
  $$('[data-i18n]').forEach((el) => { el.textContent = t(el.dataset.i18n); });
  $$('[data-i18n-ph]').forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
  $$('[data-setlang]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.setlang === state.lang)));
  renderStatus();
}

// ─────────────────────────────────────────────────────────── shell
function renderNav() {
  const nav = $('#side-nav');
  nav.innerHTML = '';
  for (const item of NAV) {
    if (item.sep) { nav.append(Object.assign(document.createElement('div'), { className: 'nav-sep' })); continue; }
    const b = document.createElement('button');
    b.className = 'nav-item';
    b.style.setProperty('--tone', item.tone);
    if (item.view === state.view) b.setAttribute('aria-current', 'page');
    b.innerHTML = `<span class="nav-icon">${iconSvg(item.icon)}</span>
      <span class="nav-text"><span class="nav-label"></span><span class="nav-sub"></span></span>`;
    $('.nav-label', b).textContent = t(item.label);
    $('.nav-sub', b).textContent = t(item.sub);
    if (item.view === 'schemes' && state.schemes?.summary?.eligible) {
      b.insertAdjacentHTML('beforeend', `<span class="nav-badge">${state.schemes.summary.eligible}</span>`);
    }
    // A hand-picked section means the last spoken answer is about something
    // else now; leaving it on top of the new view reads as stale.
    b.addEventListener('click', () => { hideReply(); go(item.view); });
    nav.append(b);
  }
}

function renderTitle() {
  const item = NAV.find((n) => n.view === state.view);
  const title = state.view === 'overview' ? t('overviewTitle', { name: displayName() }) : t(item.label);
  const sub = state.view === 'overview' ? t('overviewSub') : t(item.sub);
  $('#view-title').textContent = title;
  $('#view-sub').textContent = sub;
  document.title = `${title} · ${t('appName')}`;
}

function displayName() {
  const demo = DEMO_USERS.find((u) => u.username === state.user?.username);
  return demo ? demo.name[state.lang] : (state.user?.first_name || state.user?.username || '');
}

function renderShellUser() {
  const name = displayName();
  $('#side-user-name').textContent = name;
  $('#side-user-vpa').textContent = state.account?.vpa || '';
  $('#side-avatar').textContent = name.slice(0, 1).toUpperCase();
  if (state.view === 'overview') renderTitle();
}

function renderView() {
  if ($('#app-shell').hidden) return;
  renderBalanceFigures();
  switch (state.view) {
    case 'overview': renderOverview(); break;
    case 'balance': renderBalance(); break;
    case 'send': renderSend(); break;
    case 'schemes': renderSchemes(); break;
    case 'learn': renderLearn(); break;
    case 'scan': renderScan(); break;
    case 'safety': renderSafety(); break;
    case 'help': renderHelp(); break;
    case 'profile': renderProfile(); break;
    default: break;
  }
}

// ─────────────────────────────────────────────────────────── shared bits
function money(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  return n.toLocaleString('en-IN', { maximumFractionDigits: n % 1 ? 2 : 0 });
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function iconSpan(name, className = '') {
  const s = el('span', className);
  s.innerHTML = iconSvg(name);
  return s;
}

function avatar(name, i) {
  const a = el('span', 'avatar', (name || '?').slice(0, 1));
  a.style.background = PALETTE[i % PALETTE.length];
  return a;
}

// Names in the user's script. The seed stores one local-script name per
// contact, in the *owner's* language -- so a Hindi speaker's contacts carry
// Devanagari names, which would be wrong on screen in Tamil or English. The
// demo people are known in all four scripts; anyone else gets their local
// name only when it is in the script being displayed, otherwise the Latin one.
const KNOWN_NAMES = {
  ...Object.fromEntries(DEMO_USERS.map((u) => [`${u.username}@sandbox`, u.name])),
  'ramkirana@sandbox': { hi: 'राम किराना स्टोर', en: 'Ram Kirana Store', ta: 'ராம் கிரானா ஸ்டோர்', te: 'రామ్ కిరాణా స్టోర్' },
};
const SCRIPT = { hi: /[ऀ-ॿ]/, ta: /[஀-௿]/, te: /[ఀ-౿]/, en: /^[ -]*$/ };

function contactName(c) {
  if (!c) return '';
  const known = KNOWN_NAMES[c.vpa];
  if (known) return known[state.lang];
  if (c.name_local && SCRIPT[state.lang]?.test(c.name_local)) return c.name_local;
  return c.name || c.name_local || c.vpa || '';
}

function renderBalanceFigures() {
  const amount = state.account ? money(state.account.balance) : '—';
  $$('.bal-amount').forEach((n) => { n.textContent = amount; });
  $$('.bal-vpa').forEach((n) => { n.textContent = state.account ? `${state.account.vpa} · ${state.account.bank_name}` : ''; });
  // Never present a cached figure as live. The stamp is the honesty guarantee.
  const stale = state.accountAt && !navigator.onLine;
  const stamp = stale ? t('asOf', { time: new Date(state.accountAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) }) : '';
  $$('.bal-stamp').forEach((n) => { n.textContent = stamp; });
}

function speakBalance() {
  speak(`${t('balanceLabel')}: ${state.account ? money(state.account.balance) : '—'} ₹`);
}

function txnRow(txn) {
  const out = txn.direction === 'debit';
  const row = el('li', 'txn' + (txn.status === 'failed' ? ' failed' : ''));
  row.innerHTML = `<span class="txn-arrow ${out ? 'out' : 'in'}">${iconSvg(out ? 'arrowOut' : 'arrowIn')}</span>
    <span class="txn-body"><span class="txn-who"></span><span class="txn-when"></span></span>
    <span class="txn-amt ${out ? '' : 'in'}"></span>`;
  // The ledger stores Latin names; show the one in the user's script when known.
  const known = state.contacts.find((c) => c.vpa === txn.counterparty_vpa);
  $('.txn-who', row).textContent = known ? contactName(known) : (txn.counterparty_name || txn.counterparty_vpa || '—');
  $('.txn-when', row).textContent = new Date(txn.created_at).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  $('.txn-amt', row).textContent = `${out ? '−' : '+'}₹${money(txn.amount)}`;
  if (txn.status === 'failed') $('.txn-when', row).append(el('span', 'txn-failed-tag', ` · ${txn.failure_reason || 'failed'}`));
  return row;
}

const VERDICT = {
  eligible: { key: 'verdictEligible', icon: 'check', cls: 'lvl-eligible' },
  maybe: { key: 'verdictMaybe', icon: 'question', cls: 'lvl-maybe' },
  not_eligible: { key: 'verdictNot', icon: 'minus', cls: 'lvl-not_eligible' },
};
function verdictBadge(verdict) {
  const v = VERDICT[verdict] || VERDICT.maybe;
  const b = el('span', `badge ${v.cls}`);
  b.innerHTML = iconSvg(v.icon);
  b.append(document.createTextNode(t(v.key)));
  return b;
}

// ─────────────────────────────────────────────────────────── overview
function renderOverview() {
  // quick send
  const row = $('#ov-contacts');
  row.innerHTML = '';
  state.contacts.slice(0, 5).forEach((c, i) => {
    const b = el('button', 'avatar-btn');
    b.setAttribute('aria-pressed', String(state.draft.payee?.vpa === c.vpa));
    b.append(avatar(contactName(c), i), el('span', '', contactName(c)));
    b.addEventListener('click', () => { state.draft = { payee: c, amount: state.draft.amount }; speak(contactName(c)); go('send'); });
    row.append(b);
  });
  const chips = $('#ov-amounts');
  chips.innerHTML = '';
  for (const v of [100, 200, 500, 1000]) {
    const c = el('button', 'chip', `₹${v}`);
    c.addEventListener('click', () => { state.draft.amount = String(v); go('send'); });
    chips.append(c);
  }

  // activity
  const list = $('#ov-txns');
  list.innerHTML = '';
  if (!state.transactions.length) list.append(el('li', 'txn-empty', t('noTxns')));
  state.transactions.slice(0, 5).forEach((x) => list.append(txnRow(x)));

  // schemes
  const s = state.schemes;
  $('#ov-scheme-count').textContent = s ? s.summary.eligible : '—';
  $('#ov-scheme-text').textContent = s ? t('schemesQualify', { n: s.summary.eligible }).replace(/^\d+\s*/, '') : '';
  // A new profile qualifies for little and is "maybe" for most: say so, so a
  // low number reads as "tell us more" rather than "nothing for you".
  const maybe = $('#ov-scheme-maybe');
  maybe.hidden = !s?.summary.maybe;
  if (s?.summary.maybe) maybe.textContent = t('schemesNeedInfo', { n: s.summary.maybe });
  const ml = $('#ov-schemes');
  ml.innerHTML = '';
  (s?.results || []).filter((r) => r.verdict !== 'not_eligible').slice(0, 3).forEach((r) => {
    const li = el('li');
    const b = el('button');
    const ic = el('span', 'item-icon');
    ic.style.cssText = `--tone:${r.tone};width:30px;height:30px;border-radius:9px`;
    ic.innerHTML = iconSvg(r.icon) || iconSvg('scheme');
    // Icon-only verdict here: the card is narrow, and a full badge leaves the
    // scheme name -- the part people actually read -- cut to a few letters.
    const mark = verdictBadge(r.verdict);
    mark.classList.add('compact');
    mark.title = mark.textContent;
    mark.setAttribute('aria-label', mark.textContent);
    b.append(ic, el('span', 'mini-name', r.name), mark);
    b.addEventListener('click', () => { state.schemeSelected = r.scheme_id; go('schemes'); });
    li.append(b);
    ml.append(li);
  });

  // learn
  const L = state.lessons;
  const done = L?.completed ?? 0;
  const total = L?.total ?? 8;
  $('#ov-ring').style.strokeDashoffset = String(113.1 * (1 - done / Math.max(total, 1)));
  $('#ov-ring-label').textContent = `${done}/${total}`;
  const next = L?.results?.find((x) => !x.progress.completed);
  const nb = $('#ov-next-lesson');
  nb.textContent = next ? `${t('nextLesson')}: ${next.title}` : t('allLessonsDone');
  nb.onclick = () => { if (next) { state.lessonSelected = next.id; state.quiz = null; } go('learn'); };

  // safety mini verdict
  const mv = $('#ov-scam-result');
  const v = state.scamVerdict;
  mv.hidden = !v;
  if (v) {
    mv.className = `mini-verdict lvl-${v.label}`;
    mv.innerHTML = iconSvg(v.label === 'safe' ? 'check' : 'warning');
    mv.append(el('span', '', `${v.headline}. ${v.reasons[0] || ''}`));
  }
}

// ─────────────────────────────────────────────────────────── balance
function renderBalance() {
  const sum = (dir) => state.transactions.filter((x) => x.direction === dir && x.status !== 'failed')
    .reduce((a, x) => a + Number(x.amount), 0);
  $('#bal-in').textContent = `+₹${money(sum('credit'))}`;
  $('#bal-out').textContent = `−₹${money(sum('debit'))}`;
  $$('#txn-filter button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.f === state.txnFilter)));
  const list = $('#txn-list');
  list.innerHTML = '';
  const rows = state.transactions.filter((x) => state.txnFilter === 'all' || x.direction === state.txnFilter);
  if (!rows.length) list.append(el('li', 'txn-empty', t('noTxns')));
  rows.forEach((x) => list.append(txnRow(x)));
}

// ─────────────────────────────────────────────────────────── send
function renderSend() {
  const list = $('#contact-list');
  list.innerHTML = '';
  state.contacts.forEach((c, i) => {
    const b = el('button', 'contact');
    b.setAttribute('aria-pressed', String(state.draft.payee?.vpa === c.vpa));
    const txt = el('span');
    txt.append(el('div', 'contact-name', contactName(c)), el('div', 'contact-vpa', c.vpa));
    b.append(avatar(contactName(c), i), txt);
    b.addEventListener('click', () => { state.draft.payee = c; speak(contactName(c)); renderSend(); });
    list.append(b);
  });

  $('#amount-value').textContent = money(state.draft.amount || 0);
  const quick = $('#quick-amounts');
  quick.innerHTML = '';
  for (const v of [100, 200, 500, 1000]) {
    const c = el('button', 'chip', `₹${v}`);
    c.setAttribute('aria-pressed', String(state.draft.amount === String(v)));
    c.addEventListener('click', () => { state.draft.amount = String(v); renderSend(); });
    quick.append(c);
  }
  const keypad = $('#keypad');
  if (!keypad.childElementCount) {
    for (const key of ['1', '2', '3', '4', '5', '6', '7', '8', '9', '00', '0', '⌫']) {
      const b = el('button', 'key', key);
      b.addEventListener('click', () => {
        if (key === '⌫') state.draft.amount = state.draft.amount.slice(0, -1);
        else if (state.draft.amount.length < 6 && !(state.draft.amount === '' && key.startsWith('0'))) state.draft.amount += key;
        renderSend();
      });
      keypad.append(b);
    }
  }
  const payee = state.draft.payee;
  const value = Number(state.draft.amount);
  $('#review-payee').textContent = payee ? contactName(payee) : t('pickContactFirst');
  $('#review-amount').textContent = value ? `₹${money(value)}` : '—';
  $('#btn-review').disabled = !payee || !value;
}

function reviewTransfer() {
  const { payee, amount } = state.draft;
  const value = Number(amount);
  if (!payee || !Number.isFinite(value) || value < 1) return;
  const name = contactName(payee);
  // Minted before the network is involved, so the action keeps its identity
  // whether it is sent now or replayed from the queue tomorrow.
  state.pending = { action: 'send_money', amount: String(value), payee_vpa: payee.vpa, payee_name: name,
                    idempotency_key: `tap-${crypto.randomUUID()}` };
  const question = { hi: `${name} को ${value} रुपये भेजें?`, en: `Send ${value} rupees to ${name}?`,
                     ta: `${name} க்கு ${value} ரூபாய் அனுப்பவா?`, te: `${name} కి ${value} రూపాయలు పంపాలా?` }[state.lang];
  openConfirm(question);
  speak(question);
}

// ─────────────────────────────────────────────────────────── schemes
async function showSchemeSearch(query, ids = null) {
  state.schemeSearch = { query, ids };
  $('#scheme-q').value = query;
  await refreshSchemeSearch();
  if (state.view === 'schemes') renderSchemes();
}

async function refreshSchemeSearch() {
  const s = state.schemeSearch;
  if (!s) return;
  try {
    const data = await api(`/api/schemes/search/?q=${encodeURIComponent(s.query)}&lang=${state.lang}&k=5`);
    s.results = data.results;
  } catch {
    // Offline: fall back to the ids the dialog already found, from the cache.
    s.results = (s.ids || []).map((id) => state.schemes?.results.find((r) => r.scheme_id === id)).filter(Boolean);
  }
  if (s.results?.length && !state.schemeSelected) state.schemeSelected = s.results[0].scheme_id;
}

function renderSchemes() {
  const all = state.schemes?.results || [];
  const searching = Boolean(state.schemeSearch?.results);
  const source = searching ? state.schemeSearch.results : all;
  const rows = source.filter((r) => state.schemeFilter === 'all' || r.verdict === state.schemeFilter);
  $$('#scheme-filter button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.f === state.schemeFilter)));
  $('#scheme-clear').hidden = !searching;
  $('#scheme-results-label').hidden = !searching;

  const list = $('#scheme-list');
  list.innerHTML = '';
  rows.forEach((r) => {
    const b = el('button', 'scheme-item');
    b.style.setProperty('--tone', r.tone);
    if (r.scheme_id === state.schemeSelected) b.setAttribute('aria-current', 'true');
    const ic = el('span', 'item-icon');
    ic.innerHTML = iconSvg(r.icon) || iconSvg('scheme');
    const body = el('span', 'item-body');
    body.append(el('span', 'item-title', r.name), el('span', 'item-text', r.summary));
    b.append(ic, body, verdictBadge(r.verdict));
    b.addEventListener('click', () => { state.schemeSelected = r.scheme_id; renderSchemes(); });
    list.append(b);
  });
  if (!rows.length) list.append(el('div', 'empty', '—'));

  const detail = $('#scheme-detail');
  const r = source.find((x) => x.scheme_id === state.schemeSelected) || all.find((x) => x.scheme_id === state.schemeSelected);
  detail.innerHTML = '';
  if (!r) {
    detail.append(Object.assign(el('div', 'empty'), { innerHTML: iconSvg('scheme') }));
    $('.empty', detail).append(el('p', '', t('pickScheme')));
    return;
  }
  detail.style.setProperty('--tone', r.tone);
  const head = el('div', 'detail-head');
  const ic = el('span', 'item-icon');
  ic.innerHTML = iconSvg(r.icon) || iconSvg('scheme');
  const ht = el('div');
  ht.style.cssText = 'display:flex;flex-direction:column;gap:6px;min-width:0';
  ht.append(el('h3', 'detail-title', r.name), verdictBadge(r.verdict));
  ht.lastChild.style.alignSelf = 'flex-start';
  head.append(ic, ht);

  const scroll = el('div', 'detail-scroll');
  scroll.append(el('p', '', r.summary));
  const ben = el('div', 'benefit-box');
  ben.append(el('div', 'eyebrow', t('benefit')), el('p', '', r.benefit));
  scroll.append(ben);
  const groups = [['reasons_met', 'reasonsMet', 'r-met', 'check'], ['reasons_unmet', 'reasonsUnmet', 'r-unmet', 'close'],
                  ['reasons_unknown', 'reasonsUnknown', 'r-unknown', 'question']];
  for (const [field, label, cls, icon] of groups) {
    if (!r[field]?.length) continue;
    const g = el('div', 'reason-group');
    g.append(el('h3', '', t(label)));
    r[field].forEach((text) => {
      const row = el('div', `reason ${cls}`);
      row.append(iconSpan(icon, 'r-icon'), el('span', '', text));
      g.append(row);
    });
    scroll.append(g);
  }
  scroll.append(el('p', 'note', t('schemeDisclaimer')));

  const foot = el('div', 'detail-foot');
  const listen = el('button', 'btn btn-ghost');
  listen.append(iconSpan('speaker'), el('span', '', t('listen')));
  const verdictText = t(VERDICT[r.verdict]?.key || 'verdictMaybe');
  const why = [...(r.reasons_unmet || []), ...(r.reasons_unknown || []), ...(r.reasons_met || [])].slice(0, 2).join(' ');
  listen.addEventListener('click', () => speak(`${r.name}. ${r.summary} ${t('benefit')}: ${r.benefit} ${verdictText}. ${why}`));
  foot.append(listen);
  if (r.verdict === 'maybe' || r.missing_fields?.length) {
    const fill = el('button', 'btn btn-primary');
    fill.append(iconSpan('edit'), el('span', '', t('fillDetails')));
    fill.addEventListener('click', () => go('profile'));
    foot.append(fill);
  }
  detail.append(head, scroll, foot);
}

// ─────────────────────────────────────────────────────────── learn
function renderLearn() {
  const L = state.lessons;
  $('#learn-progress').textContent = L ? t('learnProgressShort', { n: L.completed, total: L.total }) : '';
  const list = $('#lesson-list');
  list.innerHTML = '';
  (L?.results || []).forEach((lesson) => {
    const b = el('button', 'lesson-item');
    b.style.setProperty('--tone', lesson.tone);
    if (lesson.id === state.lessonSelected) b.setAttribute('aria-current', 'true');
    const ic = el('span', 'item-icon');
    ic.innerHTML = iconSvg(lesson.icon) || iconSvg('learn');
    const body = el('span', 'item-body');
    body.append(el('span', 'item-title', lesson.title), el('span', 'item-text', t('minutes', { n: lesson.minutes })));
    b.append(ic, body);
    if (lesson.progress.completed) {
      const d = el('span', 'badge lvl-eligible');
      d.innerHTML = iconSvg('check');
      d.append(document.createTextNode(t('lessonDone')));
      b.append(d);
    }
    b.addEventListener('click', () => { state.lessonSelected = lesson.id; state.quiz = null; renderLearn(); });
    list.append(b);
  });

  const detail = $('#lesson-detail');
  const lesson = L?.results?.find((x) => x.id === state.lessonSelected);
  detail.innerHTML = '';
  if (!lesson) {
    const e = el('div', 'empty');
    e.innerHTML = iconSvg('learn');
    e.append(el('p', '', t('pickLesson')));
    detail.append(e);
    return;
  }
  detail.style.setProperty('--tone', lesson.tone);
  const head = el('div', 'detail-head');
  const ic = el('span', 'item-icon');
  ic.innerHTML = iconSvg(lesson.icon) || iconSvg('learn');
  const ht = el('div');
  ht.append(el('h3', 'detail-title', lesson.title), el('span', 'muted small', t('minutes', { n: lesson.minutes })));
  ht.style.cssText = 'flex:1;min-width:0';
  const play = el('button', 'btn btn-primary btn-sm');
  play.append(iconSpan('play'), el('span', '', t('listen')));
  play.addEventListener('click', () => speak(`${lesson.title}. ${lesson.steps.join(' ')}`));
  head.append(ic, ht, play);

  const scroll = el('div', 'detail-scroll');
  const steps = el('ol', 'step-list');
  lesson.steps.forEach((text, i) => {
    const li = el('li', 'step-item');
    const sp = el('button', 'icon-btn');
    sp.innerHTML = iconSvg('speaker');
    sp.setAttribute('aria-label', t('listen'));
    sp.addEventListener('click', () => speak(text));
    li.append(el('span', 'step-num', String(i + 1)), el('p', '', text), sp);
    steps.append(li);
  });
  scroll.append(steps, renderQuiz(lesson));
  detail.append(head, scroll);
}

function renderQuiz(lesson) {
  if (!state.quiz || state.quiz.lessonId !== lesson.id) state.quiz = { lessonId: lesson.id, answers: [], result: null };
  const q = state.quiz;
  const wrap = el('div', 'quiz');
  const top = el('div', 'card-head');
  top.append(el('h2', '', t('quizTitle')));
  const dots = el('div', 'progress-dots');
  lesson.quiz.forEach((_, i) => dots.append(el('span', i < q.answers.length ? 'on' : '')));
  top.append(dots);
  wrap.append(top);

  if (q.result) {
    const r = q.result;
    const fb = el('div', `quiz-feedback ${r.passed ? 'lvl-ok' : 'lvl-caution'}`);
    fb.append(el('strong', '', t(r.passed ? 'quizPassed' : 'quizFailed', { score: r.score, total: r.total })));
    wrap.append(fb);
    lesson.quiz.forEach((question, i) => {
      const res = r.results[i];
      const block = el('div', 'reason ' + (res.correct ? 'r-met' : 'r-unmet'));
      const txt = el('div');
      txt.append(el('div', '', question.q), el('div', 'muted small', `${question.options[res.answer]} — ${res.explain}`));
      block.append(iconSpan(res.correct ? 'check' : 'close', 'r-icon'), txt);
      wrap.append(block);
    });
    const again = el('button', 'btn btn-ghost');
    again.append(iconSpan('history'), el('span', '', t('tryAgain')));
    again.addEventListener('click', () => { state.quiz = null; renderLearn(); });
    wrap.append(again);
    return wrap;
  }

  const i = q.answers.length;
  const question = lesson.quiz[i];
  wrap.append(el('div', 'muted small', t('questionOf', { n: i + 1, total: lesson.quiz.length })));
  const qt = el('div', 'quiz-q', question.q);
  wrap.append(qt);
  const opts = el('div', 'quiz-options');
  question.options.forEach((label, k) => {
    const b = el('button', 'quiz-opt', label);
    b.addEventListener('click', async () => {
      q.answers.push(k);
      speak(label);
      if (q.answers.length === lesson.quiz.length) {
        try {
          q.result = await api(`/api/literacy/lessons/${lesson.id}/quiz/`, { method: 'POST', body: { answers: q.answers, language: state.lang } });
          speak(t(q.result.passed ? 'quizPassed' : 'quizFailed', { score: q.result.score, total: q.result.total }));
          loadLessons();
        } catch { q.answers.pop(); toast(t('networkError'), true); }
      }
      renderLearn();
    });
    opts.append(b);
  });
  const hear = el('button', 'text-btn');
  hear.append(iconSpan('speaker'), el('span', '', t('listen')));
  hear.addEventListener('click', () => speak(`${question.q} ${question.options.join(', ')}`));
  wrap.append(opts, hear);
  return wrap;
}

// ─────────────────────────────────────────────────────────── scan
let cameraStream = null;

async function openCamera() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } } });
    const video = $('#camera');
    video.srcObject = cameraStream;
    video.hidden = false;
    $('#scan-preview').hidden = true;
    $('#vf-empty').hidden = true;
    await video.play();
    $('#btn-camera').hidden = true;
    $('#btn-capture').hidden = false;
  } catch (err) {
    console.error(err);
    toast(t('cameraUnavailable'), true);
  }
}

function closeCamera() {
  cameraStream?.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  const video = $('#camera');
  if (video) { video.srcObject = null; video.hidden = true; }
  $('#btn-camera') && ($('#btn-camera').hidden = false);
  $('#btn-capture') && ($('#btn-capture').hidden = true);
}

function capture() {
  const video = $('#camera');
  if (!video.videoWidth) return;
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  closeCamera();
  canvas.toBlob((blob) => blob && analyseImage(blob), 'image/jpeg', 0.92);
}

async function analyseImage(blob) {
  const preview = $('#scan-preview');
  preview.src = URL.createObjectURL(blob);
  preview.hidden = false;
  $('#vf-empty').hidden = true;
  state.scanResult = { pending: true };
  renderScan();
  const form = new FormData();
  form.append('image', blob, 'photo.jpg');
  form.append('language', state.lang);
  try {
    const path = state.scanMode === 'qr' ? '/api/vision/qr/' : '/api/vision/note/';
    state.scanResult = { mode: state.scanMode, ...(await api(path, { method: 'POST', form })) };
    speak(state.scanResult.reply_text);
  } catch (err) {
    console.error(err);
    state.scanResult = null;
    toast(t('networkError'), true);
  }
  renderScan();
}

const LEVEL = { ok: ['levelOk', 'check'], caution: ['levelCaution', 'warning'], danger: ['levelDanger', 'alert'] };

function renderScan() {
  $$('#scan-mode button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.m === state.scanMode)));
  $('#scan-samples').hidden = state.scanMode !== 'qr';
  const box = $('#scan-result');
  const r = state.scanResult;
  box.innerHTML = '';
  if (!r) {
    const e = el('div', 'empty');
    e.innerHTML = iconSvg('scan');
    e.append(el('p', '', t('scanEmpty')));
    box.append(e);
    return;
  }
  if (r.pending) { box.append(el('div', 'empty', t('scanning'))); return; }

  if (r.mode === 'qr') {
    const [key, icon] = LEVEL[r.level] || LEVEL.caution;
    const hero = el('div', `result-hero lvl-${r.level}`);
    const txt = el('div');
    // Only a name we verified goes in the headline. The name written inside a
    // code is whatever its printer chose -- a fraudster's sticker carries the
    // shop's own name -- so an unverified code is headed by its raw address.
    txt.append(el('h3', '', t(key)), el('p', '', r.payee_name_registered || r.payee_vpa || ''));
    hero.append(iconSpan(icon), txt);
    box.append(hero);
    if (r.payee_vpa || r.amount != null) {
      const rows = el('div');
      if (r.payee_vpa) { const rr = el('div', 'review-row'); rr.append(el('span', 'muted', 'UPI'), el('strong', '', r.payee_vpa)); rows.append(rr); }
      if (r.amount != null) { const rr = el('div', 'review-row'); rr.append(el('span', 'muted', t('amountLabel')), el('strong', '', `₹${money(r.amount)}`)); rows.append(rr); }
      box.append(rows);
    }
    box.append(el('p', '', r.reply_text));
    const meter = el('div', 'meter-row');
    const m = el('div', 'meter');
    const fill = el('span');
    fill.style.width = `${Math.round((r.tamper_score || 0) * 100)}%`;
    fill.style.setProperty('--tone', r.tamper_score >= 0.5 ? 'var(--danger)' : 'var(--ok)');
    m.append(fill);
    meter.append(el('span', '', t('stickerRisk')), m, el('span', '', `${Math.round((r.tamper_score || 0) * 100)}%`));
    box.append(meter);
    const foot = el('div', 'btn-row');
    foot.style.marginTop = 'auto';
    const listen = el('button', 'btn btn-ghost');
    listen.append(iconSpan('speaker'), el('span', '', t('listen')));
    listen.addEventListener('click', () => speak(r.reply_text));
    foot.append(listen);
    if (r.can_pay) {
      const pay = el('button', 'btn btn-primary');
      pay.append(iconSpan('send'), el('span', '', t('payThisShop')));
      pay.addEventListener('click', () => {
        const known = state.contacts.find((c) => c.vpa === r.payee_vpa);
        state.draft = { payee: known || { vpa: r.payee_vpa, name: r.payee_name_registered }, amount: r.amount ? String(r.amount) : '' };
        go('send');
      });
      foot.append(pay);
    }
    box.append(foot);
    return;
  }

  // note
  const hero = el('div', `result-hero ${r.denomination ? (r.confident ? 'lvl-ok' : 'lvl-caution') : 'lvl-caution'}`);
  const txt = el('div');
  txt.append(el('h3', '', r.denomination ? `₹${r.denomination}` : '—'), el('p', '', r.reply_text));
  hero.append(iconSpan('note'), txt);
  box.append(hero);
  const meter = el('div', 'meter-row');
  const m = el('div', 'meter');
  const fill = el('span');
  fill.style.width = `${Math.round(r.confidence * 100)}%`;
  m.append(fill);
  meter.append(el('span', '', t('confidence')), m, el('span', '', `${Math.round(r.confidence * 100)}%`));
  box.append(meter);
  if (r.backend === 'colour_heuristic') box.append(el('p', 'note', t('noteHeuristic')));
}

async function loadSample(name) {
  state.scanMode = 'qr';
  closeCamera();
  try {
    const blob = await (await fetch(`/samples/${name}.png`)).blob();
    await analyseImage(blob);
  } catch { toast(t('networkError'), true); }
}

// ─────────────────────────────────────────────────────────── safety
async function checkScam(text, { mini = false } = {}) {
  if (!text) return;
  const btn = mini ? $('#ov-scam-btn') : $('#btn-scam-check');
  btn.disabled = true;
  try {
    state.scamVerdict = await api('/api/fraud/check/', { method: 'POST', body: { text, language: state.lang } });
    state.askResult = null;
    const v = state.scamVerdict;
    speak(`${v.headline}. ${v.reasons.join(' ')} ${v.advice}`);
    loadChecks();
  } catch { toast(t('networkError'), true); } finally { btn.disabled = false; }
  renderView();
  if (!mini) $('#scam-result').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

// ── fraud questions: a search over reviewed answers, not a chatbot
const QUESTION_START = ['what', 'how', 'why', 'where', 'when', 'should', 'can ', 'is ', 'do ', 'does', 'will', 'who',
  'क्या', 'कैसे', 'क्यों', 'कहाँ', 'कहां', 'कब', 'என்ன', 'எப்படி', 'ஏன்', 'எங்கே', 'ఏమి', 'ఎలా', 'ఎందుకు', 'ఎక్కడ'];
const QUESTION_END = ['?', 'क्या', 'லாமா', 'ఆ', 'నా'];

// Same rule as the voice dialog: start or end decides. A pasted scam message
// with a "?" in the middle is a message to check, not a question to answer.
function looksLikeQuestion(text) {
  const x = text.trim().toLowerCase();
  return QUESTION_START.some((w) => x.startsWith(w)) || QUESTION_END.some((w) => x.endsWith(w));
}

async function loadSuggestions() {
  const key = `questions.${state.lang}`;
  try {
    state.suggestions = (await api(`/api/fraud/questions/?lang=${state.lang}`)).results || [];
    store.set(key, state.suggestions);
  } catch { state.suggestions = store.get(key, []); }
  if (state.view === 'safety') renderSafety();
}

async function askQuestion(text) {
  if (!text) return;
  const btn = $('#btn-ask');
  btn.disabled = true;
  try {
    state.askResult = await api('/api/fraud/ask/', { method: 'POST', body: { text, language: state.lang } });
    state.askShown = state.askResult.best;
    state.scamVerdict = null;
    speak(state.askShown ? state.askShown.answer : t('noAnswer'));
  } catch { toast(t('networkError'), true); } finally { btn.disabled = false; }
  renderSafety();
  // The answer lands below the input; bring it into view so it is not missed.
  $('#ask-result').scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function renderAsk() {
  const chips = $('#ask-suggest');
  chips.innerHTML = '';
  // Four, not all: each is a full sentence, and a wall of them reads as homework.
  state.suggestions.slice(0, 4).forEach((sug) => {
    const c = el('button', 'chip q', sug.question);
    c.addEventListener('click', () => { $('#scam-input').value = sug.question; askQuestion(sug.question); });
    chips.append(c);
  });

  const box = $('#ask-result');
  const r = state.askResult;
  box.hidden = !r;
  if (!r) return;
  box.innerHTML = '';
  const shown = state.askShown;

  if (shown) {
    const head = el('div', 'card-head');
    const ic = el('span', 'card-icon');
    ic.innerHTML = iconSvg(shown.icon) || iconSvg('shield');
    const sp = el('button', 'icon-btn');
    sp.innerHTML = iconSvg('speaker');
    sp.setAttribute('aria-label', t('listen'));
    sp.addEventListener('click', () => speak(`${shown.question} ${shown.answer}`));
    head.append(ic, el('h3', 'answer-q', shown.question), sp);
    box.append(el('div', 'eyebrow', t('bestAnswer')), head, el('p', 'answer-text', shown.answer));
    if (shown.links?.length) {
      const links = el('div', 'btn-row');
      shown.links.forEach((l) => {
        const a = el('a', l.href.startsWith('tel:') ? 'btn btn-danger btn-sm' : 'btn btn-ghost btn-sm');
        a.href = l.href;
        if (!l.href.startsWith('tel:')) { a.target = '_blank'; a.rel = 'noopener'; }
        a.append(iconSpan(l.href.startsWith('tel:') ? 'phoneCall' : 'globe'), el('span', '', l.label));
        links.append(a);
      });
      box.append(el('div', 'eyebrow', t('officialHelp')), links);
    }
  } else {
    // No reliable answer: say so, and put the one action that always helps first.
    box.append(el('div', 'no-answer', t('noAnswer')));
    const call = el('a', 'btn btn-danger btn-sm');
    call.href = 'tel:1930';
    call.append(iconSpan('phoneCall'), el('span', '', t('call1930')));
    call.style.alignSelf = 'flex-start';
    box.append(call);
  }

  const others = [...(r.best && shown?.id !== r.best.id ? [r.best] : []), ...r.related]
    .filter((x) => x.id !== shown?.id);
  if (others.length) {
    box.append(el('div', 'eyebrow', t(shown ? 'relatedQuestions' : 'maybeMeant')));
    const list = el('div', 'related');
    others.forEach((x) => {
      const b = el('button');
      b.append(el('span', '', x.question), iconSpan('chevron'));
      b.addEventListener('click', () => { state.askShown = x; speak(x.answer); renderSafety(); });
      list.append(b);
    });
    box.append(list);
  }
}

function renderSafety() {
  renderAsk();
  const box = $('#scam-result');
  const v = state.scamVerdict;
  box.hidden = !v;
  if (v) {
    const tone = { safe: 'var(--ok)', suspicious: 'var(--warn)', scam: 'var(--danger)' }[v.label];
    box.style.setProperty('--tone', tone);
    box.innerHTML = '';
    const head = el('div', 'verdict-head');
    const bi = el('span', `badge-icon lvl-${v.label}`);
    bi.innerHTML = iconSvg(v.label === 'safe' ? 'check' : v.label === 'scam' ? 'alert' : 'warning');
    const ht = el('div');
    ht.style.flex = '1';
    ht.append(el('h3', '', v.headline));
    const sp = el('button', 'icon-btn');
    sp.innerHTML = iconSvg('speaker');
    sp.addEventListener('click', () => speak(`${v.headline}. ${v.reasons.join(' ')} ${v.advice}`));
    head.append(bi, ht, sp);
    box.append(head);
    if (v.reasons.length) {
      const g = el('div', 'reason-group');
      g.append(el('h3', '', t('whyFlag')));
      v.reasons.forEach((reason) => {
        const row = el('div', `reason ${v.label === 'safe' ? 'r-met' : 'r-unmet'}`);
        row.append(iconSpan(v.label === 'safe' ? 'check' : 'warning', 'r-icon'), el('span', '', reason));
        g.append(row);
      });
      box.append(g);
    }
    const adv = el('div', 'advice');
    adv.append(el('div', 'eyebrow', t('whatToDo')), el('div', '', v.advice));
    box.append(adv);
    for (const [label, val] of [[t('modelScore'), v.model_score], [t('ruleScore'), v.rule_score]]) {
      if (!val && label === t('modelScore') && !v.backend?.includes('scamnet')) continue;
      const row = el('div', 'meter-row');
      const m = el('div', 'meter');
      const fill = el('span');
      fill.style.width = `${Math.round(val * 100)}%`;
      fill.style.setProperty('--tone', tone);
      m.append(fill);
      row.append(el('span', '', label), m, el('span', '', `${Math.round(val * 100)}%`));
      box.append(row);
    }
  }

  const tips = $('#tip-list');
  tips.innerHTML = '';
  TIPS.forEach((tip) => {
    const card = el('div', 'tip');
    const ic = el('span', 'item-icon');
    ic.innerHTML = iconSvg(tip.icon);
    const body = el('div');
    body.append(el('div', 'tip-title', tip.title[state.lang]), el('div', 'tip-text', tip.text[state.lang]));
    card.append(ic, body);
    card.addEventListener('click', () => speak(`${tip.title[state.lang]}. ${tip.text[state.lang]}`));
    tips.append(card);
  });

  $$('#report-kind button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.kind === state.reportKind)));
  const steps = $('#report-steps');
  steps.hidden = !state.reportSteps;
  if (state.reportSteps) {
    steps.innerHTML = '';
    steps.append(el('div', 'eyebrow', t('nextSteps')));
    const ol = el('ol', 'next-steps');
    state.reportSteps.forEach((s) => ol.append(el('li', '', s)));
    steps.append(ol);
  }

  const hist = $('#check-history');
  hist.innerHTML = '';
  if (!state.checks.length) hist.append(el('li', 'muted', t('noChecks')));
  state.checks.slice(0, 12).forEach((c) => {
    const li = el('li');
    const badge = el('span', `badge lvl-${c.label}`, c.label);
    li.append(badge, el('span', 'h-text', c.text));
    li.addEventListener('click', () => { $('#scam-input').value = c.text; });
    hist.append(li);
  });
}

async function submitReport(kind) {
  state.reportKind = kind;
  renderSafety();
  try {
    const res = await api('/api/fraud/report/', { method: 'POST', body: { kind, language: state.lang } });
    state.reportSteps = res.next_steps;
    speak(res.next_steps.join(' '));
  } catch { toast(t('networkError'), true); }
  renderSafety();
}

// ─────────────────────────────────────────────────────────── help
function renderHelp() {
  const list = $('#phrase-list');
  list.innerHTML = '';
  const phrases = [...(PHRASES[state.lang] || []),
    ...({ hi: ['मुझे खेती के लिए पैसा चाहिए', 'पिछले लेनदेन बताओ'], en: ['I need money for farming', 'show my recent payments'],
          ta: ['விவசாயத்துக்கு பணம் வேண்டும்', 'சமீபத்திய பரிவர்த்தனைகள்'], te: ['వ్యవసాయానికి డబ్బు కావాలి', 'ఇటీవలి లావాదేవీలు చూపించు'] }[state.lang] || [])];
  phrases.forEach((p) => {
    const b = el('button', 'phrase');
    b.append(iconSpan('chat'), el('span', '', p));
    // Tapping runs the phrase through the same NLU endpoint speech uses, so
    // this list doubles as a live test harness.
    b.addEventListener('click', () => sendUtterance(p));
    list.append(b);
  });
}

// ─────────────────────────────────────────────────────────── profile
function renderProfile() {
  const p = state.profile || {};
  const form = $('#profile-form');
  for (const name of ['age', 'annual_income', 'land_holding_acres', 'household_size', 'state']) {
    const input = form.elements[name];
    if (input && document.activeElement !== input) input.value = p[name] ?? '';
  }
  $$('[data-radio]', form).forEach((group) => {
    const value = String(p[group.dataset.radio] ?? '');
    $$('button', group).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === value)));
  });
}

async function saveProfile(event) {
  event.preventDefault();
  const form = event.target;
  const body = {};
  for (const name of ['age', 'annual_income', 'household_size']) {
    const v = form.elements[name].value.trim();
    body[name] = v === '' ? null : parseInt(v, 10);
  }
  const land = form.elements.land_holding_acres.value.trim();
  body.land_holding_acres = land === '' ? null : land;
  body.state = form.elements.state.value.trim();
  $$('[data-radio]', form).forEach((group) => {
    const on = $('button[aria-pressed="true"]', group);
    if (!on) return;
    const v = on.dataset.v;
    body[group.dataset.radio] = v === 'true' ? true : v === 'false' ? false : v;
  });
  try {
    const res = await api('/api/accounts/profile/', { method: 'PATCH', body });
    state.profile = res.profile;
    store.set('profile', state.profile);
    toast(t('saved'));
    speak(t('saved'));
    await loadSchemes();
  } catch (err) {
    toast(err.data ? Object.values(err.data).flat().join(' ') : t('networkError'), true);
  }
}

// ─────────────────────────────────────────────────────────── auth view
function renderAuth() {
  const grid = $('#demo-users');
  grid.innerHTML = '';
  DEMO_USERS.forEach((person) => {
    const card = el('button', 'person-card');
    const a = el('span', 'avatar', person.name[state.lang].slice(0, 1));
    a.style.background = person.color;
    card.append(a, el('span', 'person-name', person.name[state.lang]), el('span', 'person-sub', '@' + person.username));
    card.addEventListener('click', async () => {
      try { await signIn(person.username, DEMO_PASSWORD); } catch (err) {
        console.error(err);
        toast(err.status === 400 ? 'Run: python backend/manage.py seed_demo' : t('networkError'), true);
      }
    });
    grid.append(card);
  });
}

// ─────────────────────────────────────────────────────────── toast
let toastTimer = null;
function toast(message, isError = false) {
  const n = $('#toast');
  n.textContent = message;
  n.className = 'toast' + (isError ? ' error' : '');
  n.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { n.hidden = true; }, 4200);
}

// ─────────────────────────────────────────────────────────── wiring
function wire() {
  // auth shell
  $$('.lang-card').forEach((card) => card.addEventListener('click', () => {
    store.set('langChosen', true);
    setLanguage(card.dataset.lang);
    if (state.token) enterApp(); else showAuth('auth');
  }));
  $$('[data-goto]').forEach((b) => b.addEventListener('click', () => showAuth(b.dataset.goto)));
  $('#login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    try { await signIn(f.get('username'), f.get('password')); } catch (err) {
      toast(err.status === 400 ? t('loginFailed') : t('networkError'), true);
    }
  });
  $('#btn-new-account').addEventListener('click', startSignup);
  $$('.seg-btn').forEach((b) => b.addEventListener('click', () => {
    if (!state.signup) return;
    state.signup.channel = b.dataset.channel;
    state.signup.destination = '';
    renderSignup();
    $('#dest-input').focus();
  }));
  $('#signup-form').addEventListener('submit', (e) => { e.preventDefault(); requestCode(); });
  $('#dest-input').addEventListener('input', () => { $('#dest-error').hidden = true; });
  $('#btn-verify').addEventListener('click', verifyCode);
  $('#btn-resend').addEventListener('click', () => requestCode({ resend: true }));
  $('#details-form').addEventListener('submit', completeRegistration);

  // shell
  $$('[data-setlang]').forEach((b) => b.addEventListener('click', () => { store.set('langChosen', true); setLanguage(b.dataset.setlang); }));
  $('#btn-signout').addEventListener('click', signOut);
  $('#btn-menu').addEventListener('click', openDrawer);
  $('#scrim').addEventListener('click', closeDrawer);
  $('#mic').addEventListener('click', startListening);
  $('#ask-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const input = $('#ask-input');
    const text = input.value.trim();
    if (!text) { startListening(); return; }
    input.value = '';
    sendUtterance(text);
  });
  $('#reply-close').addEventListener('click', hideReply);
  $('#reply-speak').addEventListener('click', () => speak($('#reply').dataset.speak));
  $('#status-pill').addEventListener('click', () => { renderStatus(); drainQueue(); });
  $$('[data-view-go]').forEach((b) => b.addEventListener('click', () => go(b.dataset.viewGo)));
  $$('[data-speak-balance]').forEach((b) => b.addEventListener('click', speakBalance));

  // confirmation
  $('#btn-yes').addEventListener('click', confirmPending);
  $('#btn-no').addEventListener('click', cancelPending);
  $('#confirm-sheet').addEventListener('click', (e) => { if (e.target.id === 'confirm-sheet') cancelPending(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') { if (!$('#confirm-sheet').hidden) cancelPending(); closeDrawer(); }
  });

  // overview
  $('#ov-scam-btn').addEventListener('click', () => {
    const text = $('#ov-scam-input').value.trim();
    if (!text) return;
    // A question typed into the overview box opens its answer on the safety
    // screen; anything else is checked as a message, in place.
    if (looksLikeQuestion(text)) { $('#scam-input').value = text; go('safety'); askQuestion(text); }
    else checkScam(text, { mini: true });
  });
  $$('[data-scan-go]').forEach((b) => b.addEventListener('click', () => { state.scanMode = b.dataset.scanGo; state.scanResult = null; go('scan'); }));

  // balance
  $$('#txn-filter button').forEach((b) => b.addEventListener('click', () => { state.txnFilter = b.dataset.f; renderBalance(); }));

  // send
  $('#btn-review').addEventListener('click', reviewTransfer);

  // schemes
  $('#scheme-search').addEventListener('submit', (e) => {
    e.preventDefault();
    const q = $('#scheme-q').value.trim();
    state.schemeSelected = null;
    if (q) showSchemeSearch(q); else { state.schemeSearch = null; renderSchemes(); }
  });
  $('#scheme-clear').addEventListener('click', () => { state.schemeSearch = null; $('#scheme-q').value = ''; renderSchemes(); });
  $$('#scheme-filter button').forEach((b) => b.addEventListener('click', () => { state.schemeFilter = b.dataset.f; renderSchemes(); }));

  // scan
  $$('#scan-mode button').forEach((b) => b.addEventListener('click', () => { state.scanMode = b.dataset.m; state.scanResult = null; renderScan(); }));
  $('#btn-camera').addEventListener('click', openCamera);
  $('#btn-capture').addEventListener('click', capture);
  $('#scan-file').addEventListener('change', (e) => { const f = e.target.files?.[0]; if (f) analyseImage(f); e.target.value = ''; });
  $$('[data-sample]').forEach((b) => b.addEventListener('click', () => loadSample(b.dataset.sample)));

  // safety
  $('#btn-scam-check').addEventListener('click', () => checkScam($('#scam-input').value.trim()));
  $('#btn-ask').addEventListener('click', () => askQuestion($('#scam-input').value.trim()));
  $$('#report-kind button').forEach((b) => b.addEventListener('click', () => submitReport(b.dataset.kind)));

  // profile
  $$('#profile-form [data-radio] button').forEach((b) => b.addEventListener('click', () => {
    $$('button', b.parentElement).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
  }));
  $('#profile-form').addEventListener('submit', saveProfile);

  // routing + network
  window.addEventListener('popstate', () => {
    const v = location.hash.replace('#/', '');
    if (state.token && VIEWS.includes(v) && v !== state.view) go(v, { replace: true });
  });
  window.addEventListener('online', () => { renderStatus(); renderBalanceFigures(); drainQueue(); });
  window.addEventListener('offline', () => { renderStatus(); renderBalanceFigures(); });
}

// ─────────────────────────────────────────────────────────── boot
function hydrateIcons(root = document) {
  $$('[data-icon]', root).forEach((n) => setIcon(n, n.dataset.icon));
}

async function boot() {
  hydrateIcons();
  wire();
  initCursor();
  await migrateLegacy();

  if (!state.lang || !LANGS.includes(state.lang)) {
    state.lang = 'hi';
    t = makeT('hi');
    applyStrings();
    showAuth('language');
  } else {
    t = makeT(state.lang);
    document.documentElement.lang = state.lang;
    applyStrings();
    if (state.token) await enterApp(); else showAuth('auth');
  }

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch((err) => console.warn('SW failed', err));
  }
}

boot();
