from dotenv import load_dotenv; load_dotenv(override=True)
import os
key = os.getenv("OPENROUTER_API_KEY", "")
prefix = key[:20] if len(key) >= 20 else key
suffix = key[-4:] if len(key) > 4 else ""
print(f"Key: {prefix}...{suffix} ({len(key)} chars)")
