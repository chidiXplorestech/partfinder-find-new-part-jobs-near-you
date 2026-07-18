/**
 * PartFinder — swipe-deck controller for the results page.
 *
 * Progressive enhancement: without JavaScript the cards simply stack and every
 * listing stays reachable. With JS, one card shows at a time (with peeked cards
 * behind for depth) and the Pass / Save / Apply bar advances the deck, matching
 * the Tinder-style swipe layout.
 */
(function () {
    "use strict";

    var deck = document.getElementById("deck");
    if (!deck) {
        return;
    }

    var cards = Array.prototype.slice.call(deck.querySelectorAll(".job-card"));
    var emptyState = document.getElementById("deckEmpty");
    var swipeBar = document.getElementById("swipeBar");
    var hint = document.getElementById("deckHint");
    var btnPass = document.getElementById("btnPass");
    var btnSave = document.getElementById("btnSave");
    var btnApply = document.getElementById("btnApply");

    var index = 0;

    /** Position the top card and up to two peeked cards behind it. */
    function layout() {
        cards.forEach(function (card, i) {
            var depth = i - index;
            if (depth < 0 || depth > 2) {
                card.style.display = "none";
                card.classList.remove("is-top");
                return;
            }
            card.style.display = "";
            card.style.zIndex = String(cards.length - depth);
            card.style.transform =
                "translateY(" + depth * 12 + "px) scale(" + (1 - depth * 0.04) + ")";
            card.style.opacity = depth === 0 ? "1" : "0.85";
            card.classList.toggle("is-top", depth === 0);
        });

        if (index >= cards.length) {
            finish();
        }
    }

    /** Reveal the "all caught up" state and retire the controls. */
    function finish() {
        if (emptyState) {
            emptyState.hidden = false;
        }
        if (swipeBar) {
            swipeBar.style.display = "none";
        }
        if (hint) {
            hint.style.display = "none";
        }
    }

    /** Animate the current card out in a direction, then advance. */
    function advance(direction) {
        var card = cards[index];
        if (!card) {
            return;
        }
        card.classList.add("gone-" + direction);
        index += 1;
        window.setTimeout(layout, 260);
    }

    if (btnPass) {
        btnPass.addEventListener("click", function () {
            advance("left");
        });
    }
    if (btnSave) {
        btnSave.addEventListener("click", function () {
            advance("up");
        });
    }
    if (btnApply) {
        btnApply.addEventListener("click", function () {
            var card = cards[index];
            if (card && card.dataset.url) {
                window.open(card.dataset.url, "_blank", "noopener");
            }
            advance("right");
        });
    }

    layout();
})();
