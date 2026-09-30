(function () {
  const HOME_KEYS = ["nba-fantasy-helper", "nba-fantasy-draft"];
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const HIT = "hit";
  const NUDGE = "nudge";
  const DEAL = "deal";
  let clearHit = 0;
  let clearNudge = 0;
  let clearDeal = 0;

  function pulse(kind, ms) {
    if (reduced) return;
    document.body.dataset.motion = kind;
    const which = kind === NUDGE ? "nudge" : kind === DEAL ? "deal" : "hit";
    const timers = { nudge: clearNudge, deal: clearDeal, hit: clearHit };
    window.clearTimeout(timers[which]);
    const id = window.setTimeout(() => {
      if (document.body.dataset.motion === kind) delete document.body.dataset.motion;
    }, ms);
    if (which === "nudge") clearNudge = id;
    else if (which === "deal") clearDeal = id;
    else clearHit = id;
  }

  async function resetNight() {
    const body = { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" };
    const calls = Promise.allSettled([
      fetch("/helper/api/reset", body),
      fetch("/draft/api/reset", body),
      fetch("/lab/api/reset", body),
    ]);
    await Promise.race([calls, new Promise((resolve) => window.setTimeout(resolve, 1200))]);
    try {
      HOME_KEYS.forEach((key) => localStorage.removeItem(key));
    } catch (e) {
      /* keep going home */
    }
  }

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const home = target.closest("[data-home-reset]");
    if (home) {
      event.preventDefault();
      const href = home.getAttribute("href") || "/";
      pulse(HIT, 500);
      resetNight().finally(() => {
        window.location.href = href;
      });
      return;
    }
    if (reduced) return;
    if (target.closest("[data-nudge]")) {
      pulse(NUDGE, 220);
      return;
    }
    if (target.closest("[data-pick], [data-set], #sold, #mine, #open, #start, .go, .primary, .slot-choice, .close .me, .close .sold, .go-link")) {
      pulse(HIT, 900);
    }
  });

  document.addEventListener("animationend", (event) => {
    if (event.animationName === "hammer-in" && document.body.dataset.motion === HIT) {
      delete document.body.dataset.motion;
    }
    if (event.animationName === "tick-up" && document.body.dataset.motion === NUDGE) {
      delete document.body.dataset.motion;
    }
    if (event.animationName === "deal-row" && document.body.dataset.motion === DEAL) {
      delete document.body.dataset.motion;
    }
  });

  window.NBAMotion = { pulse, resetNight };
})();
