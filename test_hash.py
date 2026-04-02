import aiohttp
import asyncio
import json
import sys

sys.path.append('.')
try:
    from config import TATUM_API_KEY
except ImportError:
    TATUM_API_KEY = "YOUR_API_KEY"

async def check_tx_hash(tx_hash):
    url = f"https://api.tatum.io/v3/litecoin/transaction/{tx_hash}"
    headers = {"x-api-key": TATUM_API_KEY}
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            print(f"Status: {response.status}")
            data = await response.json()
            print(json.dumps(data, indent=2))

if __name__ == "__main__":
    tx_hash = "fcbb090f59fc5f0929ce02466411f57d81b58adfcf1b9668b45dbf5642d9f0cc"
    asyncio.run(check_tx_hash(tx_hash))
