import aiohttp
import asyncio
import logging
from datetime import datetime
from config import TATUM_API_KEY

_session = None

async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()
    return _session

async def check_ltc_transaction(address: str, amount_expected: float, timestamp_since: int, last_tx_hash: str = None) -> tuple[bool, int, str, float, bool]:
    """
    Checks for a transaction to `address` matching `amount_expected`.
    Uses BlockCypher as primary provider and Tatum as fallback.
    
    Returns (found, confirmations, tx_hash, paid_amount, needs_review).
    """
    session = await get_session()
    
    # --- 1. PRIMARY: BlockCypher ---
    try:
        url_bc = f"https://api.blockcypher.com/v1/ltc/main/addrs/{address}/full?limit=5"
        async with session.get(url_bc, timeout=10) as resp:
            if resp.status == 200:
                data = await resp.json()
                txs = data.get("txs", [])
                logging.info(f"BLOCKCYPHER | Checking {len(txs)} txs for {address}")
                
                for tx in txs:
                    time_str = tx.get("confirmed") or tx.get("received")
                    tx_time = 0
                    if time_str:
                        ts_str = time_str.replace("Z", "+00:00")
                        dt = datetime.fromisoformat(ts_str)
                        tx_time = int(dt.timestamp())
                    
                    tx_hash = tx.get("hash", "")
                    if tx_time < (timestamp_since - 120): continue
                    if last_tx_hash and tx_hash == last_tx_hash: continue
                        
                    outputs = tx.get("outputs", [])
                    for out in outputs:
                        out_addrs = out.get("addresses", [])
                        if address in out_addrs:
                            val = out.get("value", 0) / 100000000.0
                            confirmations = tx.get("confirmations", 0)
                            is_paid, needs_review = validate_amount(val, amount_expected)
                            if is_paid:
                                return True, confirmations, tx_hash, val, needs_review

    except Exception as e:
        logging.warning(f"BLOCKCYPHER | Error: {e}")

    # --- 2. FALLBACK: Tatum ---
    url_tatum = f"https://api.tatum.io/v3/litecoin/transaction/address/{address}?pageSize=10"
    headers = {"x-api-key": TATUM_API_KEY}
    
    try:
        # Get latest height
        latest_height = 0
        async with session.get("https://api.tatum.io/v3/litecoin/info", headers=headers) as info_resp:
            if info_resp.status == 200:
                info_data = await info_resp.json()
                latest_height = info_data.get("blocks", 0)

        async with session.get(url_tatum, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                for tx in data:
                    tx_time = tx.get("time", 0)
                    tx_hash = tx.get("hash", "")
                    if tx_time < (timestamp_since - 120): continue
                    if last_tx_hash and tx_hash == last_tx_hash: continue
                    
                    outputs = tx.get("outputs", [])
                    for out in outputs:
                        if out.get("address") == address:
                            val = float(out.get("value", "0"))
                            block_num = tx.get("blockNumber")
                            confirmations = tx.get("confirmations", 0)
                            if not confirmations and block_num and latest_height:
                                confirmations = max(0, latest_height - block_num + 1)
                            
                            is_paid, needs_review = validate_amount(val, amount_expected)
                            if is_paid:
                                return True, confirmations, tx_hash, val, needs_review
    except Exception as e:
        logging.error(f"TATUM | Fallback failed: {e}")
        
    return False, 0, "", 0.0, False

def validate_amount(val: float, expected: float) -> tuple[bool, bool]:
    """Determines if amount is acceptable or needs review."""
    low_ok     = expected * 0.995 # -0.5% (Extrem de strict)
    low_review = expected * 0.75  # -25%   (Admin review)
    
    if val >= low_ok:
        return True, False
    elif low_review <= val < low_ok:
        return True, True
    return False, False
