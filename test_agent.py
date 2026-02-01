#!/usr/bin/env python3
"""Quick test script to diagnose agent issues."""

import asyncio
import logging
from app.agents.univr_agent import UniVRAgent
from app.config import GEMINI_API_KEY, MODEL

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def test():
    print(f"API Key set: {bool(GEMINI_API_KEY)}")
    print(f"API Key length: {len(GEMINI_API_KEY) if GEMINI_API_KEY else 0}")
    print(f"Model: {MODEL}")
    print()
    
    agent = UniVRAgent()
    print(f"Agent client initialized: {agent.client is not None}")
    print()
    
    if not agent.client:
        print("❌ Client not initialized!")
        return
    
    print("Testing simple message without domain...")
    try:
        result = await agent.chat("Hello, this is a test", domain=None)
        print(f"Response length: {len(result.get('response', ''))}")
        print(f"Is demo: {'demo' in result.get('response', '').lower() or '⚠️' in result.get('response', '')}")
        print(f"Response preview: {result.get('response', '')[:200]}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("Testing with domain 'schoolarship'...")
    try:
        result = await agent.chat("What scholarships are available?", domain="schoolarship")
        print(f"Response length: {len(result.get('response', ''))}")
        print(f"Is demo: {'demo' in result.get('response', '').lower() or '⚠️' in result.get('response', '')}")
        print(f"Response preview: {result.get('response', '')[:200]}")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
