/**
 * app.js â€” small, framework-free interactions shared by every page.
 * Loaded once from base.html, so all of this "just works" everywhere:
 *   1. Dark / light theme toggle, remembered in localStorage.
 *   2. Auto-dismiss flash messages after a few seconds.
 *   3. Count-up animation for any element carrying [data-counter].
 *   4. Bootstrap tooltip activation.
 *   5. Highlight the nav link that matches the current page.
 *   6. Quick client-side filter for tables marked [data-table-filter].
 */

// â”€â”€ 1. Theme toggle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const THEME_KEY = "portal-theme";

function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  const icon = document.getElementById("themeToggleIcon");
  if (icon) icon.className = theme === "dark" ? "fa-solid fa-sun" : "fa-solid fa-moon";
}

(function initTheme() {
  let saved = null; try { saved = localStorage.getItem(THEME_KEY); } catch(e) {} saved = saved ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  applyTheme(saved);
})();

function toggleTheme() {
  const next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  try { localStorage.setItem(THEME_KEY, next); } catch(e) {}
  applyTheme(next);
}

// â”€â”€ 3. Count-up animation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Parses "â‚¹12,450" / "38" / "5h" style text, animates the numeric part.
function animateCount(el, durationMs = 700) {
  const raw = el.textContent.trim();
  const match = raw.match(/-?[\d,]+(\.\d+)?/);
  if (!match) return;
  const target = parseFloat(match[0].replace(/,/g, ""));
  if (Number.isNaN(target)) return;
  const prefix = raw.slice(0, match.index);
  const suffix = raw.slice(match.index + match[0].length);
  const decimals = (match[1] || "").length - 1;
  const start = performance.now();

  function frame(now) {
    const t = Math.min(1, (now - start) / durationMs);
    const eased = 1 - Math.pow(1 - t, 3); // ease-out-cubic
    const value = target * eased;
    el.textContent = prefix + value.toLocaleString("en-IN", {
      minimumFractionDigits: Math.max(decimals, 0), maximumFractionDigits: Math.max(decimals, 0)
    }) + suffix;
    if (t < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}
window.animateCount = animateCount; // exposed so analytics.html can reuse it for values fetched via AJAX

// â”€â”€ 6. Client-side table quick filter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function wireTableFilters() {
  document.querySelectorAll("[data-table-filter]").forEach((input) => {
    const table = document.getElementById(input.getAttribute("data-table-filter"));
    if (!table) return;
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      table.querySelectorAll("tbody tr").forEach((row) => {
        row.style.display = row.textContent.toLowerCase().includes(q) ? "" : "none";
      });
    });
  });
}

// â”€â”€ 5. Active nav link â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function highlightActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll(".navbar .nav-link[href]").forEach((link) => {
    const href = link.getAttribute("href");
    if (href && href !== "/" && path.startsWith(href)) {
      link.classList.add("active-link");
    }
  });
}

// â”€â”€ 2 + 4 + wiring â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("themeToggleBtn");
  if (toggle) toggle.addEventListener("click", toggleTheme);

  // Count up every stat number already present in the initial page load
  document.querySelectorAll(".stat-card h3, [data-counter]").forEach((el) => animateCount(el));

  // Auto-dismiss flash alerts after 5s (user can still close them manually)
  document.querySelectorAll(".alert.alert-dismissible").forEach((alert) => {
    setTimeout(() => {
      const closeBtn = alert.querySelector(".btn-close");
      if (closeBtn) closeBtn.click();
    }, 5000);
  });

  // Bootstrap tooltips (title="" attributes anywhere in the page)
  document.querySelectorAll('[title]:not([data-bs-toggle])').forEach((el) => {
    el.setAttribute("data-bs-toggle", "tooltip");
  });
  if (window.bootstrap) {
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach((el) => new bootstrap.Tooltip(el));
  }

  highlightActiveNav();
  wireTableFilters();
});
