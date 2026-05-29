# KairoAI Assistant

KairoAI Assistant is a local realtime voice assistant named Riko. It uses the
OpenAI Realtime API for live speech input, turn detection, transcription,
reasoning, and spoken responses, while keeping local tools for reminders,
alarms, media playback, current information, and UI status updates.

The project has two parts:

- `backend/` - Python realtime voice pipeline with microphone and speaker I/O.
- `riko-ui/` - Next.js dashboard that shows the assistant connection and state.

## Features

- Realtime voice conversation through the OpenAI Realtime API.
- Local reminders and alarms.
- Media control support for playback commands.
- Current information tools for weather, news, scores, prices, and time queries.
- WebSocket UI status updates on `ws://localhost:8765`.
- Next.js frontend for monitoring the assistant state.

## Requirements

- Python 3.12 or newer
- Node.js 20 or newer
- `uv` for Python dependency management
- An OpenAI API key
- Working microphone and speaker/audio output

Some systems may also need audio/runtime packages such as PortAudio, FFmpeg, or
MPV for microphone input, speech playback, and media control.

## Clone The Repo

```bash
git clone https://github.com/Tanzo-em/KairoAI_Assistant.git
cd KairoAI_Assistant
```

## Backend Setup

Create a backend environment file:

```bash
cd backend
cp .env.example .env 2>/dev/null || touch .env
```

Add your OpenAI key to `backend/.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

Optional realtime settings:

```env
OPENAI_REALTIME_MODEL=gpt-realtime-2
OPENAI_REALTIME_VOICE=marin
OPENAI_REALTIME_TRANSCRIPTION_MODEL=gpt-4o-transcribe
```

Install dependencies:

```bash
uv sync
```

Run the assistant backend:

```bash
uv run python main.py
```

When the backend starts, it opens the local audio pipeline and starts the UI
WebSocket server at `ws://localhost:8765`.

## Frontend Setup

Open a second terminal from the repo root:

```bash
cd riko-ui
npm install
npm run dev
```

Open the UI in your browser:

```text
http://localhost:3000
```

Keep the backend running while using the UI so it can connect to the local
WebSocket server.

## Development Commands

Backend:

```bash
cd backend
uv sync
uv run python main.py
```

Frontend:

```bash
cd riko-ui
npm install
npm run dev
npm run build
npm run lint
```

## Notes

- Runtime logs are written under `backend/logs/`.
- Reminder data is stored under `backend/data/`.
- Model files and other generated runtime artifacts should not be committed.
- Make sure `OPENAI_API_KEY` is set before starting the backend.
