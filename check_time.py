from datetime import datetime
import time

ts = 1773764065
dt = datetime.fromtimestamp(ts)
print(f"Timestamp {ts} corresponds to: {dt} (local time)")
print(f"Current local time: {datetime.now()}")
print(f"Current UTC time: {datetime.utcnow()}")
print(f"Current timestamp: {time.time()}")
