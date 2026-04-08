import aiohttp
import asyncio
import logging
from datetime import datetime
from config import TATUM_API_KEY

async def check_ltc_transaction(address: str, amount_expected: float, timestamp_since: int, last_tx_hash: str = None) -> tuple[bool, int, str, float, bool]:
    """
    Checks for a transaction to `address` matching `amount_expected`.
    Uses BlockCypher as primary provider and Tatum as fallback.
    
    Returns (found, confirmations, tx_hash, paid_amount, needs_review).
    """
    
    # --- 1. PRIMARY: BlockCypher (Reliable confirmations & timestamps) ---
    try:
        url_bc = f"https://api.blockcypher.com/v1/ltc/main/addrs/{address}/full?limit=5"
        async with aiohttp.ClientSession() as session:
            async with session.get(url_bc, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    txs = data.get("txs", [])
                    logging.info(f"BLOCKCYPHER | Checking {len(txs)} txs for {address}")
                    
                    for tx in txs:
                        time_str = tx.get("confirmed") or tx.get("received")
                        tx_time = 0
                        if time_str:
                            # Parse UTC ISO string: 2026-03-17T16:14:25Z
                            # Replacing Z with +00:00 for fromisoformat
                            ts_str = time_str.replace("Z", "+00:00")
                            dt = datetime.fromisoformat(ts_str)
                            tx_time = int(dt.timestamp()) # dt.timestamp() returns UTC unix
                        
                        tx_hash = tx.get("hash", "")
                        logging.debug(f"BLOCKCYPHER | Comparing Order: {timestamp_since} vs TX: {tx_time} | Hash: {tx_hash[:8]}")
                        
                        if tx_time < (timestamp_since - 120): # 2 min safe buffer
                            logging.debug(f"BLOCKCYPHER | Skipping old tx {tx_hash[:8]}")
                            continue

                        if last_tx_hash and tx_hash == last_tx_hash:
                            logging.info(f"BLOCKCYPHER | Skipping last used tx {tx_hash[:8]}")
                            continue
                            
                        outputs = tx.get("outputs", [])
                        for out in outputs:
                            out_addrs = out.get("addresses", [])
                            if address in out_addrs:
                                # Value in BlockCypher is in Litoshi (1 LTC = 10^8 Litoshi)
                                val = out.get("value", 0) / 100000000.0
                                confirmations = tx.get("confirmations", 0)
                                
                                logging.info(f"BLOCKCYPHER | Match found! Hash: {tx_hash[:8]}, Val: {val}, Confs: {confirmations}")
                                
                                # Use the same logic for accepting
                                is_paid, needs_review = validate_amount(val, amount_expected)
                                if is_paid:
                                    return True, confirmations, tx_hash, val, needs_review

    except Exception as e:
        logging.warning(f"BLOCKCYPHER | Error: {e}. Falling back to Tatum.")

    # --- 2. FALLBACK: Tatum (If BlockCypher is down or rate limited) ---
    url_tatum = f"https://api.tatum.io/v3/litecoin/transaction/address/{address}?pageSize=10"
    headers = {"x-api-key": TATUM_API_KEY}
    
    try:
        async with aiohttp.ClientSession() as session:
            # Get latest height for manual conf calculation
            latest_height = 0
            async with session.get("https://api.tatum.io/v3/litecoin/info", headers=headers) as info_resp:
                if info_resp.status == 200:
                    info_data = await info_resp.json()
                    latest_height = info_data.get("blocks", 0)

            async with session.get(url_tatum, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    logging.info(f"TATUM | Fallback checked {len(data)} txs")
                    
                    for tx in data:
                        tx_time = tx.get("time", 0)
                        tx_hash = tx.get("hash", "")
                        if tx_time < (timestamp_since - 120): continue
                        if last_tx_hash and tx_hash == last_tx_hash: continue
                        
                        outputs = tx.get("outputs", [])
                        for out in outputs:
                            if out.get("address") == address:
                                val = float(out.get("value", "0"))
                                tx_hash = tx.get("hash", "")
                                
                                # Manual calculation
                                block_num = tx.get("blockNumber")
                                confirmations = tx.get("confirmations", 0)
                                if not confirmations and block_num and latest_height:
                                    confirmations = max(0, latest_height - block_num + 1)
                                
                                logging.info(f"TATUM | Fallback Match! Hash: {tx_hash[:8]}, Val: {val}, Confs: {confirmations}")
                                is_paid, needs_review = validate_amount(val, amount_expected)
                                if is_paid:
                                    return True, confirmations, tx_hash, val, needs_review
    except Exception as e:
        logging.error(f"TATUM | Fallback failed: {e}")
        
    return False, 0, "", 0.0, False

def validate_amount(val: float, expected: float) -> tuple[bool, bool]:
    """Determines if amount is acceptable or needs review."""
    low_ok     = expected * 0.995 # -0.5% (Extrem de strict)
    low_review = expected * 0.97  # -3%   (Admin review)
    high_ok    = expected * 1.02  # +2%   (Extrem de strict)
    high_review = expected * 1.15 # +15%  (Admin review)
    
    if low_ok <= val <= high_ok:
        return True, False
    elif low_review <= val <= high_review:
        return True, True
    return False, False
