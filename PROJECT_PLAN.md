# OI Scanner Pro — Development Roadmap

## Product goal

OI Scanner Pro is a professional terminal for identifying instruments where
large participants are likely building or closing positions. The scanner ranks
markets using Open Interest, volume, price, funding, liquidations and derived
signals, then provides detailed instrument analysis in the same application.

## General requirements

- Keep the project modular and compatible with existing versions.
- Preserve working functionality when adding new features.
- Implement new behaviour through dedicated services and existing domain
  models where possible.
- Use one common `ExchangeClient` interface for every exchange adapter.
- Normalize all exchange responses to the shared `ScannerItem` model.
- Supported exchanges are **Bybit**, **Binance Futures**, and **OKX** only.

## Current baseline — v0.5

- Bybit USDT perpetual scanner.
- SQLite history for price, Open Interest, 24-hour volume, and funding rate.
- OI %, Volume %, Price Change %, Funding, local alerts, and configurable
  thresholds.
- Signal column, colour highlighting, sorting, filters, and symbol search.

## Version 0.6 — Position Scanner

### Goal

Automatically identify position-building and position-closing patterns.

### Deliverables

- Calculate and display OI %, Volume %, Price %, and Funding.
- Standardize the Signal column with these values:
  - `Long Buildup` — green;
  - `Short Buildup` — red;
  - `Long Unwinding` — orange;
  - `Short Covering` — blue;
  - `Neutral` — no directional highlight.
- Support sorting by Signal.

## Version 0.7 — Multi Exchange

### Goal

Combine perpetual-market data from supported exchanges in one normalized
scanner.

### Deliverables

- Keep Bybit support.
- Add Binance Futures.
- Add OKX.
- Create a common `ExchangeClient` interface and an `ExchangeManager`.
- Require every exchange adapter to return normalized `ScannerItem` objects.
- Add an Exchange filter with: `All`, `Bybit`, `Binance`, and `OKX`.

## Version 0.8 — Real Time

### Goal

Move live market updates to WebSocket connections while retaining Refresh as a
manual fallback.

### Deliverables

- Receive market data automatically from supported exchanges.
- Update table rows without rebuilding the whole interface.
- Show Last Update, Ping, and Connection Status.

## Version 0.9 — Advanced Scanner

### Goal

Rank instruments and focus attention on the most relevant setups.

### Deliverables

- Calculate a Score using OI, volume, funding, price, and liquidations.
- Add a sortable Score column.
- Display the Top 20 instruments by interest score.
- Add a Watchlist.

## Version 1.0 — Professional Terminal

### Scanner

- Main scanner table with signals, history, score, filters, sorting, and
  alerts.

### Instrument Analysis

Open detailed analysis for the selected instrument by double-clicking a table
row. The view will combine:

- price candlestick chart for 15m, 1h, 4h, 1d, and 1w;
- Open Interest, Volume, and Funding charts;
- liquidations histogram and Delta where data is available;
- Open Interest Profile, Volume Profile where supported, and OI Heatmap;
- signal history, current Score, Score history, and detected position signals.

### Dashboard

- Top Gainers OI;
- Top Losers OI;
- Top Volume;
- Top Funding;
- Top Liquidations;
- Highest Score.

### Alerts

- Configure conditions for OI, Volume, Funding, Score, Long Buildup, and
  Short Buildup.
- Deliver alerts as local pop-ups, sound, journal entries, and Telegram
  messages.

### Data, export, and application services

- Persist Price, OI, Funding, Volume, Score, and Signal in SQLite.
- Export scanner data to CSV, Excel, and JSON.
- Make all parameters configurable.
- Add online license-key validation and update checks.

## Target architecture

```text
api/
    exchange_client.py
    exchange_manager.py
    bybit.py
    binance.py
    okx.py

services/
    scanner_service.py
    alert_service.py
    history_service.py
    score_service.py
    websocket_service.py

charts/
    chart_widget.py
    oi_chart.py
    funding_chart.py
    volume_chart.py
    liquidation_chart.py

database/
    sqlite_service.py
```
