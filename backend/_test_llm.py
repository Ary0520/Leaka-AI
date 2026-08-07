import os, asyncio
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["OLLAMA_MODEL"] = "qwen3:4b"
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"

from app.llm import get_llm
llm = get_llm()
print(f"LLM type: {type(llm).__name__}, model: {llm.model}")

from browser_use.llm.messages import UserMessage

async def test():
    resp = await llm.ainvoke([UserMessage(content="Reply with only the word READY.")])
    print(f"Response type: {type(resp).__name__}")
    attrs = [f for f in dir(resp) if not f.startswith("_")]
    print(f"Response attrs: {attrs[:20]}")
    # Try common content accessors
    for attr in ["content", "text", "message", "output", "completion"]:
        val = getattr(resp, attr, None)
        if val is not None:
            print(f"  .{attr} = {str(val)[:100]}")
    return resp

asyncio.run(test())
print("LLM connectivity test complete")
