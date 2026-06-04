# Ondo Perps Market Maker Bot

A Python-based market making bot for the Ondo Perps API. It continuously places bid and ask limit orders around the fair price to provide liquidity.

## Features
- Connects to Ondo Perps API using HMAC SHA256 authentication.
- Automatically cancels open orders before placing new ones to manage margin limits.
- Configurable spread, order size, and trading pairs.
- Graceful handling of after-hours market closures by falling back to fair price indexing.
- **Max Position Limits**: Automatically monitors your open positions and shifts into a reduce-only mode (halting bids or asks) when a defined maximum exposure is reached.

## Setup
1. Install dependencies: 
```bash
pip install -r requirements.txt
```
2. Copy `.env.example` to `.env` and fill in your API credentials.
3. Run the bot: 
```bash
python3 main.py
```
