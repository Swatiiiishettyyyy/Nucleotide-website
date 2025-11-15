import os
import redis
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_USERNAME = os.getenv("REDIS_USERNAME")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

print(f"🔍 Connecting to Redis at {REDIS_HOST}:{REDIS_PORT} ...")

try:
    r = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        username=REDIS_USERNAME,
        password=REDIS_PASSWORD,
        decode_responses=True,
        socket_connect_timeout=5
    )

    # Test SET and GET
    r.set("test:key", "hello-redis", ex=10)
    val = r.get("test:key")

    print("✅ Redis connected successfully!")
    print(f"Fetched value: {val}")

    # Check TTL
    ttl = r.ttl("test:key")
    print(f"TTL for test:key = {ttl} seconds")

except redis.AuthenticationError:
    print("❌ Authentication failed! Check your REDIS_USERNAME or REDIS_PASSWORD.")
except redis.ConnectionError:
    print("❌ Connection failed! Check host, port, or network/firewall.")
except Exception as e:
    print(f"⚠️ Unexpected error: {e}")
