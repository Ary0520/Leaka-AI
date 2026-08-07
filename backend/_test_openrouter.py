"""Quick connectivity test for OpenRouter via the app's actual llm.py + .env."""
import asyncio
import sys

# Load .env first
from dotenv import load_dotenv
load_dotenv()

from app.llm import get_llm
from app.config import settings

print(f"Provider : {settings.LLM_PROVIDER}")
print(f"Model    : {settings.LLM_MODEL_OPENROUTER}")

llm = get_llm()
print(f"LLM type : {type(llm).__name__}")

from browser_use.llm.messages import UserMessage

async def test():
    resp = await llm.ainvoke([UserMessage(content="Reply with only the word READY.")])
    return resp.completion  # ChatInvokeCompletion.completion holds the text

result = asyncio.run(test())
print(f"Response : {result}")
print("OpenRouter connectivity: OK" if "READY" in str(result).upper() else f"Unexpected response: {result}")
