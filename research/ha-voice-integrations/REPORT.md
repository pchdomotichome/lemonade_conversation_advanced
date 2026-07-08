# Home Assistant Voice Assistant Integrations: Comprehensive Landscape Report

> Generated 2026-07-08 · depth: standard · 20+ sources · workspace: research/ha-voice-integrations/

## Executive summary

- **Assist is HA's built-in voice pipeline**: a 5-component architecture (Pipeline orchestrator → STT → Conversation Agent → Intent → TTS) with interchangeable components [1][2][3]
- **Speech-to-Phrase** (Feb 2025) enables sub-1-second local STT on Raspberry Pi 4 by auto-generating phrases from your HA config — a key differentiator from Whisper [13][14]
- **Wyoming protocol** is the standard for linking voice components; used by 8.9% of HA installations, with an ecosystem covering wake word, STT, and TTS [6][7]
- **LLM-based conversation agents** (OpenAI, Ollama, Anthropic, Google) can control HA devices via the Assist API with entity exposure controls [6][41]
- **Streaming responses** (HA 2025.3) allow LLMs to stream chunked output, enabling faster command execution [7]
- **MCP integration** means HA tools can be exposed to external AI apps (Claude desktop, etc.) and HA can consume external MCP servers [8]
- **Privacy-first local processing** is the #1 value proposition driving HA voice adoption [1]
- **Voice PE sold out in 23 minutes** at launch (Dec 2024), with known microphone sensitivity issues driving user frustration [14][3]
- **Config flows** use Data Entry Flow framework with `reconfigure` steps, `OptionsFlowWithReload`, subentry flows, and translation references [1-12 in F4]
- **Community is building alternative NLU engines** (e.g., Sophia NLU) to bridge the gap between rigid built-in matching and GPU-hungry local LLMs [10/F5]

## 1. Official HA Voice Pipeline Architecture

### 1.1 The Assist Pipeline

Assist is the built-in voice assistant in Home Assistant, introduced in HA 2023.2, running as the `assist_pipeline` integration [1][82]. The architecture is a 5-component pipeline [2]:

```
Voice Satellite → STT → Conversation Agent → Intent Handler → TTS → Audio Output
     ↑                                                                    ↓
     └─────────────────────────── Pipeline Orchestrator ──────────────────┘
```

1. **Pipeline Orchestrator** (`assist_pipeline` integration) — sequences all components
2. **Speech-to-Text (STT)** — converts audio to text
3. **Conversation Agent** — processes text, generates response
4. **Intent Handler** — executes the intent (device control, queries)
5. **Text-to-Speech (TTS)** — converts response text to audio

Each component is interchangeable — you can mix cloud and local engines freely [1].

### 1.2 Conversation Entity Interface

The `ConversationEntity` class (from `homeassistant.components.conversation.ConversationEntity`) is the interface custom conversation agents must implement [5]:

- **Input**: `ConversationInput` with fields: `text`, `context`, `conversation_id`, `language`, `continue_conversation`
- **Output**: `ConversationResult` containing an `IntentResponse`
- **Action**: `conversation.process` — the programmatic API for sending text to conversation agents [4][16]

### 1.3 Intent Recognition

Intent matching uses **hassil**, a template-matching engine that matches user input against sentence templates with slots [3]:

```
(turn | switch) on [the] {area} lights
```

- 38+ built-in intents: `HassTurnOn`, `HassTurnOff`, `HassGetState`, `HassLightSet`, `HassClimateSetTemperature`, `HassStartTimer`, `HassMediaSearchAndPlay`, `HassVacuumStart`, `HassFanSetSpeed`, etc. [6]
- Intents are provided by their respective domain integrations

### 1.4 Custom Sentences

Custom sentences are defined via YAML in `config/custom_sentences/<language>/` directories [4][13]:

- Support slot-based matching with built-in entity/area lists (`{name}`, `{area}`)
- Can trigger either built-in intents or custom `intent_script` actions
- Sentence triggers for automations with wildcard support (e.g., `play {album} by {artist}`)
- Custom sentences are the primary extensibility mechanism for power users [8/F5]

### 1.5 STT and TTS Engines

**Local STT options** [7][12]:
| Engine | Type | Speed (RPi4) | Best For |
|--------|------|-------------|----------|
| Speech-to-Phrase | Close-ended, auto-generated | <1s | HA device control |
| Whisper / Faster Whisper | Open-ended | ~8s (RPi4), <1s (Intel NUC) | LLM conversations |
| Vosk | Open-ended | Variable | Alternative option |

