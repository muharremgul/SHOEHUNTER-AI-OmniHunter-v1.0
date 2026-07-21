import json
import os
import re

import httpx

try:
    from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage
except ImportError:
    LlmChat = None
    StreamDone = None
    TextDelta = None
    UserMessage = None


LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")

COACH_SYSTEM = (
    "Sen ShoeHunter AI'nin uzman ayakkabi kocusun. Turkiye pazarindaki kosu, yuruyus, trail ve sneaker "
    "modelleri hakkinda derin bilgin var. Kullanicinin ihtiyacini analiz edip somut model onerileri yaparsin. "
    "Oneriler marka + model adi icermeli. Her oneri icin kisa gerekce ver: yastiklama, kalip genisligi, "
    "dayaniklilik ve zemin uyumu. Fiyat tahminlerinde yaklasik de ve kesin fiyat garantisi verme. "
    "Turkce yanit ver, yanitlari kisa ve madde madde tut. "
    "Somut ayakkabi modeli onerdiysen yanitin en sonuna tam olarak su formatta tek satir ekle: "
    "[MODELLER]: Marka Model 1 | Marka Model 2 | Marka Model 3"
)


def _profile_text(profile):
    if not profile:
        return ""
    parts = []
    mapping = {
        "weight": "Kilo",
        "target_weight": "Hedef kilo",
        "shoe_size": "Ayakkabi numarasi",
        "foot_notes": "Ayak yapisi notlari",
        "usage": "Kullanim amaci",
        "priorities": "Oncelikler",
        "notes": "Ek notlar",
    }
    for key, label in mapping.items():
        if profile.get(key):
            parts.append(f"{label}: {profile[key]}")
    if not parts:
        return ""
    return "\n\nKullanici profili:\n" + "\n".join(parts)


async def _save_messages(db, session_id, user_message, assistant_message, provider=None):
    from services import new_id, now_iso

    await db.ai_messages.insert_one(
        {"id": new_id(), "session_id": session_id, "role": "user", "content": user_message, "provider": provider, "created_at": now_iso()}
    )
    await db.ai_messages.insert_one(
        {
            "id": new_id(),
            "session_id": session_id,
            "role": "assistant",
            "content": assistant_message,
            "provider": provider,
            "created_at": now_iso(),
        }
    )


def _extract_openai_text(data):
    if data.get("output_text"):
        return data["output_text"]

    parts = []
    for item in data.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                parts.append(content["text"])
    return "".join(parts).strip()


def _extract_gemini_text(data):
    if data.get("output_text"):
        return data["output_text"]

    parts = []
    for candidate in data.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if part.get("text"):
                parts.append(part["text"])
    for step in data.get("steps", []):
        for content in step.get("content", []):
            if isinstance(content, dict) and content.get("text"):
                parts.append(content["text"])
    return "".join(parts).strip()


def _extract_groq_text(data):
    choices = data.get("choices") or []
    if choices:
        content = choices[0].get("message", {}).get("content")
        if content:
            return content.strip()
    return ""


async def _gemini_text(system_message, user_message):
    payload = {
        "model": GEMINI_MODEL,
        "system_instruction": system_message,
        "input": user_message,
        "generation_config": {"temperature": 0.7},
    }
    headers = {
        "x-goog-api-key": GEMINI_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers=headers,
            json=payload,
        )
    if response.status_code >= 400:
        detail = response.text[:500]
        raise RuntimeError(f"Gemini istegi basarisiz: HTTP {response.status_code} - {detail}")
    text = _extract_gemini_text(response.json())
    if not text:
        raise RuntimeError("Gemini bos yanit dondu")
    return text


async def _groq_text(system_message, user_message):
    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
        )
    if response.status_code >= 400:
        detail = response.text[:500]
        raise RuntimeError(f"Groq istegi basarisiz: HTTP {response.status_code} - {detail}")
    text = _extract_groq_text(response.json())
    if not text:
        raise RuntimeError("Groq bos yanit dondu")
    return text


async def _openai_text(system_message, user_message):
    payload = {
        "model": OPENAI_MODEL,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_message}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": user_message}],
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post("https://api.openai.com/v1/responses", headers=headers, json=payload)
    if response.status_code >= 400:
        detail = response.text[:500]
        raise RuntimeError(f"OpenAI istegi basarisiz: HTTP {response.status_code} - {detail}")
    text = _extract_openai_text(response.json())
    if not text:
        raise RuntimeError("OpenAI bos yanit dondu")
    return text


