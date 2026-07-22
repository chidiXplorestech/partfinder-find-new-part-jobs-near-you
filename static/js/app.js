/* =========================================================================
   Align — swipe deck controller
   Vanilla JS + GSAP + Draggable. Talks to the Flask /api/search endpoint.
   ========================================================================= */
(function () {
  "use strict";

  const REDUCED_MOTION = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  ).matches;
  const hasGSAP = typeof window.gsap !== "undefined";
  if (hasGSAP && window.Draggable) gsap.registerPlugin(Draggable);

  // ---- DOM refs ----------------------------------------------------------
  const $ = (id) => document.getElementById(id);
  const homeView = $("homeView");
  const deckView = $("deckView");
  const form = $("searchForm");
  const deck = $("cardDeck");
  const controlBar = $("controlBar");
  const deckTitle = $("deckTitle");
  const deckNotice = $("deckNotice");

  const loadingState = $("loadingState");
  const errorState = $("errorState");
  const emptyState = $("emptyState");
  const doneState = $("doneState");
  const errorMessage = $("errorMessage");

  const matchOverlay = $("matchOverlay");
  const matchLine = $("matchLine");
  const matchesDrawer = $("matchesDrawer");
  const matchesList = $("matchesList");
  const matchesCount = $("matchesCount");

  // ---- State -------------------------------------------------------------
  let jobs = [];        // remaining, undealt jobs (top of stack = end of array)
  let saved = [];       // saved / matched jobs
  const VISIBLE = 3;    // cards rendered for depth

  // =======================================================================
  //  Search submission
  // =======================================================================
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    runSearch();
  });

  function collectQuery() {
    const data = new FormData(form);
    return {
      category: data.get("category"),
      days: data.getAll("days"),
      radius: parseInt(data.get("radius"), 10) || 5,
    };
  }

  async function runSearch() {
    const query = collectQuery();
    showView("deck");
    setState("loading");
    deckNotice.hidden = true;

    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(query),
      });
      const payload = await res.json();

      // Paywall: server asks the user to pay before revealing matches.
      if (res.status === 402 && payload.needs_payment) {
        showView("home");
        openPaywall();
        return;
      }

      if (!res.ok || !payload.ok) {
        showError(payload.error || "We couldn't load jobs right now.");
        return;
      }

      deckTitle.textContent = payload.category_label
        ? payload.category_label + " matches"
        : "Your matches";

      if (payload.notice) {
        deckNotice.textContent = payload.notice;
        deckNotice.hidden = false;
      }

      jobs = (payload.jobs || []).slice().reverse(); // top card = last element
      if (jobs.length === 0) {
        setState("empty");
        return;
      }
      setState("deck");
      renderDeck();
    } catch (err) {
      showError("Network error — check your connection and try again.");
    }
  }

  function showError(msg) {
    errorMessage.textContent = msg;
    setState("error");
  }

  // =======================================================================
  //  View / state management
  // =======================================================================
  function showView(name) {
    homeView.hidden = name !== "home";
    deckView.hidden = name !== "deck";
  }

  function setState(state) {
    loadingState.hidden = state !== "loading";
    errorState.hidden = state !== "error";
    emptyState.hidden = state !== "empty";
    doneState.hidden = state !== "done";
    deck.hidden = state !== "deck";
    controlBar.hidden = state !== "deck";
  }

  // =======================================================================
  //  Deck rendering
  // =======================================================================
  function renderDeck() {
    deck.innerHTML = "";
    const start = Math.max(0, jobs.length - VISIBLE);
    for (let i = start; i < jobs.length; i++) {
      const depth = jobs.length - 1 - i; // 0 = top card
      const card = buildCard(jobs[i], depth);
      deck.appendChild(card);
    }
    positionCards();
    const top = topCard();
    if (top && !REDUCED_MOTION && hasGSAP) {
      gsap.from(top, { y: 24, opacity: 0, duration: 0.35, ease: "power3.out" });
    }
    enableDrag();
  }

  function buildCard(job, depth) {
    const el = document.createElement("article");
    el.className = "job-card";
    el.dataset.url = job.redirect_url;

    const reasons = (job.match_reasons || [])
      .map((r) => `<span class="reason">${escapeHtml(r)}</span>`)
      .join("");

    el.innerHTML = `
      <div class="stamp like">Apply</div>
      <div class="stamp nope">Pass</div>

      <div class="card-top">
        <div class="company-tile">${escapeHtml(job.initials)}</div>
        <div class="card-top-right">
          <span class="via-pill"><span class="dot"></span>via ${escapeHtml(job.source)}</span>
          <button class="bookmark-btn" type="button" aria-label="Save job">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/></svg>
          </button>
        </div>
      </div>

      <div class="match-badge">
        <span class="pct grad-text">${job.match_percent}%</span>
        <span class="lbl">match</span>
      </div>

      <div class="overlay-badges">
        <span class="ov-badge type">${escapeHtml(job.type_display)}</span>
        <span class="ov-badge pay">${escapeHtml(job.salary_display)}</span>
      </div>

      <div class="card-glass">
        <div class="glass-meta">
          <span>${escapeHtml(job.created_display)}</span>
          <span class="sep">•</span>
          <span>${job.distance_miles != null ? job.distance_miles + " mi away" : "Nearby"}</span>
        </div>
        <h2 class="card-title">${escapeHtml(job.title)}</h2>
        <div class="card-company">${escapeHtml(job.company)} · ${escapeHtml(job.location)}</div>
        <div class="reasons">${reasons}</div>
        <div class="tiles">
          <div class="tile"><div class="tile-k">Pay</div><div class="tile-v">${escapeHtml(job.salary_display)}</div></div>
          <div class="tile"><div class="tile-k">Type</div><div class="tile-v">${escapeHtml(job.type_display)}</div></div>
          <div class="tile"><div class="tile-k">Source</div><div class="tile-v">${escapeHtml(job.source)}</div></div>
        </div>
      </div>
    `;

    el._job = job;

    el.querySelector(".bookmark-btn").addEventListener("click", (ev) => {
      ev.stopPropagation();
      if (el === topCard()) swipe("save");
    });

    return el;
  }

  function positionCards() {
    const cards = deck.querySelectorAll(".job-card");
    const total = cards.length;
    cards.forEach((card, idx) => {
      const depth = total - 1 - idx; // 0 = top
      const scale = 1 - depth * 0.05;
      const translateY = depth * 14;
      const setter = { scale: scale, y: translateY, zIndex: 100 - depth };
      if (hasGSAP) {
        gsap.set(card, setter);
      } else {
        card.style.transform = `translateY(${translateY}px) scale(${scale})`;
        card.style.zIndex = 100 - depth;
      }
      card.style.pointerEvents = depth === 0 ? "auto" : "none";
    });
  }

  function topCard() {
    const cards = deck.querySelectorAll(".job-card");
    return cards.length ? cards[cards.length - 1] : null;
  }

  // =======================================================================
  //  Drag to swipe (GSAP Draggable)
  // =======================================================================
  function enableDrag() {
    const card = topCard();
    if (!card || !hasGSAP || !window.Draggable) return;

    Draggable.create(card, {
      type: "x,y",
      inertia: false,
      onDrag: function () {
        const rot = this.x * 0.05;
        gsap.set(card, { rotation: rot });
        const likeStamp = card.querySelector(".stamp.like");
        const nopeStamp = card.querySelector(".stamp.nope");
        if (this.x > 0) {
          gsap.set(likeStamp, { opacity: Math.min(1, this.x / 100) });
          gsap.set(nopeStamp, { opacity: 0 });
        } else {
          gsap.set(nopeStamp, { opacity: Math.min(1, -this.x / 100) });
          gsap.set(likeStamp, { opacity: 0 });
        }
      },
      onDragEnd: function () {
        const threshold = 110;
        if (this.x > threshold) {
          flingCard(card, 1, () => onDecision("apply", card._job));
        } else if (this.x < -threshold) {
          flingCard(card, -1, () => onDecision("pass", card._job));
        } else {
          gsap.to(card, {
            x: 0,
            y: 0,
            rotation: 0,
            duration: 0.4,
            ease: "elastic.out(1, 0.6)",
          });
          gsap.to(card.querySelectorAll(".stamp"), { opacity: 0, duration: 0.2 });
        }
      },
    });
  }

  function flingCard(card, dir, done) {
    const dist = (window.innerWidth || 500) * 1.3;
    if (!hasGSAP || REDUCED_MOTION) {
      if (card) card.remove();
      done();
      advance();
      return;
    }
    gsap.to(card, {
      x: dir * dist,
      y: -40,
      rotation: dir * 18,
      opacity: 0,
      duration: 0.45,
      ease: "power2.in",
      onComplete: () => {
        card.remove();
        done();
        advance();
      },
    });
  }

  // =======================================================================
  //  Decisions (also reachable via buttons + keyboard)
  // =======================================================================
  function swipe(kind) {
    const card = topCard();
    if (!card) return;
    const job = card._job;
    if (kind === "pass") {
      flingCard(card, -1, () => onDecision("pass", job));
    } else if (kind === "apply") {
      flingCard(card, 1, () => onDecision("apply", job));
    } else if (kind === "save") {
      addSaved(job);
      pulseButton($("saveBtn"));
      flingCard(card, 1, () => {});
    }
  }

  function onDecision(kind, job) {
    if (kind === "apply") {
      addSaved(job);
      celebrateMatch(job);
      window.open(job.redirect_url, "_blank", "noopener");
    }
    // "pass" simply discards.
  }

  function advance() {
    // Remove the dealt job from the queue (it was the last element).
    jobs.pop();
    if (jobs.length === 0) {
      finishDeck();
      return;
    }
    // Add the next hidden card beneath the stack to keep depth.
    const needed = Math.min(VISIBLE, jobs.length);
    const rendered = deck.querySelectorAll(".job-card").length;
    if (rendered < needed) {
      const idx = jobs.length - rendered - 1;
      if (idx >= 0) {
        const card = buildCard(jobs[idx], 0);
        deck.insertBefore(card, deck.firstChild);
      }
    }
    positionCards();
    enableDrag();
  }

  function finishDeck() {
    $("doneSavedCount").textContent = saved.length
      ? saved.length + " roles"
      : "nothing yet";
    setState("done");
  }

  // =======================================================================
  //  Saved / matches
  // =======================================================================
  function addSaved(job) {
    if (saved.some((j) => j.redirect_url === job.redirect_url)) return;
    saved.push(job);
    updateMatchesBadge();
  }

  function updateMatchesBadge() {
    if (saved.length > 0) {
      matchesCount.textContent = String(saved.length);
      matchesCount.hidden = false;
    } else {
      matchesCount.hidden = true;
    }
  }

  function renderMatches() {
    if (saved.length === 0) {
      matchesList.innerHTML =
        '<div class="matches-empty">No matches yet. Swipe right or tap ♥ on a job you like.</div>';
      return;
    }
    matchesList.innerHTML = saved
      .map(
        (j) => `
      <div class="match-row">
        <div class="mini-tile">${escapeHtml(j.initials)}</div>
        <div class="mr-body">
          <div class="mr-title">${escapeHtml(j.title)}</div>
          <div class="mr-sub">${escapeHtml(j.company)} · ${escapeHtml(j.salary_display)}</div>
        </div>
        <a class="mr-apply" href="${encodeURI(j.redirect_url)}" target="_blank" rel="noopener">Apply</a>
      </div>`
      )
      .join("");
  }

  // =======================================================================
  //  "It's a match" celebration
  // =======================================================================
  function celebrateMatch(job) {
    matchLine.textContent = `You and ${job.company} could be a great fit.`;
    matchOverlay.hidden = false;
    if (hasGSAP && !REDUCED_MOTION) {
      const burst = matchOverlay.querySelector(".match-burst");
      const content = matchOverlay.querySelector(".match-content");
      gsap.fromTo(burst, { scale: 0.2, opacity: 0 }, { scale: 1.1, opacity: 1, duration: 0.5, ease: "power2.out" });
      gsap.fromTo(content, { scale: 0.6, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.5, ease: "back.out(1.7)" });
      gsap.fromTo(
        matchOverlay.querySelector(".match-spark"),
        { y: 10, rotation: -20 },
        { y: 0, rotation: 20, duration: 0.6, yoyo: true, repeat: 1, ease: "sine.inOut" }
      );
    }
    setTimeout(() => {
      matchOverlay.hidden = true;
    }, 1400);
  }

  function pulseButton(btn) {
    if (btn && hasGSAP && !REDUCED_MOTION) {
      gsap.fromTo(btn, { scale: 0.8 }, { scale: 1, duration: 0.4, ease: "back.out(2)" });
    }
  }

  // =======================================================================
  //  Paywall (£1 unlock via Stripe Checkout)
  // =======================================================================
  const CONFIG = window.ALIGN_CONFIG || { paywallActive: false, price: "£1.00", isPaid: false };
  const paywallOverlay = $("paywallOverlay");
  const paywallPayBtn = $("paywallPayBtn");

  function openPaywall() {
    $("paywallPrice").textContent = CONFIG.price || "£1.00";
    $("paywallBtnLabel").textContent = "Unlock for " + (CONFIG.price || "£1.00");
    paywallOverlay.hidden = false;
    if (hasGSAP && !REDUCED_MOTION) {
      gsap.fromTo(
        paywallOverlay.querySelector(".paywall-card"),
        { y: 30, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.4, ease: "power3.out" }
      );
    }
  }

  function closePaywall() {
    paywallOverlay.hidden = true;
  }

  async function startCheckout() {
    paywallPayBtn.disabled = true;
    $("paywallBtnLabel").textContent = "Redirecting…";
    try {
      const res = await fetch("/api/checkout", { method: "POST" });
      const payload = await res.json();
      if (payload.unlocked) {
        // Paywall disabled server-side — just proceed.
        closePaywall();
        runSearch();
        return;
      }
      if (payload.ok && payload.checkout_url) {
        window.location.href = payload.checkout_url; // hand off to Stripe
        return;
      }
      throw new Error(payload.error || "Checkout unavailable.");
    } catch (err) {
      $("paywallBtnLabel").textContent = "Unlock for " + (CONFIG.price || "£1.00");
      paywallPayBtn.disabled = false;
      alert("Sorry — couldn't start checkout. " + (err.message || ""));
    }
  }

  paywallPayBtn.addEventListener("click", startCheckout);
  $("paywallLater").addEventListener("click", closePaywall);

  // Handle the return trip from Stripe.
  (function handlePaymentReturn() {
    const params = new URLSearchParams(window.location.search);
    if (params.get("paid") === "1") {
      // Access unlocked server-side; clean the URL.
      history.replaceState({}, "", window.location.pathname);
    } else if (params.get("pay") === "failed") {
      history.replaceState({}, "", window.location.pathname);
      alert("Payment didn't complete. You can try again anytime.");
    } else if (params.get("pay") === "cancelled") {
      history.replaceState({}, "", window.location.pathname);
    }
  })();

  // =======================================================================
  //  Control bar + keyboard + drawer wiring
  // =======================================================================
  $("passBtn").addEventListener("click", () => swipe("pass"));
  $("applyBtn").addEventListener("click", () => swipe("apply"));
  $("saveBtn").addEventListener("click", () => swipe("save"));

  document.addEventListener("keydown", (e) => {
    if (deckView.hidden || deck.hidden) return;
    if (e.key === "ArrowLeft") swipe("pass");
    else if (e.key === "ArrowRight") swipe("apply");
  });

  $("backBtn").addEventListener("click", () => showView("home"));
  $("emptyBack").addEventListener("click", () => showView("home"));
  $("errorRetry").addEventListener("click", () => runSearch());
  $("doneRestart").addEventListener("click", () => showView("home"));
  $("doneMatches").addEventListener("click", openDrawer);

  $("matchesBtn").addEventListener("click", openDrawer);
  matchesDrawer.querySelectorAll("[data-close-drawer]").forEach((el) =>
    el.addEventListener("click", closeDrawer)
  );

  function openDrawer() {
    renderMatches();
    matchesDrawer.hidden = false;
  }
  function closeDrawer() {
    matchesDrawer.hidden = true;
  }

  // =======================================================================
  //  Utils
  // =======================================================================
  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  // Entrance animation for the hero on first load.
  if (hasGSAP && !REDUCED_MOTION) {
    gsap.from(".hero-title", { y: 20, opacity: 0, duration: 0.5, ease: "power3.out" });
    gsap.from(".hero-sub", { y: 16, opacity: 0, duration: 0.5, delay: 0.1, ease: "power3.out" });
    gsap.from(".filters .field", {
      y: 18,
      opacity: 0,
      duration: 0.45,
      stagger: 0.08,
      delay: 0.15,
      ease: "power3.out",
    });
  }
})();