**Local TTS** [7][34]:
| Engine | Speed (RPi4) | Quality |
|--------|-------------|---------|
| Piper | 1.6x real-time | Neural, good |
| Speech-to-Phrase | N/A | N/A (STT only) |

Speech-to-Phrase is the recommended local STT for device control — it auto-generates phrases and fine-tunes a model based on your HA devices, areas, and sentence triggers [13][14].

### 1.6 STT and TTS Entity Interfaces

**STT Entity** (`SpeechToTextEntity`) [8]:
- Properties: `supported_languages`, `supported_formats` (wav/ogg), `supported_codecs` (pcm/opus), `supported_bit_rates`, `supported_sample_rates`, `supported_channels`
- Streams audio data and returns text

**TTS Entity** (`TextToSpeechEntity`) [9]:
- 1-shot: `get_tts_audio` / `async_get_tts_audio`
- Streaming: `async_stream_tts_audio(TTSAudioRequest) -> TTSAudioResponse` — for LLM chunked output
- Streaming TTS is critical for LLM agents that generate text in chunks

### 1.7 Voice Satellites

Voice Satellites are ESPHome-based ESP32 devices (or Android/iOS/Linux apps) that detect wake words, capture speech, send it to HA, and play back responses [10]:

- **Voice Preview Edition** — official hardware, sold out in 23 minutes at launch (Dec 2024) [14]
- **ESP32-based** — DIY $13 voice remotes, S3-BOX-3 with display [12/F5]
- **Linux Voice Assistant** — experimental x64/ARM64 smart speaker using ESPHome protocol
- Satellites communicate with HA via the Wyoming protocol

## 2. Popular Custom Integrations

### 2.1 HA Cloud (Nabu Casa)

- **Adoption**: 30.4% of active installations [2]
- **Features**: Cloud STT/TTS, Google Assistant linking, Alexa linking, secure remote access [1/F2]
- **Architecture**: Creates an assist pipeline with cloud STT/TTS engines via config flow [3/F2]
- **Introduced**: HA 0.60

### 2.2 Wyoming Protocol Ecosystem

Wyoming is the standard peer-to-peer TCP protocol for linking voice pipeline components (JSONL + PCM audio) [6]:

| Component | Repo | Stars | Notes |
|-----------|------|-------|-------|
| wyoming | OHF-Voice/wyoming | 374 | Core protocol, v1.10.0 |
| wyoming-faster-whisper | rhasspy/wyoming-faster-whisper | 351 | Local STT, v3.4.1 |
| wyoming-openWakeWord | OHF-Voice | — | Wake word detection |
| wyoming-piper | OHF-Voice | — | Local TTS |
| wyoming-vosk | — | — | Alternative STT |

**HA integration**: 8.9% adoption, introduced in 2023.5, maintained by @synesthesiam [7]

### 2.3 Piper TTS

- **Original repo** (rhasspy/piper): 11.2k stars, **archived Oct 2025** [8/F2]
- **New repo** (OHF-Voice/piper1-gpl): 4.7k stars, GPL-3.0, latest v1.4.2 [9/F2]
- Fast local neural TTS with espeak-ng phonemization
- Installable via `pip install piper-tts`

### 2.4 Google Assistant Integration

- Core HA integration with smart_home protocol and trait system [4/F2]
- Files: `__init__.py`, `config_flow.py`, `smart_home.py`, `trait.py`, etc.
- Routes voice commands from Google Assistant to HA entities

### 2.5 Alexa Integration

- Core HA integration with capabilities, handlers, and intent handling [5/F2]
- Files: `__init__.py`, `capabilities.py`, `handlers.py`, `intent.py`, `smart_home.py`, etc.
- Similar architecture to Google Assistant — exposes HA entities as Alexa-compatible devices

### 2.6 Other Notable Integrations

- **openWakeWord / microWakeWord**: Wake word detection engines; microWakeWord supports "okay nabu", "hey jarvis", "alexa" [12/F5]
- **Speech-to-Phrase**: HA's close-ended STT engine (Feb 2025) — auto-generates phrases from HA config [13][14]
- **Sophia NLU**: Community-built alternative NLU engine bridging rigid built-in matching and local LLMs [10/F5]

## 3. Modern Voice Pipeline Patterns

### 3.1 STT → Intent → TTS Pipeline

The canonical voice pipeline in 2025-2026 [1][5/F3]:

