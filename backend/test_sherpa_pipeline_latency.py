import os
import time
import argparse
from loguru import logger
from dotenv import load_dotenv

from tools.sherpa_integration import (
    sherpa_installed,
    sherpa_models_present,
    transcribe_file_with_sherpa,
    speak_with_sherpa_tts,
)

load_dotenv()

DEFAULT_AUDIO = "test.wav"


def speak_with_pyttsx3(text: str) -> None:
    try:
        import pyttsx3
    except Exception as e:
        raise RuntimeError("pyttsx3 not available: " + str(e))
    engine = pyttsx3.init()
    engine.say(text)
    engine.runAndWait()


def get_openai_response(prompt: str, model: str) -> str:
    import openai

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in the environment.")

    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI(api_key=api_key)
        result = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are Echo, speak briefly."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=128,
        )
        return result.choices[0].message.content.strip()

    openai.api_key = api_key
    response = openai.ChatCompletion.create(
        model=model,
        messages=[{"role": "system", "content": "You are Echo, speak briefly."}, {"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=128,
    )
    return response.choices[0].message["content"].strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", nargs="?", default=DEFAULT_AUDIO)
    parser.add_argument("--model", default=os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini"))
    args = parser.parse_args()

    audio = args.audio

    if not os.path.exists(audio):
        raise FileNotFoundError(f"Audio file not found: {audio}")

    logger.info("Starting Sherpa pipeline latency test")

    # STT
    stt_text = None
    stt_start = time.perf_counter()
    if sherpa_installed() and sherpa_models_present():
        try:
            stt_text = transcribe_file_with_sherpa(audio)
            stt_end = time.perf_counter()
            logger.info(f"Sherpa STT result: {stt_text}")
        except Exception as e:
            stt_end = time.perf_counter()
            logger.error(f"Sherpa STT failed: {e}")
            stt_text = None
    else:
        stt_end = time.perf_counter()
        logger.warning("Sherpa not available or models missing; STT skipped")

    # If STT produced text, use that as prompt. Otherwise use fixed prompt.
    prompt = stt_text if stt_text else "What is the capital of France?"

    # LLM
    llm_start = time.perf_counter()
    answer = get_openai_response(prompt, args.model)
    llm_end = time.perf_counter()

    logger.info(f"LLM answer: {answer}")

    # TTS
    tts_start = time.perf_counter()
    if sherpa_installed() and sherpa_models_present():
        try:
            speak_with_sherpa_tts(answer)
            tts_end = time.perf_counter()
        except Exception as e:
            logger.warning(f"Sherpa TTS failed: {e}. Falling back to pyttsx3")
            speak_with_pyttsx3(answer)
            tts_end = time.perf_counter()
    else:
        # fallback to pyttsx3
        speak_with_pyttsx3(answer)
        tts_end = time.perf_counter()

    total = tts_end - stt_start
    stt_time = stt_end - stt_start
    llm_time = llm_end - llm_start
    tts_time = tts_end - tts_start

    print(f"STT time: {stt_time:.2f}s")
    print(f"LLM time: {llm_time:.2f}s")
    print(f"TTS time: {tts_time:.2f}s")
    print(f"Total (STT+LLM+TTS): {total:.2f}s")


if __name__ == "__main__":
    main()
