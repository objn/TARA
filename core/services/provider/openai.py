from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

from core.configs.settings import ENV, Env

try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_openai import ChatOpenAI
except Exception as e:  # pragma: no cover
    raise ImportError(
        "Missing LangChain OpenAI dependencies. Install: `pip install langchain-openai langchain-core`"
    ) from e


ImageInput = Union[str, Path]  # URL/data-url/path


def _require_env() -> Env:
    if ENV is not None:
        return ENV
    return Env.load()


def _is_probably_url(s: str) -> bool:
    s = s.strip().lower()
    return s.startswith("http://") or s.startswith("https://") or s.startswith("data:")


def _path_to_data_url(path: Path) -> str:
    data = path.read_bytes()
    mime, _ = mimetypes.guess_type(str(path))
    if not mime:
        mime = "application/octet-stream"
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _normalize_images(images: Sequence[ImageInput]) -> List[str]:
    out: List[str] = []
    for img in images:
        if isinstance(img, Path):
            out.append(_path_to_data_url(img))
            continue

        s = str(img).strip()
        if not s:
            continue
        if _is_probably_url(s):
            out.append(s)
            continue

        p = Path(s)
        if p.exists() and p.is_file():
            out.append(_path_to_data_url(p))
            continue

        # Fallback: pass-through (may be a non-existing URL-like string)
        out.append(s)
    return out


@dataclass
class OpenAIProvider:
    """
    LangChain-based OpenAI provider.

    Supports:
    - text chat
    - multimodal (text + images)
    - reasoning models via model selection + `reasoning_effort`
    """

    model_text: Optional[str] = None
    model_vision: Optional[str] = None
    model_reasoning: Optional[str] = None
    temperature: float = 0.0

    def _models(self) -> Env:
        return _require_env()

    def _client(
        self,
        *,
        model: str,
        reasoning_effort: Optional[str] = None,
    ) -> ChatOpenAI:
        cfg = self._models()

        model_kwargs = {}
        if reasoning_effort:
            model_kwargs["reasoning_effort"] = reasoning_effort

        # Some model/SDK combinations may reject unknown kwargs; we retry without them.
        try:
            return ChatOpenAI(
                api_key=cfg.OPENAI_API_KEY,
                model=model,
                temperature=self.temperature,
                model_kwargs=model_kwargs or None,
            )
        except TypeError:
            return ChatOpenAI(
                api_key=cfg.OPENAI_API_KEY,
                model=model,
                temperature=self.temperature,
            )

    def invoke_text(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        reasoning: bool = False,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        cfg = self._models()
        chosen_model = model
        if not chosen_model:
            chosen_model = (self.model_reasoning or cfg.OPENAI_REASONING_MODEL) if reasoning else (
                self.model_text or cfg.OPENAI_MODEL_TEXT
            )

        effort = reasoning_effort or (cfg.OPENAI_REASONING_EFFORT if reasoning else None)
        llm = self._client(model=chosen_model, reasoning_effort=effort)

        msgs = []
        if system:
            msgs.append(SystemMessage(content=system))
        msgs.append(HumanMessage(content=prompt))

        res = llm.invoke(msgs)
        return (res.content or "").strip()

    def stream_text(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        reasoning: bool = False,
        reasoning_effort: Optional[str] = None,
    ) -> Iterable[str]:
        """
        Stream output chunks as plain text deltas.

        This is intended for REST SSE endpoints to forward the deltas.
        """
        cfg = self._models()
        chosen_model = model
        if not chosen_model:
            chosen_model = (self.model_reasoning or cfg.OPENAI_REASONING_MODEL) if reasoning else (
                self.model_text or cfg.OPENAI_MODEL_TEXT
            )

        effort = reasoning_effort or (cfg.OPENAI_REASONING_EFFORT if reasoning else None)
        llm = self._client(model=chosen_model, reasoning_effort=effort)

        msgs = []
        if system:
            msgs.append(SystemMessage(content=system))
        msgs.append(HumanMessage(content=prompt))

        for chunk in llm.stream(msgs):
            # LangChain chunk types vary across versions/models.
            delta = ""
            if hasattr(chunk, "content"):
                delta = chunk.content or ""
            elif hasattr(chunk, "message") and hasattr(chunk.message, "content"):
                delta = chunk.message.content or ""
            if delta:
                yield delta

    def invoke_multimodal(
        self,
        text: str,
        images: Sequence[ImageInput],
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        reasoning: bool = False,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        cfg = self._models()
        chosen_model = model
        if not chosen_model:
            chosen_model = (self.model_reasoning or cfg.OPENAI_REASONING_MODEL) if reasoning else (
                self.model_vision or cfg.OPENAI_MODEL_VISION
            )

        effort = reasoning_effort or (cfg.OPENAI_REASONING_EFFORT if reasoning else None)
        llm = self._client(model=chosen_model, reasoning_effort=effort)

        image_urls = _normalize_images(images)
        content: List[dict] = []
        if text:
            content.append({"type": "text", "text": text})
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})

        msgs = []
        if system:
            msgs.append(SystemMessage(content=system))
        msgs.append(HumanMessage(content=content))

        res = llm.invoke(msgs)
        return (res.content or "").strip()

    def stream_multimodal(
        self,
        text: str,
        images: Sequence[ImageInput],
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        reasoning: bool = False,
        reasoning_effort: Optional[str] = None,
    ) -> Iterable[str]:
        cfg = self._models()
        chosen_model = model
        if not chosen_model:
            chosen_model = (self.model_reasoning or cfg.OPENAI_REASONING_MODEL) if reasoning else (
                self.model_vision or cfg.OPENAI_MODEL_VISION
            )

        effort = reasoning_effort or (cfg.OPENAI_REASONING_EFFORT if reasoning else None)
        llm = self._client(model=chosen_model, reasoning_effort=effort)

        image_urls = _normalize_images(images)
        content: List[dict] = []
        if text:
            content.append({"type": "text", "text": text})
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})

        msgs = []
        if system:
            msgs.append(SystemMessage(content=system))
        msgs.append(HumanMessage(content=content))

        for chunk in llm.stream(msgs):
            delta = ""
            if hasattr(chunk, "content"):
                delta = chunk.content or ""
            elif hasattr(chunk, "message") and hasattr(chunk.message, "content"):
                delta = chunk.message.content or ""
            if delta:
                yield delta


# Default instance (import-friendly)
provider = OpenAIProvider()
