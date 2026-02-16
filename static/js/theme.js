// theme.js
document.addEventListener("DOMContentLoaded", () => {
  document.body.classList.add("dark");
});
document.addEventListener("click", (event) => {
  const target = event.target.closest("button, a, input[type='submit']");

  if (!target) return;

  // Extract meaningful info
  const tag = target.tagName.toLowerCase();
  const text = target.innerText.trim().slice(0, 100); // avoid massive texts
  const href = target.getAttribute("href") || null;
  const action = `Clicked ${tag.toUpperCase()}`;

  // Log interaction
  logInteraction(action, { text, href });
});
function logInteraction(action, details = {}) {
  const csrfToken = document.querySelector('meta[name="csrf-token"]').content;
  fetch("/log-interaction", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrfToken
    },
    body: JSON.stringify({ action, details })
  }).catch(err => console.warn("Logging failed:", err));
}

// === Seasonal theme: auto-enable Halloween in October ===
(function () {
  try {
    const now = new Date();
    const isOctober = now.getMonth() === 9; // 0=Jan ... 9=Oct
    // Allow manual override via localStorage if you ever need it:
    // localStorage.setItem('season_force', 'halloween' | 'off' | '')
    const forced = localStorage.getItem('season_force');

    const shouldEnable =
      (forced === 'halloween') ||
      (forced !== 'off' && isOctober);

    if (shouldEnable) {
      document.body.classList.add('season-halloween');
    } else {
      document.body.classList.remove('season-halloween');
    }
  } catch (e) {
    console.warn('Seasonal theme failed:', e);
  }
})();
// === Seasonal Décor injector (refined) ===
(function () {
  try {
    const active = document.body.classList.contains('season-halloween');
    if (!active) return;
    if (document.querySelector('.hallo-decor')) return;

    const decor = document.createElement('div');
    decor.className = 'hallo-decor';
    decor.setAttribute('aria-hidden', 'true');
    document.body.appendChild(decor);

    // Corner webs
    ['web-tl','web-tr','web-bl','web-br'].forEach(cls=>{
      const d=document.createElement('div'); d.className='web '+cls; decor.appendChild(d);
    });

  // Toggle if you want the spider (set to false to hide)
  const ENABLE_SPIDER = true;
  if (ENABLE_SPIDER) {
    const spiderWrap = document.createElement('div');
    spiderWrap.className = 'spider-wrap';

    // thread
    const thread = document.createElement('div');
    thread.className = 'spider-thread';
    spiderWrap.appendChild(thread);

    // clear, readable SVG spider (body, head, legs)
    const spiderSvg = `
      <svg class="spider-svg" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <!-- body + head -->
        <g fill="#0b0b10" stroke="#000" stroke-opacity=".65">
          <ellipse cx="32" cy="38" rx="14" ry="12"/>
          <circle  cx="32" cy="24" r="7"/>
        </g>
        <!-- legs -->
        <g stroke="#000" stroke-width="3" stroke-linecap="round">
          <path d="M20 30 L8 22"/>
          <path d="M20 36 L6 36"/>
          <path d="M20 42 L8 50"/>
          <path d="M44 30 L56 22"/>
          <path d="M44 36 L58 36"/>
          <path d="M44 42 L56 50"/>
        </g>
        <!-- tiny eyes for definition -->
        <g fill="#7ad7ff" opacity=".9">
          <circle cx="29" cy="23" r="1.6"/>
          <circle cx="35" cy="23" r="1.6"/>
        </g>
      </svg>`;
    spiderWrap.insertAdjacentHTML('beforeend', spiderSvg);

    decor.appendChild(spiderWrap);
  }


    // Inline SVGs with clearer silhouettes
      const svgs = {
          bat: `
            <svg viewBox="0 0 120 60" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <!-- body + head -->
              <g fill="#0b0c10" stroke="rgba(255,255,255,.22)" stroke-width="1" vector-effect="non-scaling-stroke">
                <ellipse cx="60" cy="36" rx="10" ry="8"/>
                <path d="M54 28 L60 20 L66 28 Z" /> <!-- ears + head wedge -->
              </g>
              <!-- wings (scalloped) -->
              <path fill="#0b0c10" stroke="rgba(255,255,255,.22)" stroke-width="1" vector-effect="non-scaling-stroke"
                d="M10 44
                  Q18 34, 28 40
                  Q34 34, 42 38
                  Q48 34, 54 36
                  Q52 44, 44 46
                  Q36 48, 28 46
                  Q20 44, 12 46 Z
                  M110 44
                  Q102 34, 92 40
                  Q86 34, 78 38
                  Q72 34, 66 36
                  Q68 44, 76 46
                  Q84 48, 92 46
                  Q100 44, 108 46 Z"
              />
              <!-- tiny eyes -->
              <g fill="#7ad7ff" opacity=".9">
                <circle cx="58" cy="32" r="1.4" />
                <circle cx="62" cy="32" r="1.4" />
              </g>
            </svg>
          `,
      witch:`<svg viewBox="0 0 72 32" xmlns="http://www.w3.org/2000/svg">
              <path d="M6 20 l22 -7 6 2 3 7 26 6 -16 2 -12 -4 -6 2 -9 -4z" fill="#111318" stroke="rgba(255,255,255,.10)" stroke-width="1"/>
              <path d="M26 9 l7 -7 10 2 -10 3z" fill="#111318" stroke="rgba(255,255,255,.10)" stroke-width="1"/>
            </svg>`,
      pumpkin:`<svg viewBox="0 0 28 24" xmlns="http://www.w3.org/2000/svg">
                <ellipse cx="14" cy="14" rx="10" ry="7" fill="#ff7a00"/>
                <ellipse cx="10" cy="14" rx="6" ry="6" fill="#ff8e1f" opacity=".9"/>
                <ellipse cx="18" cy="14" rx="6" ry="6" fill="#ff8e1f" opacity=".9"/>
                <rect x="13" y="5" width="2" height="5" rx="1" fill="#3b6b2a"/>
              </svg>`
    };

    // Fewer + slower + always bats (no witches)
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const forceMotion = localStorage.getItem('season_motion');
    const motionAllowed = (forceMotion === 'on') || (forceMotion !== 'off' && !prefersReduced);

    const isSmall = Math.min(window.innerWidth, window.innerHeight) < 720;
    const COUNT = motionAllowed ? 1 : 0; // exactly two flyers

    function rand(min,max){return Math.random()*(max-min)+min}

    for (let i=0; i<COUNT; i++){
      const actor = document.createElement('div');
      actor.className = 'actor';
      actor.innerHTML = svgs.bat;

      // Keep them between 18–70vh so they don't sit on the header
      const y = rand(18, 70);
      const t = rand(36, 52);               // slower
      const w = isSmall ? rand(64, 78) : rand(72, 96); // larger
      const r0 = rand(-4, 4), r1 = rand(-4, 4);

      actor.style.setProperty('--y', `${y}vh`);
      actor.style.setProperty('--t', `${t}s`);
      actor.style.setProperty('--w', `${w}px`);
      actor.style.setProperty('--r0', `${r0}deg`);
      actor.style.setProperty('--r1', `${r1}deg`);

      const fromLeft = (i % 2 === 0); // one left->right, one right->left
      actor.style.setProperty('--x0', fromLeft ? '-14vw' : '114vw');
      actor.style.setProperty('--x1', fromLeft ? '114vw' : '-14vw');

      // Staggered start so they don't overlap
      actor.style.animationDelay = `-${rand(0, t)}s`;

      decor.appendChild(actor);
    }


    // Two static pumpkins near footer edges (no motion)
    const pLeft = document.createElement('div');
    pLeft.className = 'pumpkin-static pumpkin-left';
    pLeft.innerHTML = svgs.pumpkin;
    const pRight = document.createElement('div');
    pRight.className = 'pumpkin-static pumpkin-right';
    pRight.innerHTML = svgs.pumpkin;
    decor.appendChild(pLeft); decor.appendChild(pRight);

  } catch (e) { console.warn('Seasonal décor injection failed:', e); }
})();



