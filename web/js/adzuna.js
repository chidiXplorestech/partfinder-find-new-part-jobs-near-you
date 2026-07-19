/*
 * PartFinder — Adzuna live job fetch (browser).
 * Builds the request and normalizes results into job objects with REAL
 * `redirect_url` Apply links. Mirrors providers/adzuna.py from the Flask app.
 */

const ADZUNA_BASE = "https://api.adzuna.com/v1/api/jobs/{country}/search/1";

function adzunaConfigured() {
    const c = window.PF_CONFIG || {};
    return Boolean(c.ADZUNA_APP_ID && c.ADZUNA_APP_KEY);
}

function buildAdzunaUrl(criteria) {
    const c = window.PF_CONFIG || {};
    const category = CATEGORY_BY_KEY[criteria.category];
    const what = category ? category.keywords.join(" ") : criteria.category;

    const params = new URLSearchParams({
        app_id: c.ADZUNA_APP_ID,
        app_key: c.ADZUNA_APP_KEY,
        results_per_page: "50",
        what: what,
        where: ORIGIN.postcode,
        distance: String(criteria.radius),
        max_days_old: String(MAX_JOB_AGE_DAYS),
        sort_by: "date",
        part_time: "1",
        "content-type": "application/json",
    });
    if (category && category.adzuna) params.set("category", category.adzuna);
    if (category && category.contract) params.set("contract", "1");

    const base = ADZUNA_BASE.replace("{country}", c.ADZUNA_COUNTRY || "gb");
    return `${base}?${params.toString()}`;
}

/*
 * Adzuna does not send CORS headers, so a browser blocks the direct call.
 * When PF_CONFIG.CORS_PROXY is set, route the request through it. Default is a
 * free, keyless proxy that returns the raw JSON with permissive CORS headers.
 */
function withCorsProxy(adzunaUrl) {
    const c = window.PF_CONFIG || {};
    const proxy = c.CORS_PROXY;
    if (!proxy) return adzunaUrl; // direct call (only where CORS is allowed)
    return proxy + encodeURIComponent(adzunaUrl);
}

/* Normalize one Adzuna result into a job object. */
function normalizeAdzuna(item, criteria) {
    if (!item || !item.title || !item.redirect_url) return null;
    const contractTime = (item.contract_time || "").replace("_", "-");
    return {
        title: item.title,
        company: (item.company && item.company.display_name) || "Unknown",
        location: (item.location && item.location.display_name) || ORIGIN.location,
        latitude: item.latitude ?? null,
        longitude: item.longitude ?? null,
        salary_min: item.salary_min ?? null,
        salary_max: item.salary_max ?? null,
        pay: formatPay(item.salary_min, item.salary_max),
        employment_type: contractTime ? contractTime.replace(/\b\w/g, (m) => m.toUpperCase()) : "Part-time",
        created: item.created || null,
        source: "Adzuna",
        url: item.redirect_url,
        description: item.description || "",
        category: criteria.category,
        distance: null,
    };
}

/*
 * Fetch live jobs. Resolves to { jobs } or throws an Error with a `.reason`
 * of "no-key" | "cors" | "http" | "network" so the UI can show the right state.
 */
async function fetchAdzunaJobs(criteria) {
    if (!adzunaConfigured()) {
        const e = new Error("Adzuna credentials not set.");
        e.reason = "no-key";
        throw e;
    }

    let response;
    try {
        const url = withCorsProxy(buildAdzunaUrl(criteria));
        response = await fetch(url, { headers: { Accept: "application/json" } });
    } catch (err) {
        // A blocked CORS request (or an unreachable proxy) surfaces here as a
        // TypeError ("Failed to fetch").
        const e = new Error("Could not reach Adzuna from the browser.");
        e.reason = "cors";
        throw e;
    }

    if (!response.ok) {
        const e = new Error(`Adzuna returned HTTP ${response.status}.`);
        e.reason = response.status === 401 || response.status === 403 ? "no-key" : "http";
        throw e;
    }

    const payload = await response.json();
    const jobs = (payload.results || [])
        .map((item) => normalizeAdzuna(item, criteria))
        .filter(Boolean);
    return { jobs };
}
