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
  var profile = load("align.profile", {}); // { name, email, postcode, origin:{lat,lng} }

  function startApp() {
    onboarding.hidden = true;
    topbar.hidden = false;
    $("tabbar").hidden = false;
    document.body.classList.add("has-tabbar");
    showView("home");
    persist("align.onboarded", true);
    showHeroPill();
    updateSavedBadge(false);
    if (hasGSAP && !REDUCED_MOTION) {
      gsap.from(".hero-pill", { y: 10, opacity: 0, duration: 0.5, ease: "power3.out" });
      gsap.from(".hero-eyebrow, .hero-title", { y: 14, opacity: 0, duration: 0.5, stagger: 0.07, delay: 0.05, ease: "power3.out" });
      gsap.from(".setup .field, .setup .btn-cta", { y: 16, opacity: 0, duration: 0.45, stagger: 0.06, delay: 0.14, ease: "power3.out" });
    }
  }

  function showHeroPill() {
    var lastCount = load("align.lastCount", null);
    var place = profile.postcode ? " in " + profile.postcode : "";
    var text = (typeof lastCount === "number" && lastCount > 0)
      ? lastCount + " local jobs matched last time"
      : "Fresh local jobs" + place + ", updated daily";
    $("heroPillText").textContent = text;
    $("heroPill").hidden = false;
    if (profile.name) $("greeting").textContent = greetWord() + ", " + profile.name.split(" ")[0];
    syncLocationUI();
  }

  // Keep the home postcode field + fine-print in sync with the stored location.
  function syncLocationUI() {
    var input = $("homePostcode");
    if (input && profile.postcode && !input.value) input.value = profile.postcode;
    var fine = $("finePlace");
    if (fine) fine.textContent = profile.postcode || "your postcode";
  }

  function greetWord() {
    var h = new Date().getHours();
    return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  }

  // ---- Onboarding step machine ----
  var obSteps = [];
  var obIndex = 0;

  function obShow(i) {
    obIndex = Math.max(0, Math.min(obSteps.length - 1, i));
    obSteps.forEach(function (s, n) { s.hidden = n !== obIndex; });
    var el = obSteps[obIndex];
    if (hasGSAP && !REDUCED_MOTION) {
      el.classList.remove("entering"); void el.offsetWidth; el.classList.add("entering");
    }
    if (el.dataset.step === "splash") runSplash();
    updateObProgress();
    var focusable = el.querySelector("input");
    if (focusable && el.dataset.step !== "splash") setTimeout(function () { focusable.focus(); }, 260);
  }

  function updateObProgress() {
    var prog = $("obProgress"), fill = $("obProgressFill");
    var step = obSteps[obIndex].dataset.step;
    // Hide the bar on splash and the final "done" screen; show progress between.
    if (step === "splash" || step === "done") { prog.classList.remove("show"); return; }
    prog.classList.add("show");
    var last = obSteps.length - 1; // index of 'done'
    fill.style.width = Math.round((obIndex / last) * 100) + "%";
    // Reflect the current intro slide in its own dash row.
    var dashes = obSteps[obIndex].querySelectorAll(".ob-dashes span");
    if (dashes.length) {
      var slideNum = 0;
      for (var k = 0; k <= obIndex; k++) if (obSteps[k].dataset.step === "slide") slideNum++;
      dashes.forEach(function (d, n) { d.classList.toggle("on", n === slideNum - 1); });
    }
  }
  function obNext() { obShow(obIndex + 1); }
  function obBack() { obShow(obIndex - 1); }

  function runSplash() {
    var fill = $("splashBarFill");
    if (hasGSAP && !REDUCED_MOTION) {
      gsap.fromTo(fill, { width: "0%" }, { width: "100%", duration: 4, ease: "none" });
    } else { fill.style.width = "100%"; }
    clearTimeout(runSplash._t);
    runSplash._t = setTimeout(function () { if (obSteps[obIndex].dataset.step === "splash") obNext(); }, 4000);
  }

  (function initOnboarding() {
    // Load any photos the user has dropped into static/img/onboarding/.
    document.querySelectorAll(".ob-photo[data-img]").forEach(function (ph) {
      var name = ph.getAttribute("data-img");
      var img = new Image();
      img.onload = function () { ph.style.backgroundImage = "url('/static/img/onboarding/" + name + ".jpg')"; };
      img.src = "/static/img/onboarding/" + name + ".jpg";
    });

    if (load("align.onboarded", false)) { startApp(); return; }
    onboarding.hidden = false;
    obSteps = Array.prototype.slice.call(document.querySelectorAll("#onboarding .ob-step"));

    // Generic slide back/next arrows
    document.querySelectorAll("#onboarding [data-ob-next]").forEach(function (b) { b.addEventListener("click", obNext); });
    document.querySelectorAll("#onboarding [data-ob-back]").forEach(function (b) { b.addEventListener("click", obBack); });

    // Swipe left/right to navigate the intro slides.
    obSteps.forEach(function (step) {
      if (step.dataset.step !== "slide") return;
      var x0 = null;
      step.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; }, { passive: true });
      step.addEventListener("touchend", function (e) {
        if (x0 === null) return;
        var dx = e.changedTouches[0].clientX - x0; x0 = null;
        if (Math.abs(dx) < 50) return;
        if (dx < 0) obNext(); else obBack();
      }, { passive: true });
    });

    wireOnboardingForms();
    obShow(0);
  })();

  function wireOnboardingForms() {
    // --- Postcode ---
    var pcInput = $("obPostcode"), pcMsg = $("obPostcodeMsg");
    if (profile.postcode) pcInput.value = profile.postcode;
    $("obGeoBtn").addEventListener("click", function () {
      if (!navigator.geolocation) return;
      pcMsg.hidden = false; pcMsg.className = "ob-hint"; pcMsg.textContent = "Finding your location…";
      navigator.geolocation.getCurrentPosition(function (pos) {
        profile.origin = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        pcMsg.className = "ob-hint ok"; pcMsg.textContent = "Location found ✓";
      }, function () { pcMsg.className = "ob-hint danger"; pcMsg.textContent = "Couldn't get location — enter a postcode instead."; });
    });
    $("obPostcodeNext").addEventListener("click", function () {
      var pc = pcInput.value.trim();
      if (!pc && !profile.origin) { pcMsg.hidden = false; pcMsg.className = "ob-hint danger"; pcMsg.textContent = "Enter your postcode to find nearby jobs."; return; }
      var btn = this; btn.disabled = true; var lbl = btn.textContent; btn.textContent = "Finding jobs…";
      pcMsg.hidden = true;
      if (!pc) { profile.postcode = ""; persist("align.profile", profile); btn.disabled = false; btn.textContent = lbl; obNext(); return; }
      fetch("/api/geocode?postcode=" + encodeURIComponent(pc))
        .then(function (r) { return r.json(); })
        .then(function (d) {
          btn.disabled = false; btn.textContent = lbl;
          if (!d.ok) { pcMsg.hidden = false; pcMsg.className = "ob-hint danger"; pcMsg.textContent = d.error || "We couldn't find that postcode."; return; }
          profile.postcode = d.postcode; profile.origin = { lat: d.lat, lng: d.lng };
          persist("align.profile", profile);
          obNext();
        })
        .catch(function () { btn.disabled = false; btn.textContent = lbl; pcMsg.hidden = false; pcMsg.className = "ob-hint danger"; pcMsg.textContent = "Network error — try again."; });
    });

    // --- Name ---
    var nameInput = $("obName");
    if (profile.name) nameInput.value = profile.name;
    $("obNameNext").addEventListener("click", function () {
      profile.name = nameInput.value.trim();
      persist("align.profile", profile);
      obNext();
    });

    // --- Account ---
    var email = $("obEmail"), pw = $("obPassword"), tick = $("obEmailTick"), acctMsg = $("obAccountMsg");
    var rules = { len: function (v) { return v.length >= 8; }, num: function (v) { return /\d/.test(v); },
      special: function (v) { return /[^A-Za-z0-9]/.test(v); }, case: function (v) { return /[a-z]/.test(v) && /[A-Z]/.test(v); } };
    function emailValid(v) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v); }
    function refreshPw() {
      var v = pw.value, allOk = true;
      document.querySelectorAll("#pwRules li").forEach(function (li) {
        var ok = rules[li.getAttribute("data-rule")](v);
        li.classList.toggle("met", ok); if (!ok) allOk = false;
      });
      return allOk;
    }
    var confirm = $("obConfirm");
    email.addEventListener("input", function () { tick.hidden = !emailValid(email.value.trim()); });
    pw.addEventListener("input", refreshPw);
    $("obPwToggle").addEventListener("click", function () { pw.type = pw.type === "password" ? "text" : "password"; });
    $("obConfirmToggle").addEventListener("click", function () { confirm.type = confirm.type === "password" ? "text" : "password"; });
    $("obLogin").addEventListener("click", function () {
      acctMsg.hidden = false; acctMsg.className = "ob-hint"; acctMsg.textContent = "Enter your email and password above, then tap Create account to sign in.";
    });
    $("obAccountNext").addEventListener("click", function () {
      var e = email.value.trim(), p = pw.value;
      if (!emailValid(e)) { acctMsg.hidden = false; acctMsg.className = "ob-hint danger"; acctMsg.textContent = "Please enter a valid email address."; return; }
      if (!refreshPw()) { acctMsg.hidden = false; acctMsg.className = "ob-hint danger"; acctMsg.textContent = "Your password doesn't meet all the rules yet."; return; }
      if (confirm.value !== p) { acctMsg.hidden = false; acctMsg.className = "ob-hint danger"; acctMsg.textContent = "Passwords don't match."; return; }
      var btn = this; btn.disabled = true; var lbl = btn.textContent; btn.textContent = "Creating…"; acctMsg.hidden = true;
      fetch("/api/signup", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: e, password: p, name: profile.name || "" }) })
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          btn.disabled = false; btn.textContent = lbl;
          if (!res.d.ok) { acctMsg.hidden = false; acctMsg.className = "ob-hint danger"; acctMsg.textContent = res.d.error || "Couldn't create your account."; return; }
          profile.email = e; persist("align.profile", profile);
          obNext();
        })
        .catch(function () { btn.disabled = false; btn.textContent = lbl; acctMsg.hidden = false; acctMsg.className = "ob-hint danger"; acctMsg.textContent = "Network error — try again."; });
    });

    // --- Offer / paywall ---
    $("obOfferNext").addEventListener("click", function () {
      if (CONFIG.paywallActive && !CONFIG.isPaid) {
        var btn = this; btn.disabled = true; btn.textContent = "One moment…";
        fetch("/api/checkout", { method: "POST" }).then(function (r) { return r.json(); }).then(function (p) {
          if (p.checkout_url) { window.location.href = p.checkout_url; return; }
          btn.disabled = false; btn.textContent = "Get started for £1"; obNext();
        }).catch(function () { btn.disabled = false; btn.textContent = "Get started for £1"; obNext(); });
      } else { obNext(); }
    });

    // --- Done ---
    $("obStart").addEventListener("click", startApp);
  }

  // ---- Greeting ----------------------------------------------------------
  (function greet() {
    var h = new Date().getHours();
    $("greeting").textContent = h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
  })();

  // =======================================================================
  //  View / state management
  // =======================================================================
  var discoverHasDeck = false;
  function showView(name) {
    // Discover is the home/deck pair; showing either keeps you on the Discover tab.
    homeView.hidden = name !== "home";
    deckView.hidden = name !== "deck";
    var sv = $("savedView"), av = $("appliedView"), cv = $("accountView");
    if (sv) sv.hidden = true;
    if (av) av.hidden = true;
    if (cv) cv.hidden = true;
    discoverHasDeck = name === "deck";
    if (typeof setActiveTab === "function") setActiveTab("discover");
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
  form.addEventListener("submit", function (e) { e.preventDefault(); resolveThenSearch(); });

  function collectQuery() {
    var data = new FormData(form);
    return {
      category: data.get("category"),
      days: data.getAll("days"),
      radius: parseInt(data.get("radius"), 10) || 5,
      postcode: profile.postcode || null,
      origin: profile.origin || null,
    };
  }

  // Server-side postcode lookup, shared by onboarding and home.
  function geocode(pc) {
    return fetch("/api/geocode?postcode=" + encodeURIComponent(pc)).then(function (r) { return r.json(); });
  }

  // Home flow: if the user typed/changed a postcode, resolve it before searching.
  function resolveThenSearch() {
    var input = $("homePostcode");
    var pc = input ? input.value.trim() : "";
    var msg = $("homePostcodeMsg");
    if (msg) msg.hidden = true;

    if (!pc) {
      // No postcode entered — need one to search locally.
      if (!profile.origin) {
        if (msg) { msg.hidden = false; msg.className = "ob-hint danger"; msg.textContent = "Enter your postcode to find nearby jobs."; }
        if (input) input.focus();
        return;
      }
      runSearch(); return;
    }
    // Already resolved this exact postcode — search straight away.
    if (profile.postcode && pc.toUpperCase().replace(/\s/g, "") === profile.postcode.toUpperCase().replace(/\s/g, "") && profile.origin) {
      runSearch(); return;
    }
    var btn = $("findBtn"); var lbl = btn.textContent; btn.disabled = true; btn.textContent = "Finding you…";
    geocode(pc).then(function (d) {
      btn.disabled = false; btn.textContent = lbl;
      if (!d.ok) { if (msg) { msg.hidden = false; msg.className = "ob-hint danger"; msg.textContent = d.error || "We couldn't find that postcode."; } return; }
      profile.postcode = d.postcode; profile.origin = { lat: d.lat, lng: d.lng };
      persist("align.profile", profile);
      syncLocationUI();
      runSearch();
    }).catch(function () {
      btn.disabled = false; btn.textContent = lbl;
      if (msg) { msg.hidden = false; msg.className = "ob-hint danger"; msg.textContent = "Network error — try again."; }
    });
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
        persist("align.lastCount", totalInSearch);
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
    ["#FFEDE0", "#D14E00"], // mastercard orange
    ["#FDF1DC", "#8F5A08"], // amber
    ["#EDEBE6", "#3A3630"], // warm black
    ["#FCEAE8", "#B33530"], // softened red
    ["#F1EFE9", "#55524D"], // warm grey
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
    // Start empty; the ring is drawn to its target when the card enters (animateRing).
    return (
      '<div class="match-ring" title="Match score" aria-label="' + pct + '% match" data-pct="' + pct + '">' +
      '<svg width="46" height="46" viewBox="0 0 46 46" aria-hidden="true">' +
      '<circle class="ring-bg" cx="23" cy="23" r="' + r + '" fill="none" stroke-width="4"/>' +
      '<circle class="ring-fg" cx="23" cy="23" r="' + r + '" fill="none" stroke-width="4" stroke-dasharray="' + c + '" stroke-dashoffset="' + c + '"/>' +
      "</svg>" +
      '<span class="ring-label" data-count="' + pct + '">0</span>' +
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
    if (top) animateRing(top);
    enableDrag();
  }

  // Draw the match ring + count the % up when a card becomes active.
  function animateRing(card) {
    var ring = card.querySelector(".match-ring");
    if (!ring || ring._drawn) return;
    ring._drawn = true;
    var fg = ring.querySelector(".ring-fg");
    var label = ring.querySelector(".ring-label");
    var pct = parseInt(ring.getAttribute("data-pct"), 10) || 0;
    var r = 19, c = 2 * Math.PI * r, off = c * (1 - pct / 100);
    if (!hasGSAP || REDUCED_MOTION) {
      fg.setAttribute("stroke-dashoffset", off);
      label.textContent = pct;
      return;
    }
    gsap.to(fg, { attr: { "stroke-dashoffset": off }, duration: 0.9, ease: "power2.out", delay: 0.15 });
    var counter = { v: 0 };
    gsap.to(counter, { v: pct, duration: 0.9, ease: "power2.out", delay: 0.15,
      onUpdate: function () { label.textContent = Math.round(counter.v); } });
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
    var top = topCard();
    if (top) animateRing(top);
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
    var job = detailJob;
    markApplied(job);
    // The <a> opens the employer tab natively; confirm it with the sent moment.
    closeSheet(detailSheet);
    setTimeout(function () { showApplicationSent(job); }, 180);
  });

  // ---- Application-sent moment ----
  var sentOverlay = $("sentOverlay");
  var sentJob = null;
  function showApplicationSent(job) {
    sentJob = job;
    $("sentCompany").textContent = job.company || "the employer";
    sentOverlay.hidden = false;
    if (hasGSAP && !REDUCED_MOTION) {
      gsap.fromTo(sentOverlay.querySelector(".sheet-backdrop"), { opacity: 0 }, { opacity: 1, duration: 0.25 });
      gsap.fromTo(".sent-card", { y: 24, scale: 0.94, opacity: 0 }, { y: 0, scale: 1, opacity: 1, duration: 0.45, ease: "back.out(1.6)" });
      gsap.fromTo(".sent-art svg", { rotation: -8, y: 6 }, { rotation: 6, y: 0, duration: 0.7, ease: "sine.inOut" });
    }
  }
  function hideApplicationSent() {
    if (hasGSAP && !REDUCED_MOTION) {
      gsap.to(".sent-card", { y: 24, opacity: 0, duration: 0.25, ease: "power2.in",
        onComplete: function () { sentOverlay.hidden = true; gsap.set(".sent-card", { clearProps: "all" }); } });
    } else sentOverlay.hidden = true;
  }
  $("sentKeep").addEventListener("click", hideApplicationSent);
  $("sentApplications").addEventListener("click", function () {
    hideApplicationSent();
    setTimeout(function () { showSection("applied"); }, 260);
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
    var badge = $("tabSavedBadge");
    if (badge) { badge.textContent = String(saved.length); badge.hidden = saved.length === 0; }
    if (pulse && hasGSAP && !REDUCED_MOTION) {
      gsap.fromTo('.tab[data-tab="saved"]', { scale: 0.9 }, { scale: 1, duration: 0.4, ease: "back.out(2.5)" });
    }
    if (currentTab === "saved") renderSaved();
  }

  // =======================================================================
  //  Sections: Saved · Applications · You
  // =======================================================================
  function jobRowHtml(j, isApplied) {
    var t = tintFor(j.company || "?");
    var end = isApplied
      ? '<span class="jr-applied">Applied ✓</span>'
      : '<a class="jr-apply" href="' + encodeURI(j.redirect_url) + '" target="_blank" rel="noopener" data-url="' + esc(j.redirect_url) + '">Apply</a>';
    return (
      '<div class="job-row">' +
      '<div class="logo-tile" style="background:' + t[0] + ";color:" + t[1] + '">' + esc(j.initials) + "</div>" +
      '<div class="jr-body"><div class="jr-title">' + esc(j.title) + '</div><div class="jr-sub">' + esc(j.company) + " · " + esc(j.salary_display) + "</div></div>" +
      end + "</div>"
    );
  }
  function renderSaved() {
    var list = $("savedList");
    $("savedSub").textContent = saved.length
      ? saved.length + (saved.length === 1 ? " role" : " roles") + " shortlisted."
      : "Roles you've shortlisted.";
    list.innerHTML = saved.length
      ? saved.map(function (j) { return jobRowHtml(j, false); }).join("")
      : '<div class="section-empty">Nothing shortlisted yet.<br/>Swipe right on a job you like — it\'ll wait for you here.</div>';
  }
  function renderApplied() {
    var list = $("appliedList");
    list.innerHTML = applied.length
      ? applied.map(function (j) { return jobRowHtml(j, true); }).join("")
      : '<div class="section-empty">No applications yet.<br/>When you tap Apply on a job, we\'ll keep track of it here.</div>';
  }
  function renderAccount() {
    var nm = (profile.name || "").trim();
    $("acctName").textContent = nm || "Your account";
    $("acctAvatar").textContent = (nm[0] || "A").toUpperCase();
    $("acctEmail").textContent = profile.email || "Not signed in";
    $("acctPostcode").textContent = profile.postcode || "Not set";
    $("acctPlan").textContent = (CONFIG.paywallActive && !CONFIG.isPaid) ? "Free preview" : "Unlocked";
  }
  $("savedList").addEventListener("click", function (e) {
    var a = e.target.closest(".jr-apply");
    if (!a) return;
    var job = saved.find(function (j) { return j.redirect_url === a.dataset.url; });
    if (job) { markApplied(job); toast("Good luck out there 🍀"); }
  });

  // ---- Tab bar / section switching ----
  var currentTab = "discover";
  function setActiveTab(name) {
    currentTab = name;
    document.querySelectorAll("#tabbar .tab").forEach(function (t) {
      t.classList.toggle("active", t.getAttribute("data-tab") === name);
    });
  }
  function showSection(name) {
    homeView.hidden = true; deckView.hidden = true;
    $("savedView").hidden = true; $("appliedView").hidden = true; $("accountView").hidden = true;
    if (name === "discover") {
      if (discoverHasDeck) { deckView.hidden = false; } else { homeView.hidden = false; }
    } else if (name === "saved") { renderSaved(); $("savedView").hidden = false; }
    else if (name === "applied") { renderApplied(); $("appliedView").hidden = false; }
    else if (name === "account") { renderAccount(); $("accountView").hidden = false; }
    setActiveTab(name);
  }
  document.querySelectorAll("#tabbar .tab").forEach(function (t) {
    t.addEventListener("click", function () { showSection(t.getAttribute("data-tab")); });
  });
  $("doneMatches").addEventListener("click", function () { showSection("saved"); });
  $("acctNewSearch").addEventListener("click", function () { discoverHasDeck = false; showSection("discover"); showHeroPill(); });
  $("acctChangePostcode").addEventListener("click", function () {
    discoverHasDeck = false; showSection("discover"); showHeroPill();
    var input = $("homePostcode"); if (input) { input.focus(); input.select(); }
  });

  // Home "use my location" -> browser geolocation -> reverse to nearest postcode area
  $("homeGeoBtn").addEventListener("click", function () {
    var msg = $("homePostcodeMsg");
    if (!navigator.geolocation) { if (msg) { msg.hidden = false; msg.className = "ob-hint danger"; msg.textContent = "Location isn't available on this device."; } return; }
    if (msg) { msg.hidden = false; msg.className = "ob-hint"; msg.textContent = "Finding your location…"; }
    navigator.geolocation.getCurrentPosition(function (pos) {
      fetch("/api/geocode?lat=" + pos.coords.latitude + "&lng=" + pos.coords.longitude)
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d.ok) { if (msg) { msg.className = "ob-hint danger"; msg.textContent = d.error || "Couldn't find your postcode — type it instead."; } return; }
          profile.postcode = d.postcode; profile.origin = { lat: d.lat, lng: d.lng };
          persist("align.profile", profile);
          var input = $("homePostcode"); if (input) input.value = d.postcode;
          syncLocationUI();
          if (msg) { msg.className = "ob-hint ok"; msg.textContent = "Found you near " + d.postcode + " ✓"; }
        })
        .catch(function () { if (msg) { msg.className = "ob-hint danger"; msg.textContent = "Network error — type a postcode instead."; } });
    }, function () {
      if (msg) { msg.className = "ob-hint danger"; msg.textContent = "Couldn't get location — type a postcode instead."; }
    });
  });
  $("acctLogout").addEventListener("click", function () {
    try { localStorage.removeItem("align.onboarded"); } catch (e) {}
    location.reload();
  });
  updateSavedBadge(false);

  // =======================================================================
  //  Notifications (real browser-permission trigger)
  // =======================================================================
  function notifsOn() {
    return load("align.notif", false) ||
      (typeof Notification !== "undefined" && Notification.permission === "granted");
  }
  function renderNotifs() {
    var on = notifsOn();
    var toggle = $("notifToggle");
    toggle.textContent = on ? "On" : "Enable";
    toggle.classList.toggle("on", on);
    $("notifAlertD").textContent = on
      ? "You're all set — we'll ping you when fresh jobs drop near you."
      : "Turn on alerts and we'll ping you when fresh jobs drop near you.";
    $("notifList").innerHTML =
      '<div class="notif-empty">No alerts yet.<br/>New matches near ' +
      esc(profile.postcode || "you") + " will show up here.</div>";
  }
  $("bellBtn").addEventListener("click", function () {
    renderNotifs();
    openSheet($("notifSheet"));
  });
  $("notifToggle").addEventListener("click", function () {
    if (typeof Notification === "undefined") { persist("align.notif", true); renderNotifs(); toast("Job alerts on"); return; }
    if (Notification.permission === "granted") { persist("align.notif", true); renderNotifs(); toast("Job alerts already on"); return; }
    Notification.requestPermission().then(function (p) {
      if (p === "granted") {
        persist("align.notif", true);
        toast('Job alerts on <span class="tick">✓</span>');
        try { new Notification("Align", { body: "You'll be notified when fresh jobs drop near you." }); } catch (e) {}
      } else {
        toast("Allow notifications in your browser to enable alerts.");
      }
      renderNotifs();
    });
  });

  // =======================================================================
  //  Sheets
  // =======================================================================
  function openSheet(sheet) {
    sheet.hidden = false;
    var panel = sheet.querySelector(".sheet-panel");
    var backdrop = sheet.querySelector(".sheet-backdrop");
    if (hasGSAP && !REDUCED_MOTION) {
      if (backdrop) gsap.fromTo(backdrop, { opacity: 0 }, { opacity: 1, duration: 0.25 });
      var fromY = panel.classList.contains("sheet-full") ? 20 : 60;
      gsap.fromTo(panel, { y: fromY, opacity: 0 }, { y: 0, opacity: 1, duration: 0.42, ease: "power3.out" });
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

  function goHome() { showView("home"); showHeroPill(); }
  $("backBtn").addEventListener("click", goHome);
  $("emptyBack").addEventListener("click", goHome);
  $("errorRetry").addEventListener("click", runSearch);
  $("doneRestart").addEventListener("click", goHome);

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