function nthWeekdayOfMonth(year, monthIndex0, weekday0, n) {
  // monthIndex0: 0=Jan, weekday0: 0=Sun
  const first = new Date(year, monthIndex0, 1);
  const firstWeekday = first.getDay();
  const offset = (weekday0 - firstWeekday + 7) % 7;
  return new Date(year, monthIndex0, 1 + offset + (n - 1) * 7);
}

function easterSunday(year) {
  // Anonymous Gregorian algorithm (works for 1583+)
  const a = year % 19;
  const b = Math.floor(year / 100);
  const c = year % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const month = Math.floor((h + l - 7 * m + 114) / 31); // 3=March, 4=April
  const day = ((h + l - 7 * m + 114) % 31) + 1;
  return new Date(year, month - 1, day);
}

function dateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
}

function inRange(d, start, end) {
  const x = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const s = new Date(start.getFullYear(), start.getMonth(), start.getDate());
  const e = new Date(end.getFullYear(), end.getMonth(), end.getDate());
  return x >= s && x <= e;
}

function pickSiteTheme(now = new Date()) {
  const y = now.getFullYear();

  // --- Holidays (feel free to tweak windows) ---
  const valentine = new Date(y, 1, 14); // Feb 14
  if (inRange(now, new Date(y, 1, 10), new Date(y, 1, 15))) return "valentine";

  // Easter window (Fri -> Mon)
  const easter = easterSunday(y);
  const goodFriday = new Date(easter); goodFriday.setDate(easter.getDate() - 2);
  const easterMonday = new Date(easter); easterMonday.setDate(easter.getDate() + 1);
  if (inRange(now, goodFriday, easterMonday)) return "easter";

  // Halloween week
  if (inRange(now, new Date(y, 9, 25), new Date(y, 10, 2))) return "halloween"; // Oct 25 -> Nov 2

  // Thanksgiving (US/Canada differ; this is US: 4th Thu in Nov)
  const thanksgivingUS = nthWeekdayOfMonth(y, 10, 4, 4); // Nov (10), Thu (4), 4th
  if (inRange(now, new Date(y, 10, thanksgivingUS.getDate() - 3), new Date(y, 10, thanksgivingUS.getDate() + 1))) {
    return "thanksgiving";
  }

  // Christmas / New Year
  if (inRange(now, new Date(y, 11, 20), new Date(y, 11, 31))) return "christmas";
  if (inRange(now, new Date(y, 0, 1), new Date(y, 0, 3))) return "newyear";

  // --- Seasons (Northern hemisphere defaults) ---
  const m = now.getMonth(); // 0=Jan
  if (m === 11 || m === 0 || m === 1) return "winter";
  if (m >= 2 && m <= 4) return "spring";
  if (m >= 5 && m <= 7) return "summer";
  return "autumn";
}

function applySiteTheme(themeKey) {
  document.body.dataset.siteTheme = themeKey || "default";
}

window.addEventListener("DOMContentLoaded", () => {
  // Optional manual override:
  const override = localStorage.getItem("site_theme_override"); // e.g. "halloween"
  const theme = override || pickSiteTheme(new Date());
  applySiteTheme(theme);
});
