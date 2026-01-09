# Speech-to-Text (Voice Prompt Input)

## UI

- `New task` page includes a `Voice` button overlaid in the bottom-right of the prompt editor.
- Clicking `Voice` starts microphone recording; clicking `Stop` ends recording and transcribes into the prompt.

## Settings

- `Settings -> Speech-to-text`
  - `offline`: local transcription via Whisper
  - `online`: online transcription via SpeechRecognition

Settings are persisted in `~/.midoriai/agents-runner/state.json` under `settings.stt_mode`.

## Implementation

- Recording: `agents_runner/stt/mic_recorder.py`
  - Uses `ffmpeg` with PulseAudio input (`-f pulse -i default`) to record a 16kHz mono WAV file.
- Transcription:
  - Offline: `agents_runner/stt/transcribe.py` uses `faster-whisper` (`WhisperModel("base")`) with a download root under `~/.midoriai/agents-runner/models/faster-whisper/`.
  - Online: `agents_runner/stt/transcribe.py` uses `SpeechRecognition` with `recognize_google` against the recorded WAV.
- Threading: transcription runs in a `QThread` via `agents_runner/stt/qt_worker.py` to keep the UI responsive.

## Notes

- If `ffmpeg` cannot access an input device, recording fails and the UI shows a warning.
- The recorded temporary WAV file is deleted after transcription completes (success or error).

