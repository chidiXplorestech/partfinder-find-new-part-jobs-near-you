/**
 * PartFinder — progressive enhancement for the search form.
 *
 * The form works without JavaScript (native radio/checkbox inputs). This script
 * only adds small conveniences: preventing a submit with no category selected
 * and giving chips a pressed-state via keyboard.
 */
(function () {
    "use strict";

    const form = document.querySelector(".search-form");
    if (!form) {
        return;
    }

    form.addEventListener("submit", function (event) {
        const category = form.querySelector('input[name="category"]:checked');
        if (!category) {
            event.preventDefault();
            const firstGroup = form.querySelector(".option-grid");
            if (firstGroup) {
                firstGroup.scrollIntoView({ behavior: "smooth", block: "center" });
            }
        }
    });
})();