```
Audio Input → STT (Whisper/Speech-to-Phrase) → Text
    → Conversation Agent (Built-in/LLM) → Intent + Response Text
    → TTS (Piper/Cloud) → Audio Output
```

Each component is swappable. The pipeline orchestrator sequences them.

### 3.2 LLM-Based Conversation Agents

LLMs can serve as conversation agents in the pipeline [6/F3]:

- **Supported**: OpenAI, Anthropic (Claude), Ollama (local), Google Generative AI, OpenRouter
- **Assist mode**: LLM controls HA devices via the Assist API
- **No control mode**: LLM only chats, no device control
- **Entity exposure**: Users control which entities the LLM can access
- **Scripts as tools**: Exposed scripts become callable LLM tools (not entities) with a **128-tool hard limit** [11/F3]
- **Field descriptions**: Capped at 128 characters per field; script descriptions capped at ~1024 characters [11][15/F3]

### 3.3 Multi-Turn Conversation

- HA 2025.2 shared conversation history between built-in and LLM fallback agents [9/F3]
- `continue_conversation` field in `ConversationInput` enables follow-up context
- **Limitation**: Built-in system fails on many follow-up questions; users actively request better multi-turn support [5/F5]

### 3.4 Streaming Responses

- Added in HA 2025.3 for Ollama and OpenAI [7/F3]
- LLMs stream text chunks → TTS processes each chunk → audio plays incrementally
- Commands execute as soon as they appear in the stream, without waiting for full response
- TTS streaming via `async_stream_tts_audio()` handles chunked LLM output [9/F1]

### 3.5 "Prefer Handling Commands Locally"

- Setting introduced in HA 2024.12 [10/F3]
- Routes simple commands to built-in agent first, falls back to LLM only for unrecognized input
- Key pattern for cost/latency optimization with cloud LLMs

### 3.6 MCP Integration

- HA can consume external MCP servers and expose its tools to other AI apps [8/F3]
- Bidirectional: HA → Claude Desktop, Claude Desktop → HA
- Enables HA voice tools to be used in any MCP-compatible AI application

### 3.7 Custom Sentence Framework

- YAML-based in `config/custom_sentences/<language>/` [4/F1][13/F3]
- Supports `{name}`, `{area}` lists matching HA entities/areas
- Sentence triggers for automations with wildcard support
- Can trigger `intent_script` actions for custom behavior

## 4. Configuration UI Patterns

### 4.1 Config Flow Framework

HA config flows use the **Data Entry Flow** framework [1/F4]:

- Config flows subclass `ConfigFlow` and define steps via `async_step_<step_id>` methods
- **Reserved step names**: `user`, `reconfigure`, `reauth`, `import`, plus discovery steps (`bluetooth`, `dhcp`, `hassio`, `homekit`, `mqtt`, `ssdp`, `usb`, `zeroconf`) [2/F4]

### 4.2 Modern Config Flow Patterns

| Pattern | Description | Source |
|---------|-------------|--------|
| `reconfigure` step | Change config data (host/port) without OptionsFlow | [5/F4] |
| `reauth` step | Handle authentication failures | [2/F4] |
| `OptionsFlowWithReload` | Auto-reload integration on option changes | [3/F4] |
| `add_suggested_values_to_schema()` | Pre-populate forms from existing config | [11/F4] |
| `async_show_progress` + `progress_task` | Long-running async operations (OAuth) with progress UI | [12/F4] |
| `VERSION` / `MINOR_VERSION` | Config entry migration; minor bumps are backwards-compatible | [4/F4] |

### 4.3 Subentry Flows

`ConfigSubentryFlow` enables per-device entity configuration [9/F4]:

- MQTT integration demonstrates this pattern for 21+ platform types
- Imports `ConfigSubentryFlow` and `SubentryFlowResult` from `homeassistant.config_entries`
- Each device/entity gets its own subentry flow

### 4.4 Translations

Translations are structured in `strings.json` [6-8/F4]:

```json
{
  "config": { ... },
  "options": { ... },
  "config_subentries": {
    "device_type": { ... }
  }
}
```

- `config_subentries` is a map-of-maps keyed by subentry type
- Reference syntax: `[%key:component::domain::path::key%]` enables reuse across integrations
- Supports `flow_title`, `progress`, `create_entry` for dynamic UI

### 4.5 Real-World Example: HACS Config Flow

The HACS integration demonstrates modern patterns [10/F4]:

- GitHub Device OAuth flow with `async_show_progress`
- `VERSION = 1` with combined ConfigFlow + OptionsFlow
- `async_get_options_flow` static callback pattern
- Progress UI with device activation URL and user code

