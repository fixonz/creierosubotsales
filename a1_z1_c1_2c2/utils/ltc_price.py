import aiohttp
import time
import logging

# Cache: (ltc_price_in_ron, timestamp)
_cache = {"price": None, "fetched_at": 0}
CACHE_TTL = 3600  # 1 hour in seconds

async def get_ltc_ron_price() -> float:
    """
    Returns the current LTC price in RON.
    Caches the result for 1 hour to avoid excessive API calls.
    Falls back to a default if the API is unreachable.
    """
    now = time.time()
    
    # Return cached price if still valid
    if _cache["price"] is not None and (now - _cache["fetched_at"]) < CACHE_TTL:
        return _cache["price"]
    
    # Fetch fresh price from CoinGecko (free, no API key needed)
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=ron"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = data.get("litecoin", {}).get("ron")
                    if price and price > 0:
                        _cache["price"] = float(price)
                        _cache["fetched_at"] = now
                        logging.info(f"LTC/RON price updated: {_cache['price']} RON")
                        return _cache["price"]
    except Exception as e:
        logging.warning(f"Failed to fetch LTC price: {e}")
    
    # If we have an old cached price, use it even if expired
    if _cache["price"] is not None:
        logging.warning(f"Using stale LTC price: {_cache['price']} RON")
        return _cache["price"]
    
    # Ultimate fallback
    fallback = 450.0
    logging.warning(f"No LTC price available, using fallback: {fallback} RON")
    return fallback


def ron_to_ltc(price_ron: float, ltc_price_ron: float) -> float:
    """Convert RON amount to LTC using the given rate."""
    if ltc_price_ron <= 0:
        return 0.0
    return round(price_ron / ltc_price_ron, 4)