async def _ai_text(system_message, user_message):
    providers = [
        ("Gemini", bool(GEMINI_KEY), _gemini_text),
        ("Groq", bool(GROQ_KEY), _groq_text),
        ("OpenAI", bool(OPENAI_KEY), _openai_text),
    ]
    last_error = None
    for name, enabled, fn in providers:
        if not enabled:
            continue
        try:
            return name, await fn(system_message, user_message)
        except Exception as exc:
            last_error = f"{name}: {str(exc)[:220]}"
    if last_error:
        raise RuntimeError(last_error)
    raise RuntimeError("AI anahtari bulunamadi")


def _chunks(text, size=260):
    for start in range(0, len(text), size):
        yield text[start:start + size]


async def coach_stream(db, session_id, message):
    try:
        profile = await db.user_profile.find_one({"id": "main"}, {"_id": 0})
        if profile and not profile.get("share_profile_with_ai", False):
            profile = None
        history = await db.ai_messages.find({"session_id": session_id}, {"_id": 0}).sort("created_at", -1).to_list(8)
        history.reverse()
    except Exception:
        profile = None
        history = []
    context = ""
    if history:
        lines = [f"{'Kullanici' if m['role'] == 'user' else 'Koc'}: {m['content'][:400]}" for m in history]
        context = "\n\nOnceki konusma:\n" + "\n".join(lines)

    system_message = COACH_SYSTEM + _profile_text(profile) + context

    if GEMINI_KEY or GROQ_KEY or OPENAI_KEY:
        full_text = ""
        provider = None
        try:
            provider, full_text = await _ai_text(system_message, message)
            for chunk in _chunks(full_text):
                yield f"data: {json.dumps({'delta': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as exc:
            full_text = f"AI Koc isteginde hata aldi: {str(exc)[:220]}"
            yield f"data: {json.dumps({'delta': full_text})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"
        try:
            await _save_messages(db, session_id, message, full_text, provider=provider)
        except Exception:
            pass
        return

    if not LlmChat or not LLM_KEY:
        fallback = (
            "AI Koc su anda kapali. Backend icin GEMINI_API_KEY, GROQ_API_KEY, OPENAI_API_KEY veya EMERGENT_LLM_KEY ayarlaninca model onerileri aktif olur. "
            "Bu arada AI Arama ekranindan urun adiyla magaza aramasi yapabilirsiniz."
        )
        yield f"data: {json.dumps({'delta': fallback})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
        try:
            await _save_messages(db, session_id, message, fallback)
        except Exception:
            pass
        return

    chat = LlmChat(
        api_key=LLM_KEY,
        session_id=session_id,
        system_message=system_message,
    ).with_model("openai", "gpt-5.4")

    full = []
    async for event in chat.stream_message(UserMessage(text=message)):
        if isinstance(event, TextDelta):
            full.append(event.content)
            yield f"data: {json.dumps({'delta': event.content})}\n\n"
        elif isinstance(event, StreamDone):
            break
    yield f"data: {json.dumps({'done': True})}\n\n"

    try:
        await _save_messages(db, session_id, message, "".join(full))
    except Exception:
        pass


async def analyze_search_query(query):
    system_message = (
        "Sen bir urun adi normalizasyon asistansin. Kullanicinin ayakkabi arama sorgusunu analiz et ve "
        'SADECE su JSON formatinda yanit ver: {"brand": "...", "model": "...", "normalized_query": "..."}. '
        "brand: marka adi, bilinmiyorsa bos string. model: model adi. normalized_query: magaza aramasinda "
        "kullanilacak temiz sorgu, marka + model. Baska hicbir sey yazma."
    )

    if GEMINI_KEY or GROQ_KEY or OPENAI_KEY:
        try:
            _, text = await _ai_text(system_message, query)
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return {
                    "brand": data.get("brand", ""),
                    "model": data.get("model", ""),
                    "normalized_query": data.get("normalized_query") or query,
                }
        except Exception:
            pass
        return {"brand": "", "model": "", "normalized_query": query}

    try:
        chat = LlmChat(
            api_key=LLM_KEY,
            session_id="search-analyze",
            system_message=system_message,
        ).with_model("openai", "gpt-5.4")
        response = await chat.send_message(UserMessage(text=query))
        text = str(response)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {
                "brand": data.get("brand", ""),
                "model": data.get("model", ""),
                "normalized_query": data.get("normalized_query") or query,
            }
    except Exception:
        pass
    return {"brand": "", "model": "", "normalized_query": query}
