import aiohttp
import asyncio
import json
import sys

sys.path.append('.')
try:
    from config import TATUM_API_KEY
except ImportError:
    TATUM_API_KEY = "YOUR_API_KEY"

async def get_info():
    url = f"https://api.tatum.io/v3/litecoin/info"
    headers = {"x-api-key": TATUM_API_KEY}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            print(f"Status: {response.status}")
            data = await response.json()
            print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(get_info())
