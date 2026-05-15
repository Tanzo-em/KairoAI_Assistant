#!/usr/bin/env python3
import asyncio
from tools.piper_tts import speak_with_piper

async def test_tts():
    print("Testing Piper TTS...")
    await asyncio.to_thread(speak_with_piper, "Hello! How can I help today?")
    print("Test completed")

if __name__ == "__main__":
    asyncio.run(test_tts())