import time
import logging
import sys
import config
from ondo_client import OndoPerpsClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_bot():
    logger.info("Starting Ondo Perps Market Maker Bot")
    logger.info(f"Symbol: {config.TOKEN_SYMBOL}")
    logger.info(f"Spread: {config.SPREAD_BPS} bps")
    logger.info(f"Order Size: {config.ORDER_SIZE}")
    logger.info(f"Interval: {config.INTERVAL}s")

    client = OndoPerpsClient(api_key=config.API_KEY, api_secret=config.API_SECRET, base_url=config.API_BASE_URL)

    while True:
        try:
            logger.info("--- Starting Market Maker Cycle ---")
            
            # 1. Cancel existing open orders
            try:
                client.cancel_all_orders(config.TOKEN_SYMBOL)
            except Exception as e:
                logger.error(f"Failed to cancel open orders: {e}")
                # Continue anyway, or decide to halt

            # 2. Fetch current market price
            try:
                market_data = client.get_market_data(config.TOKEN_SYMBOL)
                price_val = market_data.get("price")
                base_increment = market_data.get("base_increment", 0.01)
                
                # Snap order size to base_increment
                decimals = len(str(base_increment).split('.')[-1]) if '.' in str(base_increment) else 0
                snapped_size = round(max(base_increment, round(config.ORDER_SIZE / base_increment) * base_increment), decimals)
                
                if price_val is None:
                    # If market is closed or testnet has no price, use a fallback for testing
                    logger.warning("Price is None (market might be closed). Using 312.24 for testing based on fair price.")
                    current_price = 312.24
                else:
                    current_price = float(price_val)
                    
                if current_price <= 0:
                    raise ValueError("Invalid price returned from API")
                logger.info(f"Current price for {config.TOKEN_SYMBOL}: {current_price} | Snapped Size: {snapped_size}")
            except Exception as e:
                logger.error(f"Failed to fetch market data: {e}")
                time.sleep(config.INTERVAL)
                continue

            # 3. Calculate Bid and Ask quotes
            # Spread is in basis points (1 bps = 0.01%)
            spread_pct = config.SPREAD_BPS / 10000.0
            bid_price = current_price * (1 - spread_pct)
            ask_price = current_price * (1 + spread_pct)
            
            # Format prices to 2 decimal places (adjust as needed for the specific token)
            bid_price = round(bid_price, 2)
            ask_price = round(ask_price, 2)

            # 4. Place limit orders
            try:
                # Place BID
                client.place_order(
                    symbol=config.TOKEN_SYMBOL,
                    side="BUY",
                    order_type="LIMIT",
                    price=bid_price,
                    size=snapped_size
                )
                # Place ASK
                client.place_order(
                    symbol=config.TOKEN_SYMBOL,
                    side="SELL",
                    order_type="LIMIT",
                    price=ask_price,
                    size=snapped_size
                )
            except Exception as e:
                logger.error(f"Failed to place orders: {e}")

            logger.info("--- Cycle Complete ---")

        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")

        # 5. Sleep for the configured interval
        time.sleep(config.INTERVAL)

if __name__ == "__main__":
    run_bot()
