/* One stroked icon set, drawn on a 24px grid.

   Emoji were the previous answer here and they were the wrong one. Emoji render
   in the font of whatever device you are holding, at whatever weight and colour
   that vendor chose, so the same screen looks different on every phone and never
   matches the rest of the interface. These are geometry: they inherit
   currentColor and the stroke width set in styles.css, so an icon in a warning
   strip is warning-coloured without a second asset existing.

   Everything is stroke-only on a 24 grid with 2px strokes and round joins, so
   the whole set reads as one hand. Nothing here is decorative — every icon
   labels a control that also carries text, because the primary user may not
   read either one on its own.
*/

const P = {
  /* ── primary navigation ─────────────────────────────────────────────── */
  wallet:   '<path d="M3 8.5A2.5 2.5 0 0 1 5.5 6H18a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z"/><path d="M3 8.5V7a2 2 0 0 1 2-2h11"/><circle cx="16.5" cy="13" r="1.4"/>',
  send:     '<path d="M21 3 10.5 13.5"/><path d="M21 3 14.5 21l-4-7.5L3 9.5z"/>',
  scheme:   '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="m9.5 14 1.8 1.8L15 12"/>',
  learn:    '<path d="M3 6.5C3 5.7 3.7 5 4.5 5H9a3 3 0 0 1 3 3v11a2.5 2.5 0 0 0-2.5-2.5H3z"/><path d="M21 6.5c0-.8-.7-1.5-1.5-1.5H15a3 3 0 0 0-3 3v11a2.5 2.5 0 0 1 2.5-2.5H21z"/>',
  scan:     '<path d="M3 8V6a3 3 0 0 1 3-3h2"/><path d="M16 3h2a3 3 0 0 1 3 3v2"/><path d="M21 16v2a3 3 0 0 1-3 3h-2"/><path d="M8 21H6a3 3 0 0 1-3-3v-2"/><path d="M7 12h10"/>',
  shield:   '<path d="M12 3 5 6v5.5c0 4.3 2.9 8.1 7 9.5 4.1-1.4 7-5.2 7-9.5V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
  help:     '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.6"/><path d="m5.6 5.6 3.9 3.9M14.5 14.5l3.9 3.9M18.4 5.6l-3.9 3.9M9.5 14.5l-3.9 3.9"/>',
  home:     '<path d="M4 11 12 4l8 7"/><path d="M6 10v9h12v-9"/><path d="M10 19v-5h4v5"/>',
  back:     '<path d="M15 5 8 12l7 7"/>',
  keyboard: '<rect x="2.5" y="6" width="19" height="12" rx="2.5"/><path d="M7 10h.01M11 10h.01M15 10h.01M17 13h.01M7 13h.01M9.5 13h5"/>',
  mic:      '<path d="M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
  plus:     '<path d="M12 5v14M5 12h14"/>',
  check:    '<path d="m5 12.5 4.5 4.5L19 7"/>',
  close:    '<path d="M6 6 18 18M18 6 6 18"/>',

  /* ── the small affordances ──────────────────────────────────────────── */
  speaker:  '<path d="M11 5 6.5 9H3v6h3.5L11 19z"/><path d="M15 9.5a3.5 3.5 0 0 1 0 5"/><path d="M17.8 6.5a7.5 7.5 0 0 1 0 11"/>',
  phone:    '<rect x="6" y="2.5" width="12" height="19" rx="2.8"/><path d="M10.5 18.5h3"/>',
  mail:     '<rect x="2.5" y="5" width="19" height="14" rx="2.5"/><path d="m3.5 7 7.3 5.4a2 2 0 0 0 2.4 0L20.5 7"/>',
  wrench:   '<path d="M15.5 3.5a5 5 0 0 0-5.9 6.5L3.6 16a2 2 0 0 0 2.8 2.8l6-6a5 5 0 0 0 6.5-5.9l-2.8 2.8-2.6-.7-.7-2.6z"/>',
  clock:    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.2l3.2 2"/>',
  info:     '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5M12 7.6h.01"/>',
  warning:  '<path d="M10.3 3.9 2.6 17.2A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.8L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 16.5h.01"/>',
  chat:     '<path d="M21 12a8 8 0 0 1-8 8H4.5a1.5 1.5 0 0 1-1.1-2.5L5 15.7A8 8 0 1 1 21 12z"/><path d="M9 11h6M9 14.5h3.5"/>',
  arrowOut: '<path d="M7 17 17 7"/><path d="M9 7h8v8"/>',
  arrowIn:  '<path d="M17 7 7 17"/><path d="M15 17H7V9"/>',

  /* ── schemes ────────────────────────────────────────────────────────── */
  sprout:   '<path d="M12 21v-8"/><path d="M12 13C12 9.5 9.5 7 6 7c0 3.5 2.5 6 6 6z"/><path d="M12 13c0-3 2.2-5.2 5.2-5.2C17.2 10.8 15 13 12 13z"/><path d="M7 21h10"/>',
  bank:     '<path d="M3.5 9.5 12 4l8.5 5.5"/><path d="M6 10v7M10 10v7M14 10v7M18 10v7"/><path d="M3.5 20h17"/>',
  girl:     '<circle cx="12" cy="8" r="3.5"/><path d="M5.5 20a6.5 6.5 0 0 1 13 0z"/>',
  pickaxe:  '<path d="M4 20 14 10"/><path d="M13.5 4.5c2.6-1 5.5-.2 7 1.7-2.4-.4-3.9.4-4.7 1.2s-1.6 2.3-1.2 4.7c-2-1.5-2.7-4.4-1.7-7z" transform="rotate(-45 14.5 8)"/><path d="m11 7.5 5.5 5.5"/>',

  /* ── literacy ───────────────────────────────────────────────────────── */
  upi:      '<rect x="6" y="2.5" width="12" height="19" rx="2.8"/><path d="m9.5 12 2 2 3.5-4"/>',
  lock:     '<rect x="4.5" y="10" width="15" height="11" rx="2.5"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10"/><path d="M12 14.5v2.5"/>',
  growth:   '<path d="M3 20h18"/><path d="m4 16 5-5 3.5 3.5L20 7"/><path d="M15.5 7H20v4.5"/>',
  coins:    '<ellipse cx="12" cy="6.5" rx="7" ry="3"/><path d="M5 6.5v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/><path d="M5 11.5v5c0 1.7 3.1 3 7 3s7-1.3 7-3v-5"/>',
  passbook: '<path d="M5 4.5A1.5 1.5 0 0 1 6.5 3H19v18H6.5A1.5 1.5 0 0 1 5 19.5z"/><path d="M9 3v18"/><path d="M12.5 8.5h3.5M12.5 12h3.5"/>',

  /* ── scams ──────────────────────────────────────────────────────────── */
  noOtp:    '<circle cx="12" cy="12" r="9"/><path d="m6 6 12 12"/>',
  gift:     '<rect x="3.5" y="9" width="17" height="4" rx="1"/><path d="M5 13v6.5A1.5 1.5 0 0 0 6.5 21h11a1.5 1.5 0 0 0 1.5-1.5V13"/><path d="M12 9v12"/><path d="M12 9C10 9 7.5 8.4 7.5 6.2A2.2 2.2 0 0 1 12 5.6a2.2 2.2 0 0 1 4.5.6C16.5 8.4 14 9 12 9z"/>',
  qr:       '<rect x="3.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.5"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.5"/><path d="M13.5 13.5h3v3h-3zM20.5 13.5v3M17.5 20.5h3M13.5 20.5h.01"/>',
  note:     '<rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.8"/><path d="M6 10.5v3M18 10.5v3"/>',
};

export const ICON_NAMES = Object.keys(P);

/** Icon markup as a string, for building an element via innerHTML. */
export function iconSvg(name, className = 'icon') {
  const body = P[name];
  if (!body) return '';
  return `<svg class="${className}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${body}</svg>`;
}

/** Icon as a real node, for appending. */
export function iconEl(name, className = 'icon') {
  const wrap = document.createElement('span');
  wrap.innerHTML = iconSvg(name, className);
  return wrap.firstElementChild;
}

/** Replace an element's contents with an icon, keeping its own classes. */
export function setIcon(el, name, className = 'icon') {
  if (el) el.innerHTML = iconSvg(name, className);
}
