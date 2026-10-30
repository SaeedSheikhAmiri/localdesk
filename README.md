# LocalDesk

A small, Persian-first personal AI workspace for macOS: local chat, per-chat instructions and sources, approved memory, and permission-controlled tasks.

**Status: 0.1.0-alpha.1 — source preview for technical early adopters.** This is not an independently audited security product, an autonomous OS operator, or a replacement for a mature assistant platform. The UI is currently Persian/RTL; contributions to localization are welcome.

[راهنمای فارسی](README.fa.md) · [Architecture](docs/ARCHITECTURE.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md)

## What works

- Ollama chat with streaming responses and optional vision-model attachments.
- Durable local conversations; rename, archive, trash/restore, independent branches.
- Per-chat instructions and selected text/document sources.
- An extractive **sources-only** mode that quotes matching excerpts without invoking an LLM.
- Explicitly approved memory notes and correction retrieval; no automatic weight training.
- A local storage dashboard and confirmation-gated cleanup.
- OpenCode tasks with tool approvals and generated macOS file-access policies.

Runtime data is outside this checkout. First launch starts empty: no conversations, profiles, credentials, commercial fonts, screenshots, model weights, or developer accounts are shipped. There is no telemetry, automatic model download, or automatic self-update in LocalDesk code. External engines/providers have their own behavior and licenses.

## Requirements

- macOS with `/usr/bin/sandbox-exec` (checked at startup; no unconfined fallback).
- Python 3.12 or newer. Node.js 20+ is needed only for JavaScript checks.
- [Ollama](https://ollama.com/download), installed independently and running locally.
- For tasks: [OpenCode](https://opencode.ai/docs/) installed independently. Compatibility baseline: 1.19.4; see the permission-list limitation in [SECURITY.md](SECURITY.md). New engine releases require retesting.
- Enough RAM/disk for your chosen model. Model size and speed are not guaranteed.

## Quick start

Download the source archive or clone this repository, then run from its directory:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
ollama pull qwen2.5:7b-instruct
# Start Ollama separately if it is not already running:
# ollama serve
.venv/bin/python app/launch_assistant.py --chat
```

This opens local chat on `http://127.0.0.1:8876`. The launcher uses a one-time login ticket; keep its URL private. To see your own generated password:

```sh
.venv/bin/python app/launch_assistant.py --show-password
```

For tasks, install OpenCode, then omit `--chat`:

```sh
.venv/bin/python app/launch_assistant.py
```

Tasks default to `ollama/qwen2.5:7b-instruct`. Tool reliability depends on your selected model; smaller local models can make mistakes. For optional image chat, explicitly download `qwen3-vl:8b` using Ollama first; this model requires a compatible Ollama version. See its [model page](https://ollama.com/library/qwen3-vl:8b). Image generation, audio, and video understanding are not connected.

To stop only LocalDesk's verified UI/task services:

```sh
.venv/bin/python app/launch_assistant.py --stop
```

Shared Ollama is not stopped. Do not run LocalDesk as root or expose these ports through a public proxy/tunnel.

## Configuration and online opt-in

See [.env.example](.env.example) for variable names. The app **does not automatically load `.env`**. Export only the settings you intend to use. A separate data directory and ports can be selected for another instance; do not change them while that instance is running.

Online tasks are opt-in. Set `LOCALDESK_TASK_MODEL=openrouter/openrouter/free` and provide **your own** `OPENROUTER_API_KEY` through your shell or a trusted secret manager. This sends task context and tool results to the selected provider. Availability, free quotas, and provider retention policies are outside this project's control. Never place a real key in a PR, screenshot, issue, or tracked file.

LocalDesk gives the task engine a separate HOME/XDG data tree. It never imports another OpenCode installation's account, agents, or conversations. Shell commands you approve may still access the engine's environment; local confinement is not a defense against a compromised administrator or every possible malicious process.

## Develop and contribute

```sh
.venv/bin/python -m unittest discover -s tests
node tests/test_chat_logic.cjs
.venv/bin/python scripts/check_source.py
.venv/bin/python scripts/audit_public.py
```

Use synthetic data. Open a focused pull request from a fork; passing checks alone never authorizes a merge. Maintainers review changes and decide what ships. Branch protection must be activated on the real GitHub repository; see [governance setup](docs/GOVERNANCE.md).

## License

Apache-2.0 for LocalDesk code and original generic assets. Dependencies, engines, and models keep their own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md). No model or engine binaries are bundled.