## 5. Key Features Users Expect

### 5.1 Must-Have Features

1. **Privacy-first local processing** — #1 value proposition; users explicitly cite not wanting "big tech" to have their home device config [1/F5]
2. **Fast response latency** — sub-1-second for simple commands; users report Voice PE and RPi4 as "unusably slow" after updates [6/F5]
3. **Reliable wake word detection** — English-only for openWakeWord; 3 wake words for microWakeWord; non-English users lack options [7/F5]
4. **Multi-turn conversation** — follow-up questions that reference recent commands; currently limited [5/F5]
5. **Custom sentence extensibility** — power users need wildcard triggers and custom intent handling [8/F5]

### 5.2 Power-User Patterns

- **LLM fallback**: Claude/OpenAI as backup for failed local intents; users convert successful LLM responses to local automations weekly [4/F5]
- **Alternative NLU engines**: Community building engines between rigid built-in matching and GPU-hungry local LLMs [10/F5]
- **DIY satellite hardware**: ESP32-based $13 remotes, S3-BOX-3, Linux voice assistants — hardware variety is a feature [12/F5]

### 5.3 Known Pain Points

- **Voice PE hardware issues**: Poor microphone pickup, requires loud speaking, slow after HA Core updates [3/F5]
- **TTS reliability**: Piper and Google TTS fail in certain configurations, especially on mobile companion apps [11/F5]
- **Satellite scaling**: ~5 simultaneous streaming satellites overwhelm a Raspberry Pi 4; external Wyoming servers needed for larger setups [9/F5]
- **Entity exposure overhead**: Users must manually expose entities, assign areas, and create aliases — rigid compared to Alexa/Google [2/F5]
- **Non-English support**: Wake words English-only; sentence coverage limited for non-English languages [7/F5]

## Comparison Table: Voice Pipeline Options

| Component | Local Option | Cloud Option | Speed (RPi4) | Best For |
|-----------|-------------|--------------|-------------|----------|
| **STT** | Speech-to-Phrase | HA Cloud (Nabu Casa) | <1s | Device control |
| **STT** | Whisper / Faster Whisper | HA Cloud | ~8s | LLM conversations |
| **Conversation** | Built-in (hassil) | OpenAI / Claude / Ollama | <1s | Device control |
| **Conversation** | Built-in + LLM fallback | Cloud LLMs | 1-5s | Complex queries |
| **TTS** | Piper | HA Cloud (Nabu Casa) | 1.6x realtime | All use cases |
| **Wake Word** | openWakeWord / microWakeWord | — | Real-time | Voice activation |

## Open Questions

1. **Sophia NLU and alternative NLU engines**: What is the current state of community-built NLU engines? Are any production-ready?
2. **Non-English voice support**: What is the roadmap for multi-language wake words, sentences, and TTS?
3. **Satellite scaling**: What is the recommended architecture for 10+ voice satellites in a large home?
4. **LLM cost optimization**: How do power users balance local vs. cloud LLM routing for cost?
5. **Config flow sections**: What are the latest patterns for collapsible form sections in HA 2025.x config flows?

## Sources

