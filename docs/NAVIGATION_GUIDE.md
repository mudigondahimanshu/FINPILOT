# FinPilot Navigation Guide

Complete navigation map for all pages, components, and their locations in the FinPilot application.

---

## 📱 Page Structure Overview

FinPilot uses a Next.js App Router with the following page groups:
- **Authentication Pages** — Login, Registration, OAuth Callback
- **App Pages** — Protected pages accessible after login
- **Landing Page** — Public homepage

---

## 🔐 Authentication Pages

### 1. **Login Page**
- **URL:** `http://localhost:3000/login`
- **File:** `frontend/app/(auth)/login/page.tsx`
- **Description:** User login with email/password or Google OAuth
- **Components Used:**
  - `AuthShell` — Layout wrapper for auth pages
  - `GoogleButton` — Google OAuth login button
  - `AuthProvider` — Authentication context provider

---

### 2. **Registration Page**
- **URL:** `http://localhost:3000/register`
- **File:** `frontend/app/(auth)/register/page.tsx`
- **Description:** New user registration with email/password or Google OAuth
- **Components Used:**
  - `AuthShell` — Layout wrapper for auth pages
  - `GoogleButton` — Google OAuth signup button
  - `AuthProvider` — Authentication context provider

---

### 3. **OAuth Callback Page**
- **URL:** `http://localhost:3000/auth/callback` (auto-redirected after Google login)
- **File:** `frontend/app/auth/callback/page.tsx`
- **Description:** Handles OAuth redirect and token exchange with backend
- **Components Used:** None (server-side redirect logic)

---

### 4. **Landing Page**
- **URL:** `http://localhost:3000/`
- **File:** `frontend/app/page.tsx`
- **Description:** Public homepage (redirects to `/dashboard` if logged in)

---

## 🏠 Protected App Pages

All protected pages are in the `(app)` route group and require authentication (enforced by `RequireAuth` component).

### 1. **Dashboard Page**
- **URL:** `http://localhost:3000/dashboard`
- **File:** `frontend/app/(app)/dashboard/page.tsx`
- **Key Features:**
  - Account balance summary card
  - Portfolio composition gauge
  - Budget progress bars (by category)
  - Spending trend chart
  - Recent transactions list
  - AI personalization badge
- **Components Used:**
  - `AppShell` — Main app layout (sidebar, navbar)
  - `SpendingCharts` — Contains:
    - `CustomPieTooltip` — Spending by category donut chart with white text
    - `CustomBarTooltip` — Monthly trend bar chart with white text
  - `ThemeToggle` — Dark/Light mode switcher

---

### 2. **Transactions Page**
- **URL:** `http://localhost:3000/transactions`
- **File:** `frontend/app/(app)/transactions/page.tsx`
- **Key Features:**
  - Transaction table with sorting & filtering
  - CSV bulk import
  - Add transaction modal
  - Filter by category, date, type (income/expense)
  - Transaction history search
- **Components Used:**
  - `AppShell` — Main app layout
  - `TransactionTable` — Displays transaction data with sorting
  - `TransactionFilters` — Category & date range filters
  - `AddTransactionModal` — Modal form for manual entry
  - `CsvUpload` — CSV file uploader for bulk import
  - `SpendingCharts` — Monthly spending summary

---

### 3. **Market Data Page**
- **URL:** `http://localhost:3000/market`
- **File:** `frontend/app/(app)/market/page.tsx`
- **Key Features:**
  - Ticker search (NSE/BSE stocks only)
  - Live quote display (price, change, change%)
  - OHLC price chart with SMA indicators
  - Fundamental analysis (P/E, P/B, Beta, Dividend Yield, 52W High/Low)
  - Watchlist management (add/remove stocks)
  - Period selector (5d, 1mo, 3mo, 6mo, 1y, 2y, 5y)
  - Recommended stocks section (6 popular Indian stocks)
- **Components Used:**
  - `AppShell` — Main app layout
  - `TickerSearch` — Stock symbol autocomplete search
  - `OhlcChart` — Price chart with:
    - `CustomOhlcTooltip` — White text tooltip
    - Area chart with SMA20 & SMA50 overlays
  - Business summary card (if available)

---

### 4. **Insights Page**
- **URL:** `http://localhost:3000/insights`
- **File:** `frontend/app/(app)/insights/page.tsx`
- **Key Features:**
  - AI Copilot chat widget (personalized context injection)
  - Spending forecast visualization
  - Stock sentiment analysis feed
  - Fraud detection alerts (isolation forest anomalies, velocity flags, spending cycles)
  - Real-time anomaly scoring
