# Personal Wispr (Python)

System-wide push-to-talk AI dictation utility inspired by Wispr Flow.

## Features

- Global hotkey hold-to-record using `pynput`
- Microphone capture to temporary WAV files
- Azure OpenAI Whisper transcription
- Optional GPT polishing with rewrite modes:
  - `clean_prose`
  - `casual_chat`
  - `email`
  - `technical`
  - `raw_transcript`
- App-aware rewrite routing (Slack/Discord, Gmail/Outlook, VSCode, Docs/Notion)
- Clipboard-safe paste injection with clipboard restoration
- Retry handling and graceful fallback to raw transcript

## Project Structure

```text
src/
  config.py
  hotkey_listener.py
  audio_recorder.py
  transcription_service.py
  rewrite_service.py
  mode_router.py
  clipboard_manager.py
  injector.py
  main.py
```

## Requirements

- Python 3.11+
- `uv` package manager
- macOS recommended (works best as a system-wide dictation app)

## Setup

1. Install dependencies:

```bash
uv sync
```

2. Create your env file:

```bash
cp .env.example .env
```

3. Fill in Azure settings in `.env`:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_API_VERSION`
- `WHISPER_DEPLOYMENT_NAME`
- `GPT_DEPLOYMENT_NAME`

## Azure Configuration

This app uses:

- `openai` Python SDK (`AzureOpenAI`)
- `azure-identity` (optional, if `USE_AZURE_AD_AUTH=true`)

If using Entra ID authentication, set:

```env
USE_AZURE_AD_AUTH=true
```

and make sure your identity has access to the Azure OpenAI resource.

## Run

```bash
uv run wispr-dictate
```

or:

```bash
uv run python -m src.main
```

## Hotkey

Default push-to-talk hotkey:

```env
PUSH_TO_TALK_HOTKEY=<ctrl>+<shift>+space
```

Behavior:

1. Hold hotkey: recording starts
2. Release hotkey: recording stops and processing begins
3. Transcript is polished (optional) and pasted into the focused app
4. Clipboard is restored to its previous value

## Rewrite Routing

Routing from active app name:

- Slack/Discord -> `casual_chat`
- Gmail/Outlook/Mail -> `email`
- VSCode/JetBrains -> `technical`
- Docs/Notion/Word/Pages -> `clean_prose`

Fallback mode is controlled by `DEFAULT_REWRITE_MODE`.

## macOS Permissions

For global hotkeys, microphone recording, and automated paste, grant permissions:

1. **Microphone** permission for your terminal app / Python host
2. **Accessibility** permission for input automation (for paste injection)
3. If needed, **Input Monitoring** for key listening

You can set these in:
`System Settings -> Privacy & Security`.

## Running in Background

Options:

- Keep a terminal tab open running `uv run wispr-dictate`
- Use `nohup`:

```bash
nohup uv run wispr-dictate > wispr.log 2>&1 &
```

- Use a `launchd` plist for login startup on macOS

## Reliability Notes

- If GPT polishing fails, raw transcript is used
- API calls include retry/backoff
- Audio temp files are cleaned after processing
- Errors are logged and do not crash the hotkey loop

## Extensibility

The module boundaries are designed for future features:

- streaming transcription
- local model fallback
- undo last paste
- transcript history
- tray icon
- realtime dictation
