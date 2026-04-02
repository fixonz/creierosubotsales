import aiohttp
import asyncio
import json
import sys

# Load API key from config
sys.path.append('.')
try:
    from config import TATUM_API_KEY
except ImportError:
    TATUM_API_KEY = "YOUR_API_KEY"

async def debug_tatum(address):
    url = f"https://api.tatum.io/v3/litecoin/transaction/address/{address}?pageSize=5"
    headers = {"x-api-key": TATUM_API_KEY}
    
    print(f"--- TATUM DEBUG FOR {address} ---")
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            print(f"Status: {response.status}")
            if response.status == 200:
                data = await response.json()
                print(json.dumps(data, indent=2))
            else:
                print(await response.text())

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(debug_tatum(sys.argv[1]))
    else:
        print("Usage: python debug_tatum.py <LTC_ADDRESS>")
