/*
 * PartFinder — API configuration.
 *
 * 1. Copy this file to `config.js` (same folder):
 *        cp js/config.example.js js/config.js
 * 2. Paste your free Adzuna credentials below.
 *        Get them at https://developer.adzuna.com/admin/access_details
 *
 * `config.js` is git-ignored so your keys never get pushed to GitHub.
 * Without keys the app shows an "add your key" prompt (it never invents jobs).
 */
window.PF_CONFIG = {
    ADZUNA_APP_ID: "",
    ADZUNA_APP_KEY: "",
    ADZUNA_COUNTRY: "gb",

    // Adzuna does not allow direct browser calls (CORS), so requests are routed
    // through this proxy. The default is a free, keyless public proxy.
    // - Leave as-is to work in Live Server.
    // - Set to "" to call Adzuna directly (only works behind your own proxy or
    //   when running the Flask version, `python server.py`).
    // Note: your API key passes through the proxy — use a throwaway/rotated key.
    CORS_PROXY: "https://api.allorigins.win/raw?url=",
};
