import asyncio
import logging
import sys
import os

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Add current dir to path to import utils
sys.path.append(os.getcwd())

from utils.tatum import check_ltc_transaction

async def test():
    # Test address that we know has transactions
    address = "ltc1qym8vwm47efug9sr73wtksurmwu7knwd2ykg8qn"
    expected = 0.0039
    # Use a timestamp from yesterday to find the tx
    # Current time is around March 17, 2026. 
    # Transaction fcbb09... was confirmed on 2026-03-17 16:14:25 UTC.
    # Timestamp: 1773764065
    since = 1773760000 
    
    print(f"--- Testing check_ltc_transaction for {address} ---")
    found, confs, tx_hash, paid, review = await check_ltc_transaction(address, expected, since)
    
    print(f"\nRESULTS:")
    print(f"Found: {found}")
    print(f"Confirmations: {confs}")
    print(f"TX Hash: {tx_hash}")
    print(f"Paid Amount: {paid}")
    print(f"Needs Review: {review}")

if __name__ == "__main__":
    asyncio.run(test())
