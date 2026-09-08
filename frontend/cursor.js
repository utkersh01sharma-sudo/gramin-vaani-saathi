// Interactive cursor: a dot that tracks the pointer exactly and a ring that
// trails it, growing and re-tinting over anything tappable.
//
// Two rules govern whether this runs at all:
//   1. Only on a fine pointer. On a phone -- the device this app is actually
//      for -- there is no cursor to replace, and hiding the native one would
//      break nothing but gain nothing either.
//   2. Never when the user has asked for reduced motion. A trailing element
//      that lags the pointer is exactly the kind of movement that setting is
//      there to stop.
//
// If either check fails the module returns and the browser's own cursor is left
// completely alone. That is why the hiding is done with a body class rather
// than a static CSS rule.

const FINE_POINTER = window.matchMedia('(pointer: fine)');
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)');

// Anything that responds to a click. Kept as a selector list rather than a
// [data-*] attribute so new UI picks the behaviour up without being annotated.
const INTERACTIVE =
  'button, a, input, textarea, select, summary, [role="button"], [tabindex]:not([tabindex="-1"])';

// Elements the ring should square off against instead of staying round, and
// which lean towards the pointer.
const CARD = '.tile, .lang-card, .person-card, .info-card, .scan-card, .balance-card, .seg-btn';
const MAGNETIC = '.tile, .lang-card, .person-card, .scan-card, .seg-btn, .mic, .btn-lg, .key, .chip';
const ACCENT = '.mic, .help-strip, .btn-no, .tile-speak';

// How far a magnetic element is allowed to lean, in px. Small on purpose: past
// about a sixth of the element it stops feeling responsive and starts feeling
// like the button is dodging you.
const PULL = 0.16;
const PULL_MAX = 9;

export function initCursor() {
  if (!FINE_POINTER.matches || REDUCED.matches) return;

  const dot = document.createElement('div');
  dot.className = 'cursor-dot cursor-hidden';
  const ring = document.createElement('div');
  ring.className = 'cursor-ring cursor-hidden';
  dot.setAttribute('aria-hidden', 'true');
  ring.setAttribute('aria-hidden', 'true');
  document.body.append(ring, dot);
  document.body.classList.add('cursor-on');

  let pointerX = window.innerWidth / 2;
  let pointerY = window.innerHeight / 2;
  let ringX = pointerX;
  let ringY = pointerY;
  let magnet = null;          // the element currently leaning towards the pointer
  let frame = null;

  // The ring eases towards the pointer at a fixed fraction per frame. 0.18 is
  // slow enough to read as a trail and fast enough that it never feels laggy
  // when you cross the screen.
  const EASE = 0.18;

  function tick() {
    ringX += (pointerX - ringX) * EASE;
    ringY += (pointerY - ringY) * EASE;
    ring.style.transform = `translate3d(${ringX}px, ${ringY}px, 0)`;
    dot.style.transform = `translate3d(${pointerX}px, ${pointerY}px, 0)`;
    frame = requestAnimationFrame(tick);
  }
  frame = requestAnimationFrame(tick);

  function releaseMagnet() {
    if (magnet) {
      magnet.style.transform = '';
      magnet.classList.remove('magnetic');
      magnet = null;
    }
  }

  document.addEventListener('pointermove', (event) => {
    // A pointermove from a touch or a pen means the user has switched input
    // device mid-session. Get out of the way rather than drawing a cursor
    // nobody is steering.
    if (event.pointerType !== 'mouse') { teardown(); return; }

    pointerX = event.clientX;
    pointerY = event.clientY;
    dot.classList.remove('cursor-hidden');
    ring.classList.remove('cursor-hidden');

    const target = event.target instanceof Element ? event.target : null;
    const hit = target?.closest(INTERACTIVE) ?? null;

    ring.classList.toggle('is-over', Boolean(hit));
    dot.classList.toggle('is-over', Boolean(hit));
    ring.classList.toggle('is-card', Boolean(target?.closest(CARD)));
    ring.classList.toggle('on-accent', Boolean(target?.closest(ACCENT)));

    const pullTarget = target?.closest(MAGNETIC) ?? null;
    if (pullTarget !== magnet) releaseMagnet();
    if (pullTarget) {
      magnet = pullTarget;
      magnet.classList.add('magnetic');
      const box = magnet.getBoundingClientRect();
      const dx = pointerX - (box.left + box.width / 2);
      const dy = pointerY - (box.top + box.height / 2);
      const clamp = (v) => Math.max(-PULL_MAX, Math.min(PULL_MAX, v * PULL));
      magnet.style.transform = `translate(${clamp(dx)}px, ${clamp(dy)}px)`;
    }
  }, { passive: true });

  document.addEventListener('pointerdown', () => ring.classList.add('is-down'));
  document.addEventListener('pointerup', () => ring.classList.remove('is-down'));

  // Leaving the window, or tabbing away, should not leave a dot stranded
  // mid-screen for the next person who looks at the laptop.
  document.addEventListener('pointerleave', hide);
  window.addEventListener('blur', hide);

  function hide() {
    dot.classList.add('cursor-hidden');
    ring.classList.add('cursor-hidden');
    releaseMagnet();
  }

  // Scrolling moves elements out from under a pointer that has not itself
  // moved, so the hover state has to be dropped rather than left stuck on.
  window.addEventListener('scroll', releaseMagnet, { passive: true });

  function teardown() {
    cancelAnimationFrame(frame);
    releaseMagnet();
    dot.remove();
    ring.remove();
    document.body.classList.remove('cursor-on');
  }

  // Plugging in a mouse, or switching the OS motion setting, should take effect
  // without a reload.
  REDUCED.addEventListener?.('change', (e) => { if (e.matches) teardown(); });
}
