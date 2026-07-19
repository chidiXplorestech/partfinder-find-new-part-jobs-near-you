/*
 * PartFinder — pure search logic (client-side port of the Python pipeline).
 * Origin, filters, ranking and helpers. No DOM, no network.
 */

/* Search origin: 57 Albert Grove, Nottingham, NG7 1NZ */
const ORIGIN = { lat: 52.9515, lng: -1.1789, postcode: "NG7 1NZ", location: "Nottingham" };

const MIN_HOURLY_PAY = 12.71; // hard pay floor
const MAX_JOB_AGE_DAYS = 14; // never show anything older
const ENTRY_LEVEL_SALARY_CAP = 45000; // treat above as senior
const NATIONAL_LIVING_WAGE = 12.71;
const FULL_TIME_HOURS_PER_YEAR = 37.5 * 52;

/* Category keys -> Adzuna category tag + free-text keywords */
const CATEGORIES = [
    { key: "sales", label: "Sales", keywords: ["sales assistant", "sales"], adzuna: "sales-jobs" },
    { key: "customer-service", label: "Customer Service", keywords: ["customer service", "customer assistant"], adzuna: "customer-services-jobs" },
    { key: "office", label: "Office Jobs", keywords: ["office", "admin", "receptionist"], adzuna: "admin-jobs" },
    { key: "remote", label: "Reliable Remote Jobs", keywords: ["remote", "work from home"], adzuna: null, remote: true },
    { key: "retail", label: "Retail", keywords: ["retail", "shop assistant", "store"], adzuna: "retail-catering-jobs" },
    { key: "housing", label: "Housing", keywords: ["housing", "property", "lettings"], adzuna: "property-jobs" },
    { key: "contract", label: "Contract", keywords: ["contract", "temporary"], adzuna: null, contract: true },
];
const CATEGORY_BY_KEY = Object.fromEntries(CATEGORIES.map((c) => [c.key, c]));

const WEEKEND_DAYS = ["Saturday", "Sunday"];

const REJECT_KEYWORDS = [
    "full-time", "full time", "senior", "manager", "management",
    "graduate", "director", "head of", "lead ", "principal",
];

const SOURCE_RELIABILITY = {
    Adzuna: 0.92, LinkedIn: 0.9, Indeed: 0.85, Totaljobs: 0.82, Glassdoor: 0.8,
};

const RANK_WEIGHTS = { distance: 0.35, recency: 0.25, availability: 0.18, pay: 0.12, reliability: 0.1 };

/* ---------- helpers ---------- */

function haversineMiles(lat1, lng1, lat2, lng2) {
    const R = 3958.8;
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLng = ((lng2 - lng1) * Math.PI) / 180;
    const a =
        Math.sin(dLat / 2) ** 2 +
        Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLng / 2) ** 2;
    return R * 2 * Math.asin(Math.sqrt(a));
}

function hourlyRate(salary) {
    if (!salary) return null;
    return salary < 100 ? salary : salary / FULL_TIME_HOURS_PER_YEAR;
}

function daysSince(isoDate) {
    if (!isoDate) return null;
    const then = new Date(isoDate);
    if (isNaN(then)) return null;
    return Math.floor((Date.now() - then.getTime()) / 86400000);
}

function relativeDate(isoDate) {
    const d = daysSince(isoDate);
    if (d === null) return "Recently";
    if (d <= 0) return "Today";
    if (d === 1) return "Yesterday";
    return `${d} days ago`;
}

function formatPay(min, max) {
    const vals = [min, max].filter((v) => v);
    if (!vals.length) return "Pay on application";
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    if (hi < 100) {
        return lo === hi ? `£${lo.toFixed(2)}/hour` : `£${lo.toFixed(2)}–£${hi.toFixed(2)}/hour`;
    }
    const hourly = hourlyRate(hi);
    const base = lo === hi ? `£${Math.round(lo).toLocaleString()}/year` : `£${Math.round(lo).toLocaleString()}–£${Math.round(hi).toLocaleString()}/year`;
    return hourly ? `${base} (≈£${hourly.toFixed(2)}/hr)` : base;
}

/* ---------- filters ---------- */

function passesFilters(job, criteria) {
    const hay = `${job.title} ${job.employment_type} ${job.description}`.toLowerCase();
    if (REJECT_KEYWORDS.some((k) => hay.includes(k))) return false;

    const age = daysSince(job.created);
    if (age !== null && (age < 0 || age > MAX_JOB_AGE_DAYS)) return false;

    const rate = hourlyRate(job.salary_min);
    if (rate !== null && rate < MIN_HOURLY_PAY) return false;
    if (job.salary_min && job.salary_min > ENTRY_LEVEL_SALARY_CAP) return false;

    if (job.distance !== null && job.distance > criteria.radius) return false;
    return true;
}

/* ---------- ranking ---------- */

function distanceScore(job, criteria) {
    if (job.distance === null) return 0.5;
    return Math.max(0, 1 - job.distance / Math.max(criteria.radius, 1));
}

function recencyScore(job) {
    const age = daysSince(job.created);
    if (age === null) return 0.5;
    if (age <= 1) return 1;
    if (age <= 7) return 0.75;
    return Math.max(0, 1 - age / MAX_JOB_AGE_DAYS) * 0.6;
}

function availabilityScore(job, criteria) {
    if (!criteria.days.length) return 0.5;
    const hay = `${job.title} ${job.employment_type} ${job.description}`.toLowerCase();
    let s = 0.4;
    const wantsWeekend = criteria.days.some((d) => WEEKEND_DAYS.includes(d));
    if (wantsWeekend && /weekend|saturday|sunday/.test(hay)) s += 0.4;
    if (/flexible|part-time|part time|casual|shifts/.test(hay)) s += 0.2;
    return Math.min(1, s);
}

function payScore(job) {
    const rate = hourlyRate(job.salary_min);
    if (rate === null) return 0.5;
    if (rate < MIN_HOURLY_PAY) return 0.3;
    if (rate <= NATIONAL_LIVING_WAGE * 1.5) return 1;
    return 0.6;
}

function scoreJob(job, criteria) {
    const rel = SOURCE_RELIABILITY[job.source] ?? 0.5;
    return (
        RANK_WEIGHTS.distance * distanceScore(job, criteria) +
        RANK_WEIGHTS.recency * recencyScore(job) +
        RANK_WEIGHTS.availability * availabilityScore(job, criteria) +
        RANK_WEIGHTS.pay * payScore(job) +
        RANK_WEIGHTS.reliability * rel
    );
}

/* Enrich (distance), filter, and rank a list of normalized jobs. */
function processJobs(jobs, criteria) {
    jobs.forEach((j) => {
        j.distance =
            j.latitude != null && j.longitude != null
                ? haversineMiles(ORIGIN.lat, ORIGIN.lng, j.latitude, j.longitude)
                : null;
    });
    return jobs
        .filter((j) => passesFilters(j, criteria))
        .sort((a, b) => scoreJob(b, criteria) - scoreJob(a, criteria));
}
