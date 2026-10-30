# Architecture

Browser (Persian/RTL HTML/CSS/JavaScript) → authenticated Python loopback server → either Ollama chat or the OpenCode task API. SQLite stores conversations, approved notes and corrections. Document/image parsing runs in a bounded, separately confined process. OpenRouter is an optional task-model route, not a bundled account or entitlement.

`app/settings.py` validates model IDs, unprivileged distinct ports and a dedicated data path. Source is read-only from the engine's perspective; mutable data lives outside the repository. OpenCode receives its own HOME/XDG tree. The launcher never copies another application's auth.json or profile/history databases.

Chat context contains current conversation messages (within limits), conversation instructions, selected excerpts, and approved memory when enabled. Retrieval is lexical, not embedding/vector search. In strict mode, deterministic excerpts bypass the model. Persisting history does not mean all history fits into every model request. No fine-tuning or background training is implemented.

Task profiles are instructions + selected model + permissions, not separately trained models. OpenCode handles model/tool iterations; LocalDesk validates session ownership and permission IDs. Network/shell approvals remain explicit.

Loopback defaults: Ollama 11434, task engine 8877, UI 8876. UI and task ports are configurable. This preview supports macOS only; portable paths do not imply portable confinement.
