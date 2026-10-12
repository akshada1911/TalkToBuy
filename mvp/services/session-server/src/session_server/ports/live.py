"""LivePort: a real-time speech/avatar conversation with tool calling."""

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

MediaMode = Literal["avatar", "audio_only"]
Scheduling = Literal["SILENT", "WHEN_IDLE", "INTERRUPT"]


@dataclass(frozen=True)
class AudioOut:
    pcm: bytes  # 24 kHz 16-bit LE mono


@dataclass(frozen=True)
class VideoChunk:
    mp4: bytes


@dataclass(frozen=True)
class InputTranscript:
    text: str
    final: bool


@dataclass(frozen=True)
class OutputTranscript:
    text: str
    final: bool


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCallCancelled:
    ids: tuple[str, ...]


@dataclass(frozen=True)
class Interrupted:
    pass


@dataclass(frozen=True)
class TurnComplete:
    pass


@dataclass(frozen=True)
class GoAway:
    time_left_s: float | None


@dataclass(frozen=True)
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0


LiveEvent = (
    AudioOut
    | VideoChunk
    | InputTranscript
    | OutputTranscript
    | ToolCall
    | ToolCallCancelled
    | Interrupted
    | TurnComplete
    | GoAway
    | Usage
)


@dataclass
class LiveConfig:
    system_instruction: str
    tools: list[dict[str, Any]]  # provider-neutral tool specs from mvp/contracts/tools.schema.json
    media_mode: MediaMode = "avatar"
    language_code: str = "hi-IN"
    vocabulary: list[str] = field(default_factory=list)


class LivePort(Protocol):
    async def connect(self, config: LiveConfig) -> None: ...

    async def reconnect(self, media_mode: MediaMode) -> None:
        """Reconnect (same conversation via resumption), optionally switching media mode."""
        ...

    def events(self) -> AsyncIterator[LiveEvent]: ...

    async def send_audio(self, pcm_16k: bytes) -> None: ...

    async def send_video(self, jpeg: bytes) -> None: ...

    async def send_audio_end(self) -> None:
        """The shopper stopped talking and the mic is paused (browser voice detection)."""
        ...

    async def send_text(self, text: str, *, role: Literal["user", "system_note"] = "user") -> None:
        """Typed shopper text, or a server note to the model (e.g. safety hold, pace change)."""
        ...

    async def send_tool_response(
        self, call_id: str, name: str, response: dict[str, Any], scheduling: Scheduling
    ) -> None: ...

    async def close(self) -> None: ...
