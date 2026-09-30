(function () {
  const KEY = "nba-fantasy-theme";

  function current() {
    return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
  }

  function paint(theme) {
    const next = theme === "dark" ? "dark" : "light";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* private mode */
    }
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = next === "dark" ? "#070d1a" : "#f6f8fc";
    document.querySelectorAll(".theme-toggle").forEach((btn) => {
      const dark = next === "dark";
      btn.setAttribute("aria-pressed", dark ? "true" : "false");
      btn.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
      btn.textContent = dark ? "Light" : "Dark";
    });
  }

  function apply(theme) {
    const next = theme === "dark" ? "dark" : "light";
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const run = () => paint(next);
    if (reduced || current() === next || typeof document.startViewTransition !== "function") {
      run();
      return;
    }
    try {
      document.startViewTransition(run);
    } catch {
      run();
    }
    window.setTimeout(() => {
      if (document.documentElement.dataset.theme !== next) run();
    }, 450);
  }

  window.themeToggleHtml = function () {
    const dark = current() === "dark";
    return `<button type="button" class="theme-toggle" aria-pressed="${dark ? "true" : "false"}" aria-label="${dark ? "Switch to light mode" : "Switch to dark mode"}">${dark ? "Light" : "Dark"}</button>`;
  };

  let saved = "light";
  try {
    saved = localStorage.getItem(KEY) === "dark" ? "dark" : "light";
  } catch {
    saved = "light";
  }
  apply(saved);

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".theme-toggle")) return;
    apply(current() === "dark" ? "light" : "dark");
  });
})();