[1] Home Assistant Voice Control — https://www.home-assistant.io/voice_control/ (accessed 2026-07-08)
[2] HA Cloud Integration — https://www.home-assistant.io/integrations/cloud/ (accessed 2026-07-08)
[3] HA Voice Remote Local Assistant — https://www.home-assistant.io/voice_control/voice_remote_local_assistant/ (accessed 2026-07-08)
[4] HA Conversation Integration — https://www.home-assistant.io/integrations/conversation/ (accessed 2026-07-08)
[5] HA Developer Docs: Voice Overview — https://developers.home-assistant.io/docs/voice/overview (accessed 2026-07-08)
[6] Wyoming Protocol — https://github.com/OHF-Voice/wyoming (v1.10.0, accessed 2026-07-08)
[7] HA Wyoming Integration — https://www.home-assistant.io/integrations/wyoming/ (accessed 2026-07-08)
[8] Piper TTS (archived) — https://github.com/rhasspy/piper (archived Oct 2025)
[9] Piper1-GPL — https://github.com/OHF-Voice/piper1-gpl (v1.4.2, accessed 2026-07-08)
[10] Wyoming Faster Whisper — https://github.com/rhasspy/wyoming-faster-whisper (v3.4.1, accessed 2026-07-08)
[11] HA Assist Pipeline Integration — https://www.home-assistant.io/integrations/assist_pipeline/ (accessed 2026-07-08)
[12] HA Voice Control Overview — https://www.home-assistant.io/voice_control/ (accessed 2026-07-08)
[13] HA Blog: Speech-to-Phrase — https://www.home-assistant.io/blog/2025/02/13/voice-chapter-9-speech-to-phrase/ (2025-02-13)
[14] HA Blog: Voice Chapter 9 — https://www.home-assistant.io/blog/2025/02/13/voice-chapter-9-speech-to-phrase/ (2025-02-13)
[15] HA Exposing Scripts to LLMs — https://www.home-assistant.io/voice_control/exposing_scripts_to_llms/ (accessed 2026-07-08)
[16] HA OpenAI Conversation — https://www.home-assistant.io/integrations/openai_conversation/ (accessed 2026-07-08)
[17] HA Custom Sentences — https://www.home-assistant.io/voice_control/custom_sentences/ (accessed 2026-07-08)
[18] HA About Wake Word — https://www.home-assistant.io/voice_control/about_wake_word/ (accessed 2026-07-08)
[19] HA Developer Docs: Config Flow — https://developers.home-assistant.io/docs/config_entries_config_flow_handler (accessed 2026-07-08)
[20] HA Developer Docs: Data Entry Flow — https://developers.home-assistant.io/docs/data_entry_flow_index (accessed 2026-07-08)
[21] HA Developer Docs: Options Flow — https://developers.home-assistant.io/docs/core/integration/options_flow (accessed 2026-07-08)
[22] HA Developer Docs: Internationalization — https://developers.home-assistant.io/docs/internationalization/core (accessed 2026-07-08)
[23] HA Developer Docs: Conversation Entity — https://developers.home-assistant.io/docs/core/entity/conversation (accessed 2026-07-08)
[24] HA Developer Docs: STT Entity — https://developers.home-assistant.io/docs/core/entity/stt (accessed 2026-07-08)
[25] HA Developer Docs: TTS Entity — https://developers.home-assistant.io/docs/core/entity/tts (accessed 2026-07-08)
[26] HA Developer Docs: Built-in Intents — https://developers.home-assistant.io/docs/intent_builtin/ (accessed 2026-07-08)
[27] HA Developer Docs: Intent Recognition — https://developers.home-assistant.io/docs/voice/intent-recognition (accessed 2026-07-08)
[28] HA Cloud Assist Pipeline Source — https://github.com/home-assistant/core/blob/dev/homeassistant/components/cloud/assist_pipeline.py (accessed 2026-07-08)
[29] HA Google Assistant Source — https://github.com/home-assistant/core/tree/dev/homeassistant/components/google_assistant (accessed 2026-07-08)
[30] HA Alexa Source — https://github.com/home-assistant/core/tree/dev/homeassistant/components/alexa (accessed 2026-07-08)
[31] HA MQTT Config Flow — https://github.com/home-assistant/core/blob/dev/homeassistant/components/mqtt/config_flow.py (accessed 2026-07-08)
[32] HACS Config Flow — https://github.com/hacs/integration/blob/main/custom_components/hacs/config_flow.py (accessed 2026-07-08)
[33] Reddit: HA Voice Discussion — https://old.reddit.com/r/homeassistant/comments/1unipyp/home_assistant_voice/ (2026-07-04)
[34] Reddit: Voice Satellite Solutions — https://old.reddit.com/r/homeassistant/comments/1uqmz55/ (2026-07-08)
[35] Reddit: Piper TTS Issues — https://old.reddit.com/r/homeassistant/comments/1uqcer0/ (2026-07-08)
[36] GitHub Issue: Multi-turn Conversation — https://github.com/home-assistant/core/issues/142310 (2025-07-26)
[37] GitHub Issue: Voice Slow on RPi4 — https://github.com/home-assistant/core/issues/102461 (2024-06)
[38] GitHub Issue: Voice PE Slow After Update — https://github.com/home-assistant/core/issues/161014 (accessed 2026-07-08)
[39] HA Developer Docs: Conversation Entity (dev) — https://developers.home-assistant.io/docs/core/entity/conversation (accessed 2026-07-08)
[40] HA Voice Built-in Sentences — https://www.home-assistant.io/voice_control/builtin_sentences/ (accessed 2026-07-08)
[41] HA OpenAI Conversation Integration — https://www.home-assistant.io/integrations/openai_conversation/ (accessed 2026-07-08)