- **Components Used:**
  - `AppShell` — Main app layout
  - `ChatWidget` — AI chat interface with auto-refresh
    - Personalized context (user portfolio, spending, budget constraints)
    - RAG (Retrieval-Augmented Generation) prompt injection
  - `ForecastChart` — Spending trend forecast with:
    - `CustomForecastTooltip` — Forecast value display
  - `SentimentFeed` — Stock sentiment analysis
    - `ScoreBadge` — Sentiment score badge (Bullish/Bearish/Neutral)
  - Fraud detection section:
    - Isolation forest anomalies
    - Velocity anomalies (spending spikes)
    - Cycle pattern detection

---

### 5. **Portfolio Optimizer Page**
- **URL:** `http://localhost:3000/optimize`
- **File:** `frontend/app/(app)/optimize/page.tsx`
- **Key Features:**
  - Modern Portfolio Theory (Markowitz) visualization
  - Efficient frontier scatter plot (2000 simulated portfolios)
  - Symbol management (add/remove up to 15 stocks)
  - Three recommended allocations:
    - ⭐ Max Sharpe Ratio
    - 🛡️ Min Volatility
    - ⚖️ Moderate (18% vol cap)
  - Risk profiles (Conservative, Moderate, Aggressive)
  - Allocation breakdowns with color-coded weights
- **Components Used:**
  - `AppShell` — Main app layout
  - Symbol input & management
  - `ScatterChart` — Efficient frontier visualization
    - `ScatterTooltip` — Returns & volatility display (white text)
  - `AllocationDonut` component:
    - Multiple `PieChart` components with:
      - `PieTooltip` — Allocation percentage display
    - Metrics display (Expected Return, Volatility, Sharpe Ratio)
    - Allocation weights table
  - Risk profiles grid with preset allocations

---

### 6. **Trading Page** (Paper Trading)
- **URL:** `http://localhost:3000/trading`
- **File:** `frontend/app/(app)/trading/page.tsx`
- **Key Features:**
  - Paper trading (simulated trades with virtual cash)
  - Order form (buy/sell)
  - Portfolio positions
  - Trade history
  - Real-time price quotes
- **Components Used:**
  - `AppShell` — Main app layout
  - `OrderForm` — Buy/sell order entry
    - Symbol selector
    - Quantity & price inputs
    - Order confirmation

---

## 🧩 Shared Components

### Layout Components
| Component | Location | Purpose |
|-----------|----------|---------|
| `AppShell` | `components/dashboard/app-shell.tsx` | Main app layout with sidebar, navbar, content area |
| `AuthShell` | `components/auth/auth-shell.tsx` | Auth page layout (centered form) |
| `RequireAuth` | `components/auth/require-auth.tsx` | Route protection wrapper |
| `AuthProvider` | `components/auth/auth-provider.tsx` | Authentication context (session, login/logout) |
| `ThemeProvider` | `components/theme-provider.tsx` | Dark/light mode context |

### UI Components (Primitives)
| Component | Location | Purpose |
|-----------|----------|---------|
| `Button` | `components/ui/button.tsx` | Reusable button with variants |
| `Input` | `components/ui/input.tsx` | Text input field |
| `Label` | `components/ui/label.tsx` | Form label |
| `ThemeToggle` | `components/ui/theme-toggle.tsx` | Dark/light mode switch (moon/sun icons) |

### Feature Components
| Component | Location | Purpose |
|-----------|----------|---------|
| `GoogleButton` | `components/auth/google-button.tsx` | OAuth sign-in button |
| `TickerSearch` | `components/market/ticker-search.tsx` | Stock symbol autocomplete search |
| `OhlcChart` | `components/market/ohlc-chart.tsx` | Price chart with SMA indicators + `CustomOhlcTooltip` |
| `ChatWidget` | `components/ml/chat-widget.tsx` | AI Copilot chat with personalization |
| `ForecastChart` | `components/ml/forecast-chart.tsx` | Spending forecast visualization |
| `SentimentFeed` | `components/ml/sentiment-feed.tsx` | Stock sentiment analysis feed with `ScoreBadge` |
| `OrderForm` | `components/trading/order-form.tsx` | Paper trading buy/sell form |
| `TransactionTable` | `components/transactions/transaction-table.tsx` | Sortable transaction list |
| `TransactionFilters` | `components/transactions/transaction-filters.tsx` | Filter by category/date/type |
| `AddTransactionModal` | `components/transactions/add-transaction-modal.tsx` | Manual transaction entry |
| `CsvUpload` | `components/transactions/csv-upload.tsx` | Bulk CSV import |
| `SpendingCharts` | `components/transactions/spending-charts.tsx` | Contains `CustomPieTooltip` & `CustomBarTooltip` |

