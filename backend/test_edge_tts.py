import time
from tools.edge_tts import speak_with_edge_tts


def main():
    text = "Hello. This is a test of a more natural, neural voice."
    start = time.time()
    try:
        wav = speak_with_edge_tts(text, voice="en-US-AriaNeural", play=False)
        elapsed = time.time() - start
        print(f"Synthesized to {wav} in {elapsed:.2f}s")
    except Exception as e:
        print("Error synthesizing:", e)


if __name__ == "__main__":
    main()
