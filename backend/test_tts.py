#!/usr/bin/env python3
import asyncio
from tools.gtts_tts import speak_with_gtts

async def test_tts():
    print("Testing gTTS...")
    await speak_with_gtts("Hello! How can I help today?")
    print("Test completed")

if __name__ == "__main__":
    asyncio.run(test_tts())