# PartFinder — Static Web App (HTML + CSS + GSAP)

A **pure front-end** version of PartFinder that runs with **VS Code Live Server**
(no Python needed) and pushes straight to GitHub. It fetches **live jobs from the
Adzuna API** in the browser, so every card is a real Nottingham listing and every
**Apply** button opens the real posting — no placeholder links.

Searches are centred on **57 Albert Grove, Nottingham, NG7 1NZ** and only show
part-time / casual / student roles paying **£12.71/hour and up**, posted in the last
two weeks. Swipe (drag or tap): **Pass**, **Save**, **Apply**.

---

## Run it in VS Code (Live Server)

1. **Add your free Adzuna keys** (required for live results):
   ```bash
   cd web
   cp js/config.example.js js/config.js
   ```
   Open `js/config.js` and paste your credentials from
   <https://developer.adzuna.com/admin/access_details>:
   ```js
   window.PF_CONFIG = {
       ADZUNA_APP_ID: "your_app_id",
       ADZUNA_APP_KEY: "your_app_key",
       ADZUNA_COUNTRY: "gb",
   };
   ```
2. Install the **Live Server** extension in VS Code.
3. Right-click `web/index.html` → **"Open with Live Server"**.
4. Pick a category, days, and radius → **Find my matches** → swipe your live matches.

Without keys the app shows an "add your key" prompt — it never shows fake jobs.

---

## Push to GitHub

`js/config.js` is git-ignored, so your keys stay private:

```bash
git add web
git commit -m "Add PartFinder static web app"
git push
```

To deploy free, enable **GitHub Pages** (Settings → Pages → deploy from branch,
`/web` folder). Note: on a public site your key is visible in the page source — use a
throwaway/rate-limited Adzuna key, or serve via the Flask version below.

---

## Files

```
web/
├── index.html          # single page: search view + swipe results view
├── css/style.css       # dark, Tinder-inspired theme
└── js/
    ├── config.example.js  # copy to config.js and add your keys
    ├── logic.js           # origin, filters, ranking, distance (pure)
    ├── adzuna.js          # live Adzuna fetch + normalization
    └── app.js             # GSAP swipe deck + UI states
```

GSAP and its Draggable plugin load from a CDN (animation only).

---

## How the live call works (CORS)

Adzuna does not send CORS headers, so a browser blocks a direct call. The app therefore
routes the request through a **CORS proxy** set in `js/config.js`:

```js
CORS_PROXY: "https://api.allorigins.win/raw?url=",
```

- This is a free, keyless public proxy — it makes the static app work in Live Server.
- **Your Adzuna key passes through the proxy**, so use a throwaway key and rotate it
  after your demo.
- To avoid any third party, set `CORS_PROXY: ""` and run the **Flask version**
  (`python server.py` in the repo root) — it calls Adzuna server-side, no CORS proxy.

## Notes & troubleshooting

- **"Couldn't reach the job service"** — the proxy was busy or down. Wait and retry,
  swap `CORS_PROXY` for another proxy (e.g. `https://corsproxy.io/?url=`), or run the
  Flask version.
- **"Add your free Adzuna key"** — you haven't created `js/config.js` yet, or the keys
  are blank/invalid. Both an App ID *and* an App Key are required.
- **No matches** — nothing paying £12.71/hour+ within your radius right now; widen the
  radius or try another category.
- **Security** — never commit real keys or hard-code them into a public deployment.
