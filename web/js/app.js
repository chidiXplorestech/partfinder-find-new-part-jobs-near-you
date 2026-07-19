/*
 * PartFinder — UI controller (GSAP swipe deck).
 * Home form -> live Adzuna fetch -> filter/rank -> Tinder-style swipe deck.
 * Never fabricates jobs: shows explicit loading / error / empty / no-key states.
 */
(function () {
    "use strict";

    if (window.gsap && window.Draggable) {
        gsap.registerPlugin(Draggable);
    }

    const els = {
        homeView: document.getElementById("homeView"),
        resultsView: document.getElementById("resultsView"),
        form: document.getElementById("searchForm"),
        categoryGrid: document.getElementById("categoryGrid"),
        resultsTitle: document.getElementById("resultsTitle"),
        resultsMeta: document.getElementById("resultsMeta"),
        deck: document.getElementById("deck"),
        deckStatus: document.getElementById("deckStatus"),
        swipeBar: document.getElementById("swipeBar"),
        deckHint: document.getElementById("deckHint"),
        btnPass: document.getElementById("btnPass"),
        btnSave: document.getElementById("btnSave"),
        btnApply: document.getElementById("btnApply"),
        newSearch: document.getElementById("newSearch"),
    };

    let deck = { cards: [], index: 0, drag: null, busy: false };

    /* ---------- build category chips from logic.js ---------- */
    CATEGORIES.forEach((c, i) => {
        const label = document.createElement("label");
        label.className = "chip";
        label.innerHTML =
            '<input type="radio" name="category" value="' + c.key + '"' + (i === 0 ? " required" : "") + ">" +
            "<span>" + c.label + "</span>";
        els.categoryGrid.appendChild(label);
    });

    /* ---------- view switching ---------- */
    function showView(name) {
        const showing = name === "results" ? els.resultsView : els.homeView;
        const hiding = name === "results" ? els.homeView : els.resultsView;
        hiding.classList.remove("active");
        showing.classList.add("active");
        window.scrollTo(0, 0);
        if (window.gsap) {
            gsap.fromTo(showing, { opacity: 0, y: 18 }, { opacity: 1, y: 0, duration: 0.35, ease: "power2.out" });
        }
    }

    /* ---------- deck status (loading / error / empty) ---------- */
    function setStatus(html) {
        els.deck.innerHTML = "";
        deck.cards = [];
        els.deckStatus.hidden = !html;
        els.deckStatus.innerHTML = html || "";
        const hasCards = !html;
        els.swipeBar.style.display = hasCards ? "" : "none";
        els.deckHint.style.display = hasCards ? "" : "none";
    }

    function errorHtml(title, body) {
        return '<h2>' + title + '</h2><p>' + body + '</p><a class="btn btn-primary" href="#" id="statusBack">Back to search</a>';
    }

    /* ---------- card markup ---------- */
    function cardEl(job) {
        const initials = (job.company || "?").slice(0, 2).toUpperCase();
        const payShort = job.pay.split("/")[0].split("(")[0].trim();
        const el = document.createElement("article");
        el.className = "job-card";
        el.dataset.url = job.url;
        el.innerHTML =
            '<div class="job-visual">' +
              '<div class="job-topbar">' +
                '<div class="topbar-left">' +
                  '<span class="company-tile">' + initials + "</span>" +
                  '<span class="source-pill">via ' + job.source + "</span>" +
                "</div>" +
                '<span class="save-btn" aria-hidden="true"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1Z"/></svg></span>' +
              "</div>" +
              '<div class="badges">' +
                '<span class="badge">' + job.employment_type + "</span>" +
                '<span class="badge badge-solid">' + job.pay.split("(")[0].trim() + "</span>" +
              "</div>" +
              '<div class="job-glass"><div class="job-glass-inner">' +
                '<div class="posted-line"><span class="posted-dot"></span>' + relativeDate(job.created) +
                  (job.distance !== null ? " · " + job.distance.toFixed(1) + " mi away" : "") + "</div>" +
                '<h2 class="job-title">' + job.title + "</h2>" +
                '<p class="job-company">' + job.company + " · " + job.location + "</p>" +
                '<div class="meta-tiles">' +
                  '<div class="meta-tile"><span>Pay</span><strong>' + payShort + "</strong></div>" +
                  '<div class="meta-tile"><span>Type</span><strong>' + job.employment_type + "</strong></div>" +
                  '<div class="meta-tile"><span>Source</span><strong>' + job.source + "</strong></div>" +
                "</div>" +
              "</div></div>" +
            "</div>";
        return el;
    }

    /* ---------- deck build + layout ---------- */
    function buildDeck(jobs) {
        setStatus("");
        deck = { cards: [], index: 0, drag: null, busy: false };
        jobs.forEach((job) => {
            const el = cardEl(job);
            els.deck.appendChild(el);
            deck.cards.push({ el: el, job: job });
        });
        if (window.gsap) {
            deck.cards.forEach((c) => gsap.set(c.el, { y: 60, opacity: 0 }));
        }
        layout();
    }

    function layout() {
        const shown = [];
        deck.cards.forEach((c, i) => {
            const depth = i - deck.index;
            if (depth < 0 || depth > 2) {
                c.el.style.display = "none";
                return;
            }
            c.el.style.display = "";
            c.el.classList.toggle("is-top", depth === 0);
            const props = { x: 0, y: depth * 14, scale: 1 - depth * 0.04, rotation: 0, opacity: depth === 0 ? 1 : 0.9, zIndex: 100 - depth };
            if (window.gsap) gsap.to(c.el, Object.assign({ duration: 0.4, ease: "power3.out" }, props));
            else Object.assign(c.el.style, {
                transform: "translateY(" + depth * 14 + "px) scale(" + (1 - depth * 0.04) + ")",
                opacity: depth === 0 ? "1" : "0.9",
                zIndex: String(100 - depth),
            });
            shown.push(c);
        });
        if (deck.index >= deck.cards.length) return finish();
        enableDrag();
    }

    function enableDrag() {
        if (!window.Draggable) return;
        if (deck.drag) { deck.drag.kill(); deck.drag = null; }
        const top = deck.cards[deck.index];
        if (!top) return;
        deck.drag = Draggable.create(top.el, {
            type: "x,y",
            onDrag: function () { gsap.set(this.target, { rotation: this.x / 18 }); },
            onDragEnd: function () {
                if (this.x > 120) swipe("right");
                else if (this.x < -120) swipe("left");
                else gsap.to(this.target, { x: 0, y: 0, rotation: 0, duration: 0.4, ease: "power2.out" });
            },
        })[0];
    }

    function swipe(direction) {
        if (deck.busy) return;
        const top = deck.cards[deck.index];
        if (!top) return;
        deck.busy = true;
        if (deck.drag) { deck.drag.kill(); deck.drag = null; }
        if (direction === "right" && top.el.dataset.url) {
            window.open(top.el.dataset.url, "_blank", "noopener");
        }
        const x = direction === "left" ? -600 : direction === "right" ? 600 : 0;
        const y = direction === "up" ? -700 : 0;
        const rot = direction === "left" ? -18 : direction === "right" ? 18 : 0;
        const done = function () { top.el.style.display = "none"; deck.index += 1; deck.busy = false; layout(); };
        if (window.gsap) gsap.to(top.el, { x: x, y: y, rotation: rot, opacity: 0, duration: 0.42, ease: "power2.in", onComplete: done });
        else done();
    }

    function finish() {
        setStatus(
            '<h2>You’re all caught up</h2><p>That’s every live match for this search. Widen your radius or try another category.</p>' +
            '<a class="btn btn-primary" href="#" id="statusBack">New search</a>'
        );
    }

    /* ---------- search flow ---------- */
    async function runSearch(criteria) {
        showView("results");
        const cat = CATEGORY_BY_KEY[criteria.category];
        els.resultsTitle.textContent = "Your " + (cat ? cat.label.replace(" Jobs", "") : "") + " matches";
        els.resultsMeta.textContent = "Searching live around " + ORIGIN.postcode + "…";
        setStatus('<div class="spinner" aria-hidden="true"></div><p>Finding live jobs near you…</p>');

        try {
            const result = await fetchAdzunaJobs(criteria);
            const jobs = processJobs(result.jobs, criteria);
            const n = jobs.length;
            els.resultsMeta.textContent =
                n + " live match" + (n === 1 ? "" : "es") + " within " + criteria.radius + " miles" +
                (criteria.days.length ? " · free " + criteria.days.join(", ") : "");
            if (!n) {
                setStatus(errorHtml("No live matches", "Nothing paying £12.71/hour and up within " + criteria.radius + " miles right now. Try a wider radius or another category."));
                return;
            }
            buildDeck(jobs);
        } catch (err) {
            els.resultsMeta.textContent = "";
            if (err.reason === "no-key") {
                setStatus(errorHtml("Add your free Adzuna key", "Live search needs an Adzuna API key. Copy <code>js/config.example.js</code> to <code>js/config.js</code> and paste your App ID + App Key from developer.adzuna.com."));
            } else if (err.reason === "cors") {
                setStatus(errorHtml("Browser blocked the request", "Your browser blocked the direct Adzuna call (CORS). Run the included Flask version (<code>python server.py</code>) for live results, or deploy behind a small proxy. See the README."));
            } else {
                setStatus(errorHtml("Live search failed", (err.message || "Please try again.") + " Check your keys and connection."));
            }
        }
    }

    /* ---------- events ---------- */
    els.form.addEventListener("submit", function (e) {
        e.preventDefault();
        const data = new FormData(els.form);
        const category = data.get("category");
        if (!category) return;
        const days = data.getAll("days");
        const radius = parseInt(data.get("radius"), 10) || 5;
        runSearch({ category: category, days: days, radius: radius });
    });

    els.btnPass.addEventListener("click", function () { swipe("left"); });
    els.btnSave.addEventListener("click", function () { swipe("up"); });
    els.btnApply.addEventListener("click", function () { swipe("right"); });
    els.newSearch.addEventListener("click", function (e) { e.preventDefault(); showView("home"); });

    // Delegated: "Back to search" links inside status cards.
    els.deckStatus.addEventListener("click", function (e) {
        if (e.target && e.target.id === "statusBack") { e.preventDefault(); showView("home"); }
    });

    // Keyboard: left = pass, right = apply.
    document.addEventListener("keydown", function (e) {
        if (!els.resultsView.classList.contains("active")) return;
        if (e.key === "ArrowLeft") swipe("left");
        else if (e.key === "ArrowRight") swipe("right");
    });
})();
