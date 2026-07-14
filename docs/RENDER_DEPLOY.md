# Deploying FinPilot's backend to Render

The repo ships a [`render.yaml`](../render.yaml) blueprint that provisions
everything on Render's **free tier**: Postgres 16, a Redis-compatible
key-value store, and the FastAPI backend (Docker).

## One-time setup (~10 minutes)

1. **Create the stack** — in the [Render dashboard](https://dashboard.render.com):
   *New → Blueprint*, connect the GitHub repo, and apply. Render builds the
   backend image, provisions the database and key-value store, generates a
   `JWT_SECRET_KEY`, and boots the API (migrations run automatically on boot).

2. **Deploy the frontend** (recommended: [Vercel](https://vercel.com), also free):
   - Import the repo, set the root directory to `frontend`.
   - Env vars: `NEXT_PUBLIC_API_URL=https://<your-backend>.onrender.com`
     and `NEXT_PUBLIC_WS_URL=wss://<your-backend>.onrender.com`.

3. **Point the backend at the frontend** — in the Render service's
   *Environment* tab fill the two values the blueprint left blank:
   - `FRONTEND_URL=https://<your-frontend>.vercel.app`
   - `CORS_ORIGINS=https://<your-frontend>.vercel.app`

4. **(Optional) Google sign-in** — create an OAuth client at
   console.cloud.google.com with redirect URI
   `https://<your-backend>.onrender.com/auth/google/callback`, then set
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `GOOGLE_REDIRECT_URI`.

5. **(Optional) Sharper copilot answers** — set ONE free key:
   - `GROQ_API_KEY` from <https://console.groq.com> (recommended, fast), or
   - `GEMINI_API_KEY` from <https://aistudio.google.com/apikey>.

   End users never provide keys; without one the copilot still answers from
   each user's own financial data.

## Free-tier notes

- **No TimescaleDB on Render** — migrations detect this and create regular
  tables instead of hypertables. Everything works; time-series queries are
  just unpartitioned.
- **`DISABLE_EMBEDDINGS=1`** keeps the 512 MB instance within memory by
  skipping the sentence-transformers model. Copilot answers stay personal
  (they come from the user's own data); knowledge-base retrieval reactivates
  if you upgrade to a Starter instance and remove the variable.
- **Cold starts** — free web services sleep after 15 minutes idle; the first
  request after that takes ~30s.
- **No Celery worker** on the free tier — background email alerts are off;
  every user-facing feature works without it.
