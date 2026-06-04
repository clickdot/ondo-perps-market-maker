import time
import logging
import sys
import config
from ondo_client import OndoPerpsClient, OndoWSSClient

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

    # Fetch initial base_increment once
    logger.info("Fetching market metadata...")
    try:
        initial_market_data = client.get_market_data(config.TOKEN_SYMBOL)
        base_increment = initial_market_data.get("base_increment", 0.01)
    except Exception as e:
        logger.error(f"Failed to fetch initial market data: {e}")
        base_increment = 0.01

    decimals = len(str(base_increment).split('.')[-1]) if '.' in str(base_increment) else 0
    snapped_size = round(max(base_increment, round(config.ORDER_SIZE / base_increment) * base_increment), decimals)

    # Setup WSS State
    shared_state = {"price": None}
    
    def on_price_update(new_price):
        shared_state["price"] = new_price

    wss_client = OndoWSSClient(config.TOKEN_SYMBOL, on_price_update)
    wss_client.start()

    logger.info("Waiting for initial WSS price...")
    while shared_state["price"] is None:
        time.sleep(0.5)
    
    logger.info("WSS price received! Starting market making loop.")

    try:
        while True:
            try:
                logger.info("--- Starting Market Maker Cycle ---")
                
                # 1. Cancel existing open orders
                try:
                    client.cancel_all_orders(config.TOKEN_SYMBOL)
                except Exception as e:
                    logger.error(f"Failed to cancel open orders: {e}")
                    # Continue anyway, or decide to halt

                # 2. Get current price from WSS
                current_price = shared_state["price"]
                
                if current_price is None or current_price <= 0:
                    logger.error("Invalid price from WSS. Skipping cycle.")
                    time.sleep(config.INTERVAL)
                    continue
                    
                logger.info(f"Current WSS price for {config.TOKEN_SYMBOL}: {current_price} | Snapped Size: {snapped_size}")

                # 3. Check position logic for Max Position
                place_bid = True
                place_ask = True
                bid_size = snapped_size
                ask_size = snapped_size
                
                try:
                    position = client.get_position(config.TOKEN_SYMBOL)
                    if position:
                        net_qty = float(position.get("netQuantity", 0))
                        direction = position.get("direction", "")
                        
                        if net_qty >= config.MAX_POSITION_SIZE:
                            logger.warning(f"Max position reached: {net_qty} {direction}. Entering reduce-only mode with max position size.")
                            unwind_size = round(max(base_increment, round(net_qty / base_increment) * base_increment), decimals)
                            if direction == "long":
                                place_bid = False
                                ask_size = unwind_size
                            elif direction == "short":
                                place_ask = False
                                bid_size = unwind_size
                except Exception as e:
                    logger.error(f"Failed to fetch position data: {e}")

                # 4. Calculate Bid and Ask quotes
                # Spread is in basis points (1 bps = 0.01%)
                spread_pct = config.SPREAD_BPS / 10000.0
                bid_price = round(current_price * (1 - spread_pct), 2)
                ask_price = round(current_price * (1 + spread_pct), 2)

                # 5. Place limit orders conditionally
                try:
                    # Place BID
                    if place_bid:
                        client.place_order(
                            symbol=config.TOKEN_SYMBOL,
                            side="BUY",
                            order_type="LIMIT",
                            price=bid_price,
                            size=bid_size
                        )
                    # Place ASK
                    if place_ask:
                        client.place_order(
                            symbol=config.TOKEN_SYMBOL,
                            side="SELL",
                            order_type="LIMIT",
                            price=ask_price,
                            size=ask_size
                        )
                except Exception as e:
                    logger.error(f"Failed to place orders: {e}")

                logger.info("--- Cycle Complete ---")

            except Exception as e:
                logger.error(f"Unexpected error in cycle: {e}")

            # 6. Sleep for the configured interval
            time.sleep(config.INTERVAL)

    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        logger.info("Shutting down WSS Client...")
        wss_client.stop()

if __name__ == "__main__":
    run_bot()
