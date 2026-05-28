# KairoAI_Assistant

## Realtime voice pipeline

The backend now uses OpenAI Realtime as the active voice pipeline:

- `OPENAI_REALTIME_MODEL` defaults to `gpt-realtime-2`
- `OPENAI_REALTIME_VOICE` defaults to `marin`
- `OPENAI_REALTIME_TRANSCRIPTION_MODEL` defaults to `gpt-4o-transcribe`

Realtime now owns live VAD, interruption handling, transcription, LLM responses,
and speech output. Local media controls, reminders, current info, and local
date/time are exposed as Realtime function tools.

The backend gates completed Realtime transcripts before creating a response:
while Echo is speaking it ignores speech, and while music is audible it ignores
speech unless the transcript starts with `Echo`.

Keep `OPENAI_API_KEY` set before running the backend.
