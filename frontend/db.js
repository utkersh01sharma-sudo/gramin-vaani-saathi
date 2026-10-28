// Offline queue in IndexedDB.
//
// Why not localStorage, which the first version used: localStorage is
// synchronous, capped at a few MB, and some Android browsers clear it under
// storage pressure with no warning. A queued payment is the one piece of
// client state that must survive -- losing it means the user believes money
// was sent that never was. IndexedDB is durable, async, and readable from a
// service worker if background sync is added later.
//
// Each record is keyed by the idempotency key it carries, so enqueueing the
// same action twice (a double tap while offline) stores it once.
//
// If IndexedDB cannot be opened (some private-browsing modes) the queue falls
// back to localStorage rather than failing: a less durable queue is better
// than refusing to queue at all.

const DB_NAME = 'gvs';
const STORE = 'queue';
const LS_KEY = 'gvs.queue';

let dbPromise = null;

function open() {
  if (dbPromise) return dbPromise;
  dbPromise = new Promise((resolve) => {
    if (!('indexedDB' in window)) { resolve(null); return; }
    let req;
    try { req = indexedDB.open(DB_NAME, 1); } catch { resolve(null); return; }
    req.onupgradeneeded = () => {
      req.result.createObjectStore(STORE, { keyPath: 'pending.idempotency_key' });
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => resolve(null);
    req.onblocked = () => resolve(null);
  });
  return dbPromise;
}

function lsRead() {
  try { return JSON.parse(localStorage.getItem(LS_KEY)) || []; } catch { return []; }
}
function lsWrite(items) {
  try { localStorage.setItem(LS_KEY, JSON.stringify(items)); } catch { /* full or blocked */ }
}

function tx(db, mode, fn) {
  return new Promise((resolve, reject) => {
    const t = db.transaction(STORE, mode);
    const result = fn(t.objectStore(STORE));
    t.oncomplete = () => resolve(result?.result ?? result);
    t.onerror = () => reject(t.error);
  });
}

export async function queueAll() {
  const db = await open();
  if (!db) return lsRead();
  const items = await tx(db, 'readonly', (s) => s.getAll());
  return (items || []).sort((a, b) => a.queued_at - b.queued_at);
}

export async function queuePut(item) {
  const db = await open();
  if (!db) {
    const items = lsRead().filter((i) => i.pending.idempotency_key !== item.pending.idempotency_key);
    items.push(item);
    lsWrite(items);
    return;
  }
  await tx(db, 'readwrite', (s) => s.put(item));
}

export async function queueDelete(keys) {
  const db = await open();
  if (!db) {
    lsWrite(lsRead().filter((i) => !keys.includes(i.pending.idempotency_key)));
    return;
  }
  await tx(db, 'readwrite', (s) => { keys.forEach((k) => s.delete(k)); });
}

// One-time move of anything the localStorage-era build left behind, so an
// action queued before this update is not silently dropped by it.
export async function migrateLegacy() {
  let legacy = [];
  try { legacy = JSON.parse(localStorage.getItem('gvs.queue')) || []; } catch { /* none */ }
  const db = await open();
  if (!db || !legacy.length) return;
  for (const item of legacy) {
    await queuePut({ pending: item.pending, language: item.language, queued_at: item.at || Date.now() });
  }
  try { localStorage.removeItem('gvs.queue'); } catch { /* ignore */ }
}