---

## 🎨 Custom Chart Tooltips (Dark Theme)

All tooltips have white text (`color: "#ffffff"`) on dark backgrounds for readability:

| Tooltip | File | Chart Type | Used In |
|---------|------|-----------|---------|
| `CustomOhlcTooltip` | `components/market/ohlc-chart.tsx` | Area Chart | Market page — Price data |
| `CustomPieTooltip` | `components/transactions/spending-charts.tsx` | Pie Chart | Dashboard — Spending by category |
| `CustomBarTooltip` | `components/transactions/spending-charts.tsx` | Bar Chart | Dashboard — Monthly trend |
| `ScatterTooltip` | `frontend/app/(app)/optimize/page.tsx` | Scatter Chart | Optimizer page — Efficient frontier |
| `PieTooltip` | `frontend/app/(app)/optimize/page.tsx` | Pie Chart | Optimizer page — Allocations |

---

## 🔗 Navigation Hierarchy

```
localhost:3000
├── / (landing page)
│
├── (auth)
│   ├── /login
│   ├── /register
│   └── /auth/callback
│
└── (app) [protected]
    ├── /dashboard ⭐ Default after login
    ├── /transactions
    ├── /market
    ├── /insights
    ├── /optimize
    └── /trading
```

---

## 🚀 Quick Navigation Quick Reference

| Feature | Go To | File |
|---------|-------|------|
| View balance & spending | `/dashboard` | `app/(app)/dashboard/page.tsx` |
| Add transactions | `/transactions` | `app/(app)/transactions/page.tsx` |
| Search stocks & watch | `/market` | `app/(app)/market/page.tsx` |
| AI copilot & insights | `/insights` | `app/(app)/insights/page.tsx` |
| Portfolio optimization | `/optimize` | `app/(app)/optimize/page.tsx` |
| Paper trading | `/trading` | `app/(app)/trading/page.tsx` |
| Login | `/login` | `app/(auth)/login/page.tsx` |
| Sign up | `/register` | `app/(auth)/register/page.tsx` |

---

## 📂 File Structure Reference

```
frontend/
├── app/
│   ├── page.tsx (landing)
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── auth/
│   │   └── callback/page.tsx
│   └── (app)/
│       ├── dashboard/page.tsx
│       ├── transactions/page.tsx
│       ├── market/page.tsx
│       ├── insights/page.tsx
│       ├── optimize/page.tsx
│       └── trading/page.tsx
│
└── components/
    ├── auth/
    │   ├── auth-provider.tsx
    │   ├── auth-shell.tsx
    │   ├── google-button.tsx
    │   └── require-auth.tsx
    ├── dashboard/
    │   └── app-shell.tsx
    ├── market/
    │   ├── ohlc-chart.tsx
    │   └── ticker-search.tsx
    ├── ml/
    │   ├── chat-widget.tsx
    │   ├── forecast-chart.tsx
    │   └── sentiment-feed.tsx
    ├── trading/
    │   └── order-form.tsx
    ├── transactions/
    │   ├── add-transaction-modal.tsx
    │   ├── csv-upload.tsx
    │   ├── spending-charts.tsx
    │   ├── transaction-filters.tsx
    │   └── transaction-table.tsx
    ├── ui/
    │   ├── button.tsx
    │   ├── input.tsx
    │   ├── label.tsx
    │   └── theme-toggle.tsx
    ├── theme-provider.tsx
```

---

## 🔑 Key Navigation Tips

1. **Auth Required:** All pages in `(app)` group require login. Access without token → redirect to `/login`
2. **Default Landing:** After login, users land on `/dashboard`
3. **Stock Data:** Market page shows only **Indian stocks (NSE/BSE)** via yfinance
4. **Protected Routes:** Use `RequireAuth` wrapper to enforce authentication on pages
5. **Dark Mode:** Available on all app pages via `ThemeToggle` (moon/sun icon)
6. **Real-Time Data:** Dashboard, Market, and Insights pages fetch live data from backend

---

## 📝 Notes

- All file paths are relative to project root (`/Users/himanshumudigonda/Projects/finpilot/`)
- Component imports use `@/` alias (configured in `tsconfig.json`)
- All tooltips in charts use inline CSS styling with `color: "#ffffff"` for contrast
- The app uses Recharts for all data visualization
