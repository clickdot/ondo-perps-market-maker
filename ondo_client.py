import requests
import json
import logging
import time
import hmac
import hashlib
from urllib.parse import urlparse
import websocket
import threading
logger = logging.getLogger(__name__)

class OndoPerpsClient:
    def __init__(self, api_key: str, api_secret: str, base_url: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str) -> str:
        payload = timestamp + method + request_path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method: str, endpoint: str, data=None, params=None):
        url = f"{self.base_url}{endpoint}"
        
        # Prepare the request to get the exact path including query params
        req = requests.Request(method, url, json=data, params=params)
        prepared = self.session.prepare_request(req)
        
        timestamp = str(int(time.time() * 1000))
        parsed_url = urlparse(prepared.url)
        request_path = parsed_url.path
        if parsed_url.query:
            request_path += "?" + parsed_url.query
            
        # Decode body if present, else empty string
        body = prepared.body.decode('utf-8') if prepared.body else ""
        
        signature = self._generate_signature(timestamp, method.upper(), request_path, body)
        
        prepared.headers["ONDO-KEY-ID"] = self.api_key
        prepared.headers["ONDO-TIMESTAMP"] = timestamp
        prepared.headers["ONDO-SIGN"] = signature
        prepared.headers["Content-Type"] = "application/json"

        try:
            response = self.session.send(prepared)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API Request failed: {method} {url} - {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response body: {e.response.text}")
            raise

    def get_market_data(self, symbol: str):
        """
        Fetches the current market data and live price for a given token symbol.
        """
        market = f"{symbol}.P" if not symbol.endswith(".P") else symbol
        
        # 1. Fetch live mark price
        price = None
        price_data = self._request("GET", "/perps/mark_prices")
        if "result" in price_data and market in price_data["result"]:
            price = price_data["result"][market].get("price") or price_data["result"][market].get("markPrice")
            
        # 2. Fetch base increment from market metadata
        base_increment = 0.01
        meta_data = self._request("GET", "/markets")
        if "result" in meta_data and "perps" in meta_data["result"]:
            for pair in meta_data["result"]["perps"]["tradingPairs"]:
                if symbol.replace("-USD", "") in pair["market"]:
                    base_increment = float(pair.get("baseIncrement", 0.01))
                    break
                    
        return {"price": price, "base_increment": base_increment}

    def place_order(self, symbol: str, side: str, order_type: str, price: float, size: float):
        """
        Places an order on the exchange.
        """
        endpoint = "/perps/orders/delayed"
        # The API uses 'market' instead of 'symbol', and it expects '.P' suffix for perps
        market = f"{symbol}.P" if not symbol.endswith(".P") else symbol
        payload = {
            "market": market,
            "side": side.upper(),       # "BUY" or "SELL"
            "type": order_type.upper(), # "LIMIT" or "MARKET"
            "price": str(price),
            "size": str(size),
            "leverage": "10"
        }
        logger.info(f"Placing {side} order for {size} {market} @ {price} with 10x leverage")
        return self._request("POST", endpoint, data=payload)

    def cancel_all_orders(self, symbol: str):
        """
        Cancels all open orders for a given symbol.
        """
        endpoint = "/perps/orders"
        market = f"{symbol}.P" if not symbol.endswith(".P") else symbol
        params = {"market": market}
        logger.info(f"Canceling all open orders for {market}")
        return self._request("DELETE", endpoint, params=params)

    def get_open_orders(self, symbol: str = None):
        """
        Gets a list of all open orders.
        """
        endpoint = "/perps/orders/open"
        params = {}
        if symbol:
            params["market"] = f"{symbol}.P" if not symbol.endswith(".P") else symbol
        return self._request("GET", endpoint, params=params)

    def get_position(self, symbol: str):
        """
        Gets the current open position for a given symbol.
        Returns the position dict if it exists, otherwise None.
        """
        endpoint = "/perps/positions"
        market = f"{symbol}.P" if not symbol.endswith(".P") else symbol
        response = self._request("GET", endpoint)
        if "result" in response:
            for position in response["result"]:
                if position.get("market") == market:
                    return position
        return None

class OndoWSSClient:
    def __init__(self, symbol: str, on_price_update):
        self.symbol = f"{symbol}.P" if not symbol.endswith(".P") else symbol
        self.url = "wss://api.ondoperps.xyz/ws"
        self.ws = None
        self.wst = None
        self.on_price_update = on_price_update

    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data.get("type") == "update" and data.get("channel") == "topOfBooksPerps":
                for item in data.get("data", []):
                    if item.get("market") == self.symbol:
                        asks = item.get("asks", [])
                        bids = item.get("bids", [])
                        if asks and bids:
                            best_ask = float(asks[0][0])
                            best_bid = float(bids[0][0])
                            mid_price = (best_ask + best_bid) / 2.0
                            self.on_price_update(mid_price)
        except Exception as e:
            logger.error(f"Error parsing WSS message: {e}")

    def _on_error(self, ws, error):
        logger.error(f"WSS Error: {error}")

    def _on_close(self, ws, close_status_code, close_msg):
        logger.info("WSS Connection Closed")

    def _on_open(self, ws):
        logger.info(f"WSS Connected. Subscribing to {self.symbol} topOfBooksPerps...")
        payload = {
            "op": "subscribe",
            "channel": "topOfBooksPerps",
            "markets": [self.symbol]
        }
        ws.send(json.dumps(payload))

    def start(self):
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        self.wst = threading.Thread(target=self.ws.run_forever)
        self.wst.daemon = True
        self.wst.start()

    def stop(self):
        if self.ws:
            self.ws.close()
