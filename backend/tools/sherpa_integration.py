import os
import time
from pathlib import Path
from loguru import logger
from tools.audio_playback import (
    play_wav_interruptible,
    playback_generation,
    was_playback_stopped_since,
)

MODEL_DIR = Path(__file__).resolve().parent.parent / "models" / "sherpa"


def sherpa_installed() -> bool:
    try:
        import sherpa_onnx  # type: ignore
        return True
    except Exception:
        return False


def sherpa_models_present() -> bool:
    # We look for a couple of sentinel files for common model types
    if not MODEL_DIR.exists():
        return False

    # transducer style: tokens.txt + encoder.onnx + decoder.onnx + joiner.onnx
    transducer_files = ["tokens.txt", "encoder.onnx", "decoder.onnx", "joiner.onnx"]
    if all((MODEL_DIR / f).exists() for f in transducer_files):
        return True

    # sense-voice / other single-file models
    single_model = list(MODEL_DIR.glob("*.onnx"))
    if len(single_model) > 0:
        return True

    # TTS models (various names) - presence means offline TTS is possible
    tts_candidates = list(MODEL_DIR.glob("*tts*")) + list(MODEL_DIR.glob("*.onnx"))
    if len(tts_candidates) > 0:
        return True

    return False


def transcribe_file_with_sherpa(file_path: str) -> str:
    """Attempt to transcribe an audio file using sherpa_onnx.

    This helper needs Sherpa models under `backend/models/sherpa`.
    If models are missing, it raises RuntimeError with instructions.
    """
    if not sherpa_installed():
        raise RuntimeError("sherpa_onnx is not installed in the environment")

    if not sherpa_models_present():
        raise RuntimeError(
            f"Sherpa models not found under {MODEL_DIR}. Please download the appropriate pre-trained models and place them there. See https://k2-fsa.github.io/sherpa/onnx/ for details."
        )

    import sherpa_onnx as s  # type: ignore

    # Basic strategy: try common factory methods. This code assumes models are in MODEL_DIR
    # and tries `from_sense_voice` first, then `from_transducer`.
    # The exact filenames may vary depending on the model; users should adapt MODEL_DIR contents.

    # try sense-voice
    try:
        tokens = str(MODEL_DIR / "tokens.txt")
        model = str(next(MODEL_DIR.glob("*.onnx")))
        recognizer = s.OfflineRecognizer.from_sense_voice(model=model, tokens=tokens)
    except Exception:
        # try transducer
        try:
            encoder = str(MODEL_DIR / "encoder.onnx")
            decoder = str(MODEL_DIR / "decoder.onnx")
            joiner = str(MODEL_DIR / "joiner.onnx")
            tokens = str(MODEL_DIR / "tokens.txt")
            recognizer = s.OfflineRecognizer.from_transducer(
                encoder=encoder, decoder=decoder, joiner=joiner, tokens=tokens
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to create Sherpa OfflineRecognizer: {e}. Ensure correct model files are placed in {MODEL_DIR}."
            )

    # create stream and feed wave file
    try:
        stream = recognizer.create_stream()
        # sherpa_onnx provides a helper `write_wave` but easiest is to load waveform samples as floats in [-1,1]
        # We'll use the library helper to write a wav and then feed samples
        import soundfile as sf

        data, sr = sf.read(file_path)
        # If stereo, take first channel
        if len(data.shape) > 1:
            data = data[:, 0]

        # Sherpa expects float32 array in range [-1,1]
        stream.accept_waveform(sr, data.tolist())
        recognizer.decode_stream(stream)
        result = stream.result
        if hasattr(result, 'text'):
            return result.text
        # fallback: stringify
        return str(result)
    except Exception as e:
        raise RuntimeError(f"Sherpa transcription failed: {e}")


def speak_with_sherpa_tts(text: str) -> None:
    """Try to synthesize speech using Sherpa offline TTS models under models/sherpa.

    Falls back to raising a RuntimeError with instructions if models are missing.
    """
    if not sherpa_installed():
        raise RuntimeError("sherpa_onnx is not installed in the environment")
    if not sherpa_models_present():
        raise RuntimeError(
            f"Sherpa TTS models not found under {MODEL_DIR}. Please download an OfflineTts model and place it there. See https://k2-fsa.github.io/sherpa/onnx/ for details."
        )

    import sherpa_onnx as s  # type: ignore
    import tempfile
    from pathlib import Path
    import subprocess

    generation = playback_generation()

    # Try to instantiate a default OfflineTts using a detected model file
    try:
        model_file = next(MODEL_DIR.glob("*tts*.onnx"), None)
        if model_file is None:
            model_file = next(MODEL_DIR.glob("*.onnx"))
        tts_config = s.OfflineTtsConfig()
        tts = s.OfflineTts(tts_config)
        # The exact API to synthesize may vary; try high-level helper functions
        wav_path = Path(tempfile.mktemp(suffix=".wav"))
        # Some Sherpa TTS provide a `synthesize` or `apply` method; try common names
        if hasattr(tts, 'synthesize'):
            tts.synthesize(text, str(wav_path))
        elif hasattr(tts, 'speak'):
            tts.speak(text, str(wav_path))
        else:
            # fallback: try to call `tts.run` or `tts.apply`
            if hasattr(tts, 'apply'):
                tts.apply(text, str(wav_path))
            else:
                raise RuntimeError('Unknown OfflineTts API - cannot synthesize')

        # play generated wav
        if not was_playback_stopped_since(generation):
            play_wav_interruptible(wav_path, generation=generation)

        wav_path.unlink(missing_ok=True)
    except Exception as e:
        raise RuntimeError(f"Sherpa TTS failed: {e}")
