/* =========================================================================
   Align — app controller
   Vanilla JS + GSAP. Views: onboarding → home → deck. Sheets: details,
   profile, paywall. Persistence: localStorage (shortlist, applied, onboarded).
   ========================================================================= */
(function () {
  "use strict";

  var REDUCED_MOTION = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var hasGSAP = typeof window.gsap !== "undefined";
  if (hasGSAP && window.Draggable) gsap.registerPlugin(Draggable);

  var CONFIG = window.ALIGN_CONFIG || { paywallActive: false, price: "£1.00", isPaid: false };

  var $ = function (id) { return document.getElementById(id); };

  // ---- Views & controls --------------------------------------------------
  var onboarding = $("onboarding");
  var topbar = $("topbar");
  var homeView = $("homeView");
  var deckView = $("deckView");
  var form = $("searchForm");
  var deck = $("cardDeck");
  var controlBar = $("controlBar");
  var deckHint = $("deckHint");
  var deckTitle = $("deckTitle");
  var deckCount = $("deckCount");
  var deckNotice = $("deckNotice");

  var loadingState = $("loadingState");
  var errorState = $("errorState");
  var emptyState = $("emptyState");
  var doneState = $("doneState");

  var detailSheet = $("detailSheet");
  var profileSheet = $("profileSheet");
  var paywallOverlay = $("paywallOverlay");
  var toastEl = $("toast");

  // ---- State -------------------------------------------------------------
  var jobs = [];          // remaining stack (top card = last element)
  var totalInSearch = 0;
  var detailJob = null;
  var profileTab = "saved";
  var VISIBLE = 3;

  // ---- Persistence -------------------------------------------------------
  function load(key, fallback) {
    try { return JSON.parse(localStorage.getItem(key)) || fallback; }
    catch (e) { return fallback; }
  }
  function persist(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
  }
  var saved = load("align.saved", []);
  var applied = load("align.applied", []);

  // =======================================================================
  //  Onboarding
  // =======================================================================
  function startApp() {
    onboarding.hidden = true;
    topbar.hidden = false;
    showView("home");
    persist("align.onboarded", true);
    if (hasGSAP && !REDUCED_MOTION) {
      gsap.from(".hero-eyebrow, .hero-title", { y: 14, opacity: 0, duration: 0.5, stagger: 0.07, ease: "power3.out" });
      gsap.from(".setup .field, .setup .btn-cta", { y: 16, opacity: 0, duration: 0.45, stagger: 0.06, delay: 0.12, ease: "power3.out" });
    }
  }

  (function initOnboarding() {
    if (load("align.onboarded", false)) { startApp(); return; }
    onboarding.hidden = false;

    var track = $("obTrack");
    var dots = $("obDots").children;
    var next = $("obNext");
    var slideCount = track.children.length;

    function currentSlide() {
      return Math.round(track.scrollLeft / track.clientWidth);
    }
    function syncDots() {
      var idx = currentSlide();
      for (var i = 0; i < dots.length; i++) dots[i].classList.toggle("active", i === idx);
      next.textContent = idx === slideCount - 1 ? "Start swiping" : "Continue";
    }
    track.addEventListener("scroll", function () { requestAnimationFrame(syncDots); });
    next.addEventListener("click", function () {
      var idx = currentSlide();
      if (idx >= slideCount - 1) { startApp(); return; }
      track.scrollTo({ left: (idx + 1) * track.clientWidth, behavior: REDUCED_MOTION ? "auto" : "smooth" });
    });
    $("obSkip").addEventListener("click", startApp);
  })();

  // ---- Greeting ----------------------------------------------------------
  (function greet() {
    var h = new Date().getHours();
    $("greeting").textContent = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  })();

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
    deckHint.hidden = state !== "deck";
  }

  // =======================================================================
  //  Search
  // =======================================================================
  form.addEventListener("submit", function (e) { e.preventDefault(); runSearch(); });

  function collectQuery() {
    var data = new FormData(form);
    return {
      category: data.get("category"),
      days: data.getAll("days"),
      radius: parseInt(data.get("radius"), 10) || 5,
    };
  }

  function runSearch() {
    var query = collectQuery();
    showView("deck");
    setState("loading");
    deckNotice.hidden = true;
    deckCount.textContent = "";

    fetch("/api/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(query),
    })
      .then(function (res) { return res.json().then(function (p) { return { res: res, payload: p }; }); })
      .then(function (r) {
        var res = r.res, payload = r.payload;

        if (res.status === 402 && payload.needs_payment) {
          showView("home");
          openPaywall();
          return;
        }
        if (!res.ok || !payload.ok) {
          showError(payload.error || "We couldn't load jobs just now.");
          return;
        }

        deckTitle.textContent = payload.category_label ? payload.category_label + " near you" : "Nearby jobs";
        if (payload.notice) {
          deckNotice.textContent = payload.notice;
          deckNotice.hidden = false;
        }

        jobs = (payload.jobs || []).slice().reverse();
        totalInSearch = jobs.length;
        if (!jobs.length) { setState("empty"); return; }
        setState("deck");
        renderDeck();
        updateCount();
      })
      .catch(function () {
        showError("Check your connection and try again.");
      });
  }

  function showError(msg) {
    $("errorMessage").textContent = msg;
    setState("error");
  }

  function updateCount() {
    var seen = totalInSearch - jobs.length + 1;
    deckCount.textContent = jobs.length ? seen + " of " + totalInSearch : "";
  }

  // =======================================================================
  //  Deck rendering
  // =======================================================================
  var TILE_TINTS = [
    ["#E8EDFC", "#003ECD"], // persian blue
    ["#E3E8F2", "#002A62"], // royal blue
    ["#FBF2D9", "#8A6410"], // creamy gold
    ["#FFE9EC", "#C11227"], // imperial red
    ["#EDF1F8", "#475980"], // cool grey-blue
  ];
  function tintFor(name) {
    var h = 0;
    for (var i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
    return TILE_TINTS[h % TILE_TINTS.length];
  }

  function logoTile(job, size) {
    var t = tintFor(job.company || "?");
    return '<div class="logo-tile" style="background:' + t[0] + ";color:" + t[1] + '" aria-hidden="true">' + esc(job.initials) + "</div>";
  }

  function matchRing(pct) {
    var r = 19, c = 2 * Math.PI * r;
    var off = c * (1 - pct / 100);
    return (
      '<div class="match-ring" title="Match score" aria-label="' + pct + '% match">' +
      '<svg width="46" height="46" viewBox="0 0 46 46" aria-hidden="true">' +
      '<circle class="ring-bg" cx="23" cy="23" r="' + r + '" fill="none" stroke-width="4"/>' +
      '<circle class="ring-fg" cx="23" cy="23" r="' + r + '" fill="none" stroke-width="4" stroke-dasharray="' + c + '" stroke-dashoffset="' + off + '"/>' +
      "</svg>" +
      '<span class="ring-label">' + pct + "</span>" +
      "</div>"
    );
  }

  function buildCard(job) {
    var el = document.createElement("article");
    el.className = "job-card";
    el.setAttribute("tabindex", "0");
    el.setAttribute("aria-label", job.title + " at " + job.company);

    var reasons = (job.match_reasons || [])
      .map(function (r) { return '<div class="reason">' + esc(r) + "</div>"; })
      .join("");

    el.innerHTML =
      '<div class="stamp like">Shortlist</div>' +
      '<div class="stamp nope">Pass</div>' +
      '<div class="card-head">' +
        logoTile(job) +
        '<div class="card-co">' +
          '<div class="co-name">' + esc(job.company) + "</div>" +
          '<div class="co-loc">' + esc(job.location) + "</div>" +
        "</div>" +
        matchRing(job.match_percent) +
      "</div>" +
      '<h2 class="card-title">' + esc(job.title) + "</h2>" +
      '<div class="card-pills">' +
        '<span class="pill pay">' + esc(job.salary_display) + "</span>" +
        '<span class="pill">' + esc(job.type_display) + "</span>" +
        (job.distance_miles != null ? '<span class="pill">' + job.distance_miles + " mi</span>" : "") +
      "</div>" +
      (reasons
        ? '<div class="card-reasons"><div class="reasons-label">Why it fits</div>' + reasons + "</div>"
        : "") +
      '<div class="card-foot">' +
        "<span>" + esc(job.created_display) + " · via " + esc(job.source) + "</span>" +
        '<span class="tap-hint">Tap for details</span>' +
      "</div>";

    el._job = job;

    el.addEventListener("click", function (e) {
      if (el === topCard() && !el._dragging) openDetail(job);
    });
    el.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && el === topCard()) openDetail(job);
    });

    return el;
  }

  function renderDeck() {
    deck.innerHTML = "";
    var start = Math.max(0, jobs.length - VISIBLE);
    for (var i = start; i < jobs.length; i++) {
      deck.appendChild(buildCard(jobs[i]));
    }
    positionCards();
    var top = topCard();
    if (top && hasGSAP && !REDUCED_MOTION) {
      gsap.from(top, { y: 26, opacity: 0, duration: 0.4, ease: "power3.out" });
    }
    enableDrag();
  }

  function positionCards() {
    var cards = deck.querySelectorAll(".job-card");
    var total = cards.length;
    cards.forEach(function (card, idx) {
      var depth = total - 1 - idx;
      var scale = 1 - depth * 0.045;
      var y = depth * 12;
      if (hasGSAP) gsap.set(card, { scale: scale, y: y, zIndex: 100 - depth });
      else {
        card.style.transform = "translateY(" + y + "px) scale(" + scale + ")";
        card.style.zIndex = 100 - depth;
      }
      card.style.pointerEvents = depth === 0 ? "auto" : "none";
    });
  }

  function topCard() {
    var cards = deck.querySelectorAll(".job-card");
    return cards.length ? cards[cards.length - 1] : null;
  }

  // =======================================================================
  //  Drag physics
  // =======================================================================
  function enableDrag() {
    var card = topCard();
    if (!card || !hasGSAP || !window.Draggable) return;

    Draggable.create(card, {
      type: "x,y",
      onDragStart: function () { card._dragging = true; },
      onDrag: function () {
        gsap.set(card, { rotation: this.x * 0.05 });
        var like = card.querySelector(".stamp.like");
        var nope = card.querySelector(".stamp.nope");
        if (this.x > 0) {
          gsap.set(like, { opacity: Math.min(1, this.x / 90) });
          gsap.set(nope, { opacity: 0 });
        } else {
          gsap.set(nope, { opacity: Math.min(1, -this.x / 90) });
          gsap.set(like, { opacity: 0 });
        }
      },
      onDragEnd: function () {
        var threshold = 100;
        if (this.x > threshold) {
          fling(card, 1, function () { onShortlist(card._job); });
        } else if (this.x < -threshold) {
          fling(card, -1, function () {});
        } else {
          gsap.to(card, { x: 0, y: 0, rotation: 0, duration: 0.5, ease: "elastic.out(1, 0.65)" });
          gsap.to(card.querySelectorAll(".stamp"), { opacity: 0, duration: 0.2 });
        }
        // Delay clearing so the click handler after drag-release is ignored.
        setTimeout(function () { card._dragging = false; }, 120);
      },
    });
  }

  function fling(card, dir, after) {
    var dist = (window.innerWidth || 480) * 1.25;
    if (!hasGSAP || REDUCED_MOTION) {
      card.remove(); after(); advance(); return;
    }
    gsap.to(card, {
      x: dir * dist, y: -30, rotation: dir * 14, opacity: 0,
      duration: 0.4, ease: "power2.in",
      onComplete: function () { card.remove(); after(); advance(); },
    });
  }

  // =======================================================================
  //  Decisions
  // =======================================================================
  function swipe(kind) {
    var card = topCard();
    if (!card) return;
    if (kind === "pass") fling(card, -1, function () {});
    else if (kind === "save") fling(card, 1, function () { onShortlist(card._job); });
  }

  function onShortlist(job) {
    addSaved(job);
    toast('Shortlisted <span class="tick">✓</span>');
  }

  function advance() {
    jobs.pop();
    if (!jobs.length) { finishDeck(); return; }
    var needed = Math.min(VISIBLE, jobs.length);
    var rendered = deck.querySelectorAll(".job-card").length;
    if (rendered < needed) {
      var idx = jobs.length - rendered - 1;
      if (idx >= 0) deck.insertBefore(buildCard(jobs[idx]), deck.firstChild);
    }
    positionCards();
    enableDrag();
    updateCount();
  }

  function finishDeck() {
    $("doneSavedLine").textContent = saved.length
      ? "you shortlisted " + saved.length + (saved.length === 1 ? " job." : " jobs.")
      : "come back tomorrow.";
    setState("done");
  }

  // =======================================================================
  //  Detail sheet
  // =======================================================================
  function openDetail(job) {
    detailJob = job;
    var body = $("detailBody");
    body.innerHTML =
      '<div class="detail-head">' +
        logoTile(job) +
        '<div class="card-co">' +
          '<div class="co-name">' + esc(job.company) + "</div>" +
          '<div class="co-loc">' + esc(job.location) + "</div>" +
        "</div>" +
        matchRing(job.match_percent) +
      "</div>" +
      '<h2 class="detail-title">' + esc(job.title) + "</h2>" +
      '<div class="card-pills">' +
        '<span class="pill pay">' + esc(job.salary_display) + "</span>" +
        '<span class="pill">' + esc(job.type_display) + "</span>" +
        (job.distance_miles != null ? '<span class="pill">' + job.distance_miles + " mi away</span>" : "") +
      "</div>" +
      (job.match_reasons && job.match_reasons.length
        ? '<div class="detail-section"><h3>Why it fits</h3>' +
          job.match_reasons.map(function (r) { return '<div class="reason">' + esc(r) + "</div>"; }).join("") +
          "</div>"
        : "") +
      (job.description
        ? '<div class="detail-section"><h3>About this role</h3><p class="detail-desc">' + esc(job.description) + "</p></div>"
        : "") +
      '<div class="detail-section"><h3>Details</h3><div class="detail-meta">' +
        metaTile("Posted", job.created_display) +
        metaTile("Type", job.type_display) +
        metaTile("Pay", job.salary_display) +
        metaTile("Source", job.source) +
      "</div></div>";

    var applyBtn = $("detailApplyBtn");
    applyBtn.href = job.redirect_url;
    syncDetailSave();
    openSheet(detailSheet);
  }

  function metaTile(k, v) {
    return '<div class="meta-tile"><div class="meta-k">' + esc(k) + '</div><div class="meta-v">' + esc(v || "—") + "</div></div>";
  }

  function syncDetailSave() {
    $("detailSaveBtn").classList.toggle("active", !!(detailJob && isSaved(detailJob)));
  }

  $("detailSaveBtn").addEventListener("click", function () {
    if (!detailJob) return;
    if (isSaved(detailJob)) removeSaved(detailJob);
    else { addSaved(detailJob); toast('Shortlisted <span class="tick">✓</span>'); }
    syncDetailSave();
  });

  $("detailApplyBtn").addEventListener("click", function () {
    if (!detailJob) return;
    markApplied(detailJob);
    toast("Good luck out there 🍀");
  });

  // =======================================================================
  //  Saved / applied
  // =======================================================================
  function isSaved(job) {
    return saved.some(function (j) { return j.redirect_url === job.redirect_url; });
  }
  function addSaved(job) {
    if (isSaved(job)) return;
    saved.unshift(job);
    persist("align.saved", saved);
    updateSavedBadge(true);
  }
  function removeSaved(job) {
    saved = saved.filter(function (j) { return j.redirect_url !== job.redirect_url; });
    persist("align.saved", saved);
    updateSavedBadge(false);
  }
  function markApplied(job) {
    if (!applied.some(function (j) { return j.redirect_url === job.redirect_url; })) {
      applied.unshift(job);
      persist("align.applied", applied);
    }
  }
  function updateSavedBadge(pulse) {
    var badge = $("savedCount");
    badge.textContent = String(saved.length);
    badge.hidden = saved.length === 0;
    if (pulse && hasGSAP && !REDUCED_MOTION) {
      gsap.fromTo("#profileBtn", { scale: 0.86 }, { scale: 1, duration: 0.4, ease: "back.out(2.5)" });
    }
  }
  updateSavedBadge(false);

  // =======================================================================
  //  Profile sheet
  // =======================================================================
  function renderProfile() {
    var list = $("profileList");
    var items = profileTab === "saved" ? saved : applied;
    $("tabSaved").classList.toggle("active", profileTab === "saved");
    $("tabApplied").classList.toggle("active", profileTab === "applied");
    $("tabSaved").setAttribute("aria-selected", profileTab === "saved");
    $("tabApplied").setAttribute("aria-selected", profileTab === "applied");

    if (!items.length) {
      list.innerHTML =
        '<div class="profile-empty">' +
        (profileTab === "saved"
          ? "Nothing shortlisted yet.<br/>Swipe right on a job you like — it'll wait for you here."
          : "No applications yet.<br/>When you tap Apply on a job, we'll keep track of it here.") +
        "</div>";
      return;
    }
    list.innerHTML = items
      .map(function (j) {
        var t = tintFor(j.company || "?");
        var end =
          profileTab === "applied"
            ? '<span class="jr-applied">Applied ✓</span>'
            : '<a class="jr-apply" href="' + encodeURI(j.redirect_url) + '" target="_blank" rel="noopener" data-url="' + esc(j.redirect_url) + '">Apply</a>';
        return (
          '<div class="job-row">' +
          '<div class="logo-tile" style="background:' + t[0] + ";color:" + t[1] + '">' + esc(j.initials) + "</div>" +
          '<div class="jr-body"><div class="jr-title">' + esc(j.title) + '</div><div class="jr-sub">' + esc(j.company) + " · " + esc(j.salary_display) + "</div></div>" +
          end +
          "</div>"
        );
      })
      .join("");
  }

  $("profileList").addEventListener("click", function (e) {
    var a = e.target.closest(".jr-apply");
    if (a) {
      var job = saved.find(function (j) { return j.redirect_url === a.dataset.url; });
      if (job) markApplied(job);
    }
  });

  $("tabSaved").addEventListener("click", function () { profileTab = "saved"; renderProfile(); });
  $("tabApplied").addEventListener("click", function () { profileTab = "applied"; renderProfile(); });

  function openProfile() {
    renderProfile();
    $("subBadge").textContent = CONFIG.paywallActive && !CONFIG.isPaid ? "Locked" : "Unlocked";
    openSheet(profileSheet);
  }
  $("profileBtn").addEventListener("click", openProfile);
  $("doneMatches").addEventListener("click", openProfile);

  // =======================================================================
  //  Sheets
  // =======================================================================
  function openSheet(sheet) {
    sheet.hidden = false;
    var panel = sheet.querySelector(".sheet-panel");
    if (hasGSAP && !REDUCED_MOTION) {
      gsap.fromTo(sheet.querySelector(".sheet-backdrop"), { opacity: 0 }, { opacity: 1, duration: 0.25 });
      gsap.fromTo(panel, { y: 60, opacity: 0 }, { y: 0, opacity: 1, duration: 0.42, ease: "power3.out" });
    }
  }
  function closeSheet(sheet) {
    var panel = sheet.querySelector(".sheet-panel");
    if (hasGSAP && !REDUCED_MOTION) {
      gsap.to(panel, {
        y: 60, opacity: 0, duration: 0.28, ease: "power2.in",
        onComplete: function () { sheet.hidden = true; gsap.set(panel, { clearProps: "all" }); },
      });
    } else sheet.hidden = true;
  }

  document.querySelectorAll("[data-close-sheet]").forEach(function (el) {
    el.addEventListener("click", function () {
      closeSheet(el.closest(".sheet"));
    });
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      [detailSheet, profileSheet].forEach(function (s) { if (!s.hidden) closeSheet(s); });
    }
  });

  // =======================================================================
  //  Paywall
  // =======================================================================
  var paywallPayBtn = $("paywallPayBtn");

  function openPaywall() {
    $("paywallPrice").textContent = CONFIG.price || "£1";
    $("paywallBtnLabel").textContent = "Unlock Align — " + (CONFIG.price || "£1");
    openSheet(paywallOverlay);
  }
  function closePaywall() { closeSheet(paywallOverlay); }

  paywallPayBtn.addEventListener("click", function () {
    paywallPayBtn.disabled = true;
    $("paywallBtnLabel").textContent = "One moment…";
    fetch("/api/checkout", { method: "POST" })
      .then(function (r) { return r.json(); })
      .then(function (payload) {
        if (payload.unlocked) { closePaywall(); runSearch(); return; }
        if (payload.ok && payload.checkout_url) { window.location.href = payload.checkout_url; return; }
        throw new Error(payload.error || "Checkout unavailable.");
      })
      .catch(function (err) {
        $("paywallBtnLabel").textContent = "Unlock Align — " + (CONFIG.price || "£1");
        paywallPayBtn.disabled = false;
        toast(err.message || "Couldn't start checkout — try again.");
      });
  });
  $("paywallLater").addEventListener("click", closePaywall);

  (function handlePaymentReturn() {
    var params = new URLSearchParams(window.location.search);
    if (params.get("paid") === "1") {
      history.replaceState({}, "", window.location.pathname);
      CONFIG.isPaid = true;
      toast('Align unlocked <span class="tick">✓</span> Welcome in.');
    } else if (params.get("pay") === "failed") {
      history.replaceState({}, "", window.location.pathname);
      toast("Payment didn't go through — you can try again anytime.");
    } else if (params.get("pay") === "cancelled") {
      history.replaceState({}, "", window.location.pathname);
    }
  })();

  // =======================================================================
  //  Controls
  // =======================================================================
  $("passBtn").addEventListener("click", function () { swipe("pass"); });
  $("saveBtn").addEventListener("click", function () { swipe("save"); });
  $("viewBtn").addEventListener("click", function () {
    var card = topCard();
    if (card) openDetail(card._job);
  });

  document.addEventListener("keydown", function (e) {
    if (deckView.hidden || deck.hidden || !detailSheet.hidden || !profileSheet.hidden) return;
    if (e.key === "ArrowLeft") swipe("pass");
    else if (e.key === "ArrowRight") swipe("save");
    else if (e.key === "ArrowUp") {
      var card = topCard();
      if (card) openDetail(card._job);
    }
  });

  $("backBtn").addEventListener("click", function () { showView("home"); });
  $("emptyBack").addEventListener("click", function () { showView("home"); });
  $("errorRetry").addEventListener("click", runSearch);
  $("doneRestart").addEventListener("click", function () { showView("home"); });

  // =======================================================================
  //  Toast
  // =======================================================================
  var toastTimer = null;
  function toast(html) {
    toastEl.innerHTML = html;
    toastEl.hidden = false;
    if (hasGSAP && !REDUCED_MOTION) {
      gsap.fromTo(toastEl, { y: 14, opacity: 0 }, { y: 0, opacity: 1, duration: 0.3, ease: "power3.out" });
    }
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      if (hasGSAP && !REDUCED_MOTION) {
        gsap.to(toastEl, { opacity: 0, duration: 0.25, onComplete: function () { toastEl.hidden = true; } });
      } else toastEl.hidden = true;
    }, 2200);
  }

  // =======================================================================
  //  Utils
  // =======================================================================
  function esc(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
})();
