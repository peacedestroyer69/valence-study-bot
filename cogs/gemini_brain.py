# ============================================================
# GEMINI AI BRAIN — YPT Study Bot (v2 — Multi-Key Rotation)
# ============================================================
# Uses up to 4 Gemini API keys in rotation.
# On quota exhaustion (429) or any API error, automatically
# switches to the next key. Falls back to curated static banks
# only if ALL keys fail.
# ============================================================

import os
import json
import logging
import asyncio
import random
import re

try:
    from google import genai
    from google.genai import types
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logging.warning("[GEMINI] google-genai not installed. Run: pip install google-genai")

# ---- Load all keys from env ----
_ALL_KEYS = [
    k for k in [
        os.getenv("GEMINI_API_KEY_1", ""),
        os.getenv("GEMINI_API_KEY_2", ""),
        os.getenv("GEMINI_API_KEY_3", ""),
        os.getenv("GEMINI_API_KEY_4", ""),
        os.getenv("GEMINI_API_KEY_5", ""),
        os.getenv("GEMINI_API_KEY_6", ""),
        os.getenv("GEMINI_API_KEY", ""),   # legacy single-key fallback
    ]
    if k.strip()
]
# Deduplicate while preserving order
seen = set()
_KEYS: list[str] = []
for k in _ALL_KEYS:
    if k not in seen:
        seen.add(k)
        _KEYS.append(k)

_MODEL_PREFERENCE = [
    "gemini-3.6-flash",
    "gemini-3.6-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite"
]

_current_key_idx = 0
_cached_clients: dict[str, object] = {}   # key -> genai.Client instance
_rotation_lock = asyncio.Lock()
_init_lock = asyncio.Lock()  # Serialize client init

# --- GEMINI KEY DETAILED METRICS TRACKER ---
_KEY_STATS: dict[int, dict] = {}

def _init_key_stats():
    """Initializes tracking metrics for all configured Gemini API keys."""
    global _KEY_STATS
    _KEY_STATS = {}
    for idx, k in enumerate(_KEYS):
        key_num = idx + 1
        masked = f"...{k[-4:]}" if len(k) >= 4 else "...????"
        _KEY_STATS[key_num] = {
            "key_idx": key_num,
            "masked_key": masked,
            "total_calls": 0,
            "success_count": 0,
            "error_count": 0,
            "quota_429_count": 0,
            "overload_503_count": 0,
            "timeout_count": 0,
            "not_found_404_count": 0,
            "auth_403_count": 0,
            "other_error_count": 0,
            "last_used_ts": None,
            "last_success_ts": None,
            "last_success_model": None,
            "last_error_ts": None,
            "last_error_msg": None,
            "last_error_model": None,
            "models_used": {},
        }

_init_key_stats()

def _record_key_attempt(key_num: int):
    import datetime
    from utils import IST_TZ
    if key_num in _KEY_STATS:
        _KEY_STATS[key_num]["total_calls"] += 1
        _KEY_STATS[key_num]["last_used_ts"] = datetime.datetime.now(IST_TZ).strftime("%Y-%m-%d %H:%M:%S IST")

def _record_key_success(key_num: int, model_name: str):
    import datetime
    from utils import IST_TZ
    if key_num in _KEY_STATS:
        s = _KEY_STATS[key_num]
        s["success_count"] += 1
        ts_str = datetime.datetime.now(IST_TZ).strftime("%Y-%m-%d %H:%M:%S IST")
        s["last_success_ts"] = ts_str
        s["last_success_model"] = model_name
        s["models_used"][model_name] = s["models_used"].get(model_name, 0) + 1

def _record_key_error(key_num: int, model_name: str, err_type: str, err_msg: str):
    import datetime
    from utils import IST_TZ
    if key_num in _KEY_STATS:
        s = _KEY_STATS[key_num]
        s["error_count"] += 1
        ts_str = datetime.datetime.now(IST_TZ).strftime("%Y-%m-%d %H:%M:%S IST")
        s["last_error_ts"] = ts_str
        s["last_error_msg"] = err_msg[:120]  # truncate long error strings
        s["last_error_model"] = model_name

        if err_type == "429":
            s["quota_429_count"] += 1
        elif err_type == "503":
            s["overload_503_count"] += 1
        elif err_type == "timeout":
            s["timeout_count"] += 1
        elif err_type == "404":
            s["not_found_404_count"] += 1
        elif err_type == "403":
            s["auth_403_count"] += 1
        else:
            s["other_error_count"] += 1

def get_gemini_stats_data() -> dict:
    """Returns detailed statistics about Gemini API key usage and errors."""
    total_calls = sum(s["total_calls"] for s in _KEY_STATS.values())
    total_success = sum(s["success_count"] for s in _KEY_STATS.values())
    total_errors = sum(s["error_count"] for s in _KEY_STATS.values())
    total_429 = sum(s["quota_429_count"] for s in _KEY_STATS.values())
    total_503 = sum(s["overload_503_count"] for s in _KEY_STATS.values())
    
    success_rate = (total_success / total_calls * 100) if total_calls > 0 else 100.0

    return {
        "total_keys": len(_KEYS),
        "current_key_idx": _current_key_idx + 1,
        "total_calls": total_calls,
        "total_success": total_success,
        "total_errors": total_errors,
        "total_429": total_429,
        "total_503": total_503,
        "success_rate": round(success_rate, 1),
        "model_preference": _MODEL_PREFERENCE,
        "key_stats": list(_KEY_STATS.values()),
    }

def reset_gemini_stats_data():
    """Resets all tracked key statistics counters."""
    _init_key_stats()

def _get_client(key: str):
    """Returns the genai.Client for a given API key, creating if needed."""
    if key not in _cached_clients:
        try:
            client = genai.Client(api_key=key)
            _cached_clients[key] = client
            logging.info(f"[GEMINI] Initialized client for key (ends with ...{key[-8:]})")
        except Exception as e:
            logging.error(f"[GEMINI] Failed to init client for key: {e}")
            return None
    return _cached_clients[key]

async def _rotate_key():
    """Rotate to the next available API key."""
    global _current_key_idx
    async with _rotation_lock:
        _current_key_idx = (_current_key_idx + 1) % max(len(_KEYS), 1)
        logging.warning(f"[GEMINI] Rotated to key #{_current_key_idx + 1}")
        await asyncio.sleep(1.5)

async def _call_gemini(prompt: str, fallback: str, timeout: float = 18.0, model_preference: list = None, max_output_tokens: int = 1024) -> str:
    """Calls Gemini API with rotation, fallback, and max output tokens."""
    if not _GENAI_AVAILABLE or not _KEYS:
        return fallback

    pref = model_preference or _MODEL_PREFERENCE

    # Strategy: Try each model across ALL keys before falling back to next model.
    # e.g. gemini-3.6-flash on key1..key6, then gemini-3.5-flash on key1..key6, etc.
    for model_name in pref:
        model_skip = False  # If model doesn't exist or is globally unavailable
        start_idx = _current_key_idx
        for attempt in range(len(_KEYS)):
            if model_skip:
                break
            key_idx = (start_idx + attempt) % len(_KEYS)
            key = _KEYS[key_idx]
            client = _get_client(key)
            if client is None:
                continue

            key_num = key_idx + 1
            _record_key_attempt(key_num)
            try:
                loop = asyncio.get_running_loop()
                config = types.GenerateContentConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=0.7,
                )
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda c=client, m=model_name, p=prompt, cfg=config: c.models.generate_content(
                        model=m,
                        contents=p,
                        config=cfg,
                    )),
                    timeout=timeout + 2.0,
                )
                text = response.text.strip() if response.text else ""
                if text:
                    _record_key_success(key_num, model_name)
                    logging.info(f"[GEMINI] ✅ Success using '{model_name}' on key #{key_num}")
                    return text
            except asyncio.TimeoutError:
                _record_key_error(key_num, model_name, "timeout", "asyncio timeout exceeded")
                logging.warning(f"[GEMINI] Key #{key_num} timed out using '{model_name}' — trying next key")
                continue
            except Exception as e:
                err_str = str(e).lower()
                if "not found" in err_str or "404" in err_str or "not_found" in err_str:
                    _record_key_error(key_num, model_name, "404", str(e))
                    logging.warning(f"[GEMINI] Model '{model_name}' does not exist (404) — skipping to next model")
                    model_skip = True
                    break
                elif "503" in err_str or "unavailable" in err_str or "overloaded" in err_str:
                    _record_key_error(key_num, model_name, "503", str(e))
                    logging.warning(f"[GEMINI] '{model_name}' is overloaded (503) on key #{key_num} — trying next key")
                    continue
                elif "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str or "exhausted" in err_str or "exceeded" in err_str:
                    _record_key_error(key_num, model_name, "429", str(e))
                    logging.warning(f"[GEMINI] Key #{key_num} quota exceeded for '{model_name}' — trying next key")
                    await asyncio.sleep(1.0)
                    continue
                elif "deadline" in err_str or "timeout" in err_str:
                    _record_key_error(key_num, model_name, "timeout", str(e))
                    logging.warning(f"[GEMINI] Key #{key_num} timed out (API) for '{model_name}' — trying next key")
                    continue
                elif "api_key" in err_str or "invalid" in err_str or "403" in err_str or "blocked" in err_str:
                    _record_key_error(key_num, model_name, "403", str(e))
                    logging.error(f"[GEMINI] Key #{key_num} auth error — skipping key. Error: {e}")
                    continue
                else:
                    _record_key_error(key_num, model_name, "other", str(e))
                    logging.warning(f"[GEMINI] Key #{key_num} error with '{model_name}': {e} — trying next key")
                    continue

        if not model_skip:
            logging.warning(f"[GEMINI] All {len(_KEYS)} keys failed for '{model_name}' — falling back to next model")

    logging.warning("[GEMINI] ❌ All models and all keys exhausted — using static fallback")
    return fallback

async def _call_gemini_fast(prompt: str, fallback: str, timeout: float = 7.0, max_output_tokens: int = 512) -> str:
    """Calls Gemini API with fast strategy: 15s overall speed limit, tries all keys, 7s per-model timeout."""
    if not _GENAI_AVAILABLE or not _KEYS:
        return fallback

    import time
    start_time = time.time()
    max_global_seconds = 15.0  # Generous 15s speed limit for motivation DMs

    pref = _MODEL_PREFERENCE

    for attempt in range(len(_KEYS)):
        if time.time() - start_time >= max_global_seconds:
            logging.warning("[GEMINI FAST] ⚡ 15s speed limit reached — using pre-made fallback")
            return fallback

        key_idx = (_current_key_idx + attempt) % len(_KEYS)
        key = _KEYS[key_idx]
        client = _get_client(key)
        if client is None:
            continue
            
        key_num = key_idx + 1
        _record_key_attempt(key_num)
        
        for model_name in pref:
            if time.time() - start_time >= max_global_seconds:
                logging.warning("[GEMINI FAST] ⚡ 15s speed limit reached — using pre-made fallback")
                return fallback

            try:
                loop = asyncio.get_running_loop()
                config = types.GenerateContentConfig(
                    max_output_tokens=max_output_tokens,
                    temperature=0.7,
                )
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda c=client, m=model_name, p=prompt, cfg=config: c.models.generate_content(
                        model=m,
                        contents=p,
                        config=cfg,
                    )),
                    timeout=timeout,
                )
                text = response.text.strip() if response.text else ""
                if text:
                    _record_key_success(key_num, model_name)
                    logging.info(f"[GEMINI FAST] ✅ Success using '{model_name}' on key #{key_num} in {round(time.time() - start_time, 2)}s")
                    return text
            except asyncio.TimeoutError:
                _record_key_error(key_num, model_name, "timeout", "asyncio timeout exceeded")
                continue
            except Exception as e:
                err_str = str(e).lower()
                if "not found" in err_str or "404" in err_str or "not_found" in err_str:
                    _record_key_error(key_num, model_name, "404", str(e))
                    continue
                elif "503" in err_str or "unavailable" in err_str or "overloaded" in err_str:
                    _record_key_error(key_num, model_name, "503", str(e))
                    continue
                elif "429" in err_str or "quota" in err_str or "resource_exhausted" in err_str or "exhausted" in err_str or "exceeded" in err_str:
                    _record_key_error(key_num, model_name, "429", str(e))
                    continue
                elif "deadline" in err_str or "timeout" in err_str:
                    _record_key_error(key_num, model_name, "timeout", str(e))
                    continue
                elif "api_key" in err_str or "invalid" in err_str or "403" in err_str or "blocked" in err_str:
                    _record_key_error(key_num, model_name, "403", str(e))
                    break
                else:
                    _record_key_error(key_num, model_name, "other", str(e))
                    continue

    logging.warning("[GEMINI FAST] ⚡ All attempts completed — using static fallback")
    return fallback

# ============================================================
# FALLBACK BANKS (used only when ALL Gemini keys fail)
# ============================================================

_FALLBACK_PUZZLES = [
    {"question": "A train travels from A to B at 60 km/h and returns at 40 km/h. What is the average speed?",
     "options": {"A": "48 km/h", "B": "50 km/h", "C": "52 km/h", "D": "45 km/h"},
     "answer": "A",
     "explanation": "Average speed = 2*60*40/(60+40) = 48 km/h. Always use harmonic mean for same-distance round trips."},
    {"question": "If you overtake the person in 2nd place in a race, what position are you in?",
     "options": {"A": "1st", "B": "2nd", "C": "3rd", "D": "Cannot determine"},
     "answer": "B",
     "explanation": "You take their position — 2nd. You'd only be 1st if you overtook the 1st-place person."},
    {"question": "What is the next number in: 1, 1, 2, 3, 5, 8, 13, ...?",
     "options": {"A": "18", "B": "20", "C": "21", "D": "24"},
     "answer": "C",
     "explanation": "Fibonacci sequence: each term = sum of previous two. 8+13 = 21."},
    {"question": "In △ABC with angle A = 90°, AB = 3, BC = 5. Find AC.",
     "options": {"A": "2", "B": "3", "C": "4", "D": "√34"},
     "answer": "C",
     "explanation": "Pythagoras: BC² = AB² + AC². 25 = 9 + AC². AC = 4. Classic 3-4-5 triangle."},
    {"question": "What is the oxidation state of Chromium (Cr) in potassium dichromate (K2Cr2O7)?",
     "options": {"A": "+3", "B": "+5", "C": "+6", "D": "+7"},
     "answer": "C",
     "explanation": "In K2Cr2O7: 2(+1) + 2(Cr) + 7(-2) = 0 => 2 + 2(Cr) - 14 = 0 => 2(Cr) = 12 => Cr = +6."},
    {"question": "Evaluate the limit: lim (x -> 0) [sin(x) / x].",
     "options": {"A": "0", "B": "1", "C": "Undefined", "D": "Infinity"},
     "answer": "B",
     "explanation": "This is a fundamental trigonometric limit. Using L'Hopital's rule, diff(sin x)/diff(x) = cos(x)/1. As x->0, cos(0) = 1."},
    {"question": "A block of mass m slides down a frictionless incline plane of angle 30°. What is its acceleration?",
     "options": {"A": "g", "B": "g/2", "C": "g√3/2", "D": "g/4"},
     "answer": "B",
     "explanation": "The component of gravity along the incline is g sin(θ). Since θ = 30° and sin(30°) = 0.5, acceleration = g sin(30°) = g/2."},
    {"question": "A projectile is launched with a velocity of 20 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "20.0 m", "B": "80.0 m", "C": "40.0 m", "D": "60.0 m"},
     "answer": "C",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (20²)/10 = 40.0 m."},
    {"question": "A projectile is launched with a velocity of 22 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "96.8 m", "B": "24.2 m", "C": "48.4 m", "D": "72.6 m"},
     "answer": "C",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (22²)/10 = 48.4 m."},
    {"question": "A projectile is launched with a velocity of 24 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "57.6 m", "B": "28.8 m", "C": "86.4 m", "D": "115.2 m"},
     "answer": "A",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (24²)/10 = 57.6 m."},
    {"question": "A projectile is launched with a velocity of 26 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "101.4 m", "B": "67.6 m", "C": "33.8 m", "D": "135.2 m"},
     "answer": "B",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (26²)/10 = 67.6 m."},
    {"question": "A projectile is launched with a velocity of 28 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "156.8 m", "B": "39.2 m", "C": "117.6 m", "D": "78.4 m"},
     "answer": "D",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (28²)/10 = 78.4 m."},
    {"question": "A projectile is launched with a velocity of 30 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "135.0 m", "B": "45.0 m", "C": "180.0 m", "D": "90.0 m"},
     "answer": "D",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (30²)/10 = 90.0 m."},
    {"question": "A projectile is launched with a velocity of 32 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "204.8 m", "B": "102.4 m", "C": "51.2 m", "D": "153.6 m"},
     "answer": "B",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (32²)/10 = 102.4 m."},
    {"question": "A projectile is launched with a velocity of 34 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "57.8 m", "B": "231.2 m", "C": "173.4 m", "D": "115.6 m"},
     "answer": "D",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (34²)/10 = 115.6 m."},
    {"question": "A projectile is launched with a velocity of 36 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "259.2 m", "B": "194.4 m", "C": "129.6 m", "D": "64.8 m"},
     "answer": "C",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (36²)/10 = 129.6 m."},
    {"question": "A projectile is launched with a velocity of 38 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "288.8 m", "B": "72.2 m", "C": "216.6 m", "D": "144.4 m"},
     "answer": "D",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (38²)/10 = 144.4 m."},
    {"question": "A projectile is launched with a velocity of 40 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "160.0 m", "B": "80.0 m", "C": "240.0 m", "D": "320.0 m"},
     "answer": "A",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (40²)/10 = 160.0 m."},
    {"question": "A projectile is launched with a velocity of 42 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "264.6 m", "B": "88.2 m", "C": "176.4 m", "D": "352.8 m"},
     "answer": "C",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (42²)/10 = 176.4 m."},
    {"question": "A projectile is launched with a velocity of 44 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "193.6 m", "B": "290.4 m", "C": "387.2 m", "D": "96.8 m"},
     "answer": "A",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (44²)/10 = 193.6 m."},
    {"question": "A projectile is launched with a velocity of 46 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "317.4 m", "B": "105.8 m", "C": "211.6 m", "D": "423.2 m"},
     "answer": "C",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (46²)/10 = 211.6 m."},
    {"question": "A projectile is launched with a velocity of 48 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "460.8 m", "B": "115.2 m", "C": "345.6 m", "D": "230.4 m"},
     "answer": "D",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (48²)/10 = 230.4 m."},
    {"question": "A projectile is launched with a velocity of 50 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "125.0 m", "B": "500.0 m", "C": "250.0 m", "D": "375.0 m"},
     "answer": "C",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (50²)/10 = 250.0 m."},
    {"question": "A projectile is launched with a velocity of 52 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "270.4 m", "B": "135.2 m", "C": "540.8 m", "D": "405.6 m"},
     "answer": "A",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (52²)/10 = 270.4 m."},
    {"question": "A projectile is launched with a velocity of 54 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "291.6 m", "B": "583.2 m", "C": "437.4 m", "D": "145.8 m"},
     "answer": "A",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (54²)/10 = 291.6 m."},
    {"question": "A projectile is launched with a velocity of 56 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "156.8 m", "B": "470.4 m", "C": "627.2 m", "D": "313.6 m"},
     "answer": "D",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (56²)/10 = 313.6 m."},
    {"question": "A projectile is launched with a velocity of 58 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "336.4 m", "B": "168.2 m", "C": "504.6 m", "D": "672.8 m"},
     "answer": "A",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (58²)/10 = 336.4 m."},
    {"question": "A projectile is launched with a velocity of 60 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "720.0 m", "B": "360.0 m", "C": "540.0 m", "D": "180.0 m"},
     "answer": "B",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (60²)/10 = 360.0 m."},
    {"question": "A projectile is launched with a velocity of 62 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "192.2 m", "B": "384.4 m", "C": "576.6 m", "D": "768.8 m"},
     "answer": "B",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (62²)/10 = 384.4 m."},
    {"question": "A projectile is launched with a velocity of 64 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "204.8 m", "B": "614.4 m", "C": "819.2 m", "D": "409.6 m"},
     "answer": "D",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (64²)/10 = 409.6 m."},
    {"question": "A projectile is launched with a velocity of 66 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "217.8 m", "B": "435.6 m", "C": "871.2 m", "D": "653.4 m"},
     "answer": "B",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (66²)/10 = 435.6 m."},
    {"question": "A projectile is launched with a velocity of 68 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "462.4 m", "B": "924.8 m", "C": "231.2 m", "D": "693.6 m"},
     "answer": "A",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (68²)/10 = 462.4 m."},
    {"question": "A projectile is launched with a velocity of 70 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "490.0 m", "B": "980.0 m", "C": "735.0 m", "D": "245.0 m"},
     "answer": "A",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (70²)/10 = 490.0 m."},
    {"question": "A projectile is launched with a velocity of 72 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "259.2 m", "B": "777.6 m", "C": "518.4 m", "D": "1036.8 m"},
     "answer": "C",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (72²)/10 = 518.4 m."},
    {"question": "A projectile is launched with a velocity of 74 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "547.6 m", "B": "821.4 m", "C": "1095.2 m", "D": "273.8 m"},
     "answer": "A",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (74²)/10 = 547.6 m."},
    {"question": "A projectile is launched with a velocity of 76 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "866.4 m", "B": "577.6 m", "C": "1155.2 m", "D": "288.8 m"},
     "answer": "B",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (76²)/10 = 577.6 m."},
    {"question": "A projectile is launched with a velocity of 78 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "912.6 m", "B": "1216.8 m", "C": "304.2 m", "D": "608.4 m"},
     "answer": "D",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (78²)/10 = 608.4 m."},
    {"question": "A projectile is launched with a velocity of 80 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "320.0 m", "B": "1280.0 m", "C": "960.0 m", "D": "640.0 m"},
     "answer": "D",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (80²)/10 = 640.0 m."},
    {"question": "A projectile is launched with a velocity of 82 m/s at an angle of 45° to the horizontal. Assuming g = 10 m/s², what is the horizontal range?",
     "options": {"A": "1344.8 m", "B": "672.4 m", "C": "1008.6 m", "D": "336.2 m"},
     "answer": "B",
     "explanation": "Range R = v² sin(2θ)/g. Here, sin(90°) = 1, so R = (82²)/10 = 672.4 m."},
    {"question": "A Carnot engine operates between source temperature 300 K and sink temperature 150 K. What is its efficiency?",
     "options": {"A": "25%", "B": "100%", "C": "60%", "D": "50%"},
     "answer": "D",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 150/300) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 310 K and sink temperature 155 K. What is its efficiency?",
     "options": {"A": "25%", "B": "100%", "C": "60%", "D": "50%"},
     "answer": "D",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 155/310) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 320 K and sink temperature 160 K. What is its efficiency?",
     "options": {"A": "60%", "B": "100%", "C": "50%", "D": "25%"},
     "answer": "C",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 160/320) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 330 K and sink temperature 165 K. What is its efficiency?",
     "options": {"A": "25%", "B": "60%", "C": "100%", "D": "50%"},
     "answer": "D",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 165/330) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 340 K and sink temperature 170 K. What is its efficiency?",
     "options": {"A": "25%", "B": "100%", "C": "50%", "D": "60%"},
     "answer": "C",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 170/340) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 350 K and sink temperature 175 K. What is its efficiency?",
     "options": {"A": "50%", "B": "60%", "C": "100%", "D": "25%"},
     "answer": "A",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 175/350) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 360 K and sink temperature 180 K. What is its efficiency?",
     "options": {"A": "50%", "B": "100%", "C": "60%", "D": "25%"},
     "answer": "A",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 180/360) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 370 K and sink temperature 185 K. What is its efficiency?",
     "options": {"A": "100%", "B": "25%", "C": "50%", "D": "60%"},
     "answer": "C",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 185/370) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 380 K and sink temperature 190 K. What is its efficiency?",
     "options": {"A": "25%", "B": "100%", "C": "60%", "D": "50%"},
     "answer": "D",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 190/380) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 390 K and sink temperature 195 K. What is its efficiency?",
     "options": {"A": "25%", "B": "50%", "C": "100%", "D": "60%"},
     "answer": "B",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 195/390) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 400 K and sink temperature 200 K. What is its efficiency?",
     "options": {"A": "25%", "B": "50%", "C": "100%", "D": "60%"},
     "answer": "B",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 200/400) = 0.50, which is 50%."},
    {"question": "A Carnot engine operates between source temperature 410 K and sink temperature 205 K. What is its efficiency?",
     "options": {"A": "25%", "B": "60%", "C": "100%", "D": "50%"},
     "answer": "D",
     "explanation": "Efficiency = (1 - T_sink/T_source) × 100%. Here, (1 - 205/410) = 0.50, which is 50%."},
    {"question": "Two point charges 5 μC and 10 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "0.450 N", "B": "0.225 N", "C": "0.056 N", "D": "0.112 N"},
     "answer": "D",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(5×10^-6)(10×10^-6)/2² = 0.112 N."},
    {"question": "Two point charges 6 μC and 12 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "0.081 N", "B": "0.162 N", "C": "0.324 N", "D": "0.648 N"},
     "answer": "B",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(6×10^-6)(12×10^-6)/2² = 0.162 N."},
    {"question": "Two point charges 7 μC and 14 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "0.882 N", "B": "0.110 N", "C": "0.441 N", "D": "0.221 N"},
     "answer": "D",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(7×10^-6)(14×10^-6)/2² = 0.221 N."},
    {"question": "Two point charges 8 μC and 16 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "0.288 N", "B": "0.144 N", "C": "0.576 N", "D": "1.152 N"},
     "answer": "A",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(8×10^-6)(16×10^-6)/2² = 0.288 N."},
    {"question": "Two point charges 9 μC and 18 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "0.729 N", "B": "0.182 N", "C": "1.458 N", "D": "0.364 N"},
     "answer": "D",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(9×10^-6)(18×10^-6)/2² = 0.364 N."},
    {"question": "Two point charges 10 μC and 20 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "0.900 N", "B": "0.450 N", "C": "1.800 N", "D": "0.225 N"},
     "answer": "B",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(10×10^-6)(20×10^-6)/2² = 0.450 N."},
    {"question": "Two point charges 11 μC and 22 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "2.178 N", "B": "0.544 N", "C": "1.089 N", "D": "0.272 N"},
     "answer": "B",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(11×10^-6)(22×10^-6)/2² = 0.544 N."},
    {"question": "Two point charges 12 μC and 24 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "0.324 N", "B": "1.296 N", "C": "0.648 N", "D": "2.592 N"},
     "answer": "C",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(12×10^-6)(24×10^-6)/2² = 0.648 N."},
    {"question": "Two point charges 13 μC and 26 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "0.760 N", "B": "0.380 N", "C": "3.042 N", "D": "1.521 N"},
     "answer": "A",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(13×10^-6)(26×10^-6)/2² = 0.760 N."},
    {"question": "Two point charges 14 μC and 28 μC are separated by a distance of 2 m in a vacuum. What is the magnitude of the electrostatic force between them? (k = 9×10^9 N·m²/C²)",
     "options": {"A": "0.441 N", "B": "3.528 N", "C": "1.764 N", "D": "0.882 N"},
     "answer": "D",
     "explanation": "F = k|q1 q2|/r². F = (9×10^9)(14×10^-6)(28×10^-6)/2² = 0.882 N."},
    {"question": "How many moles of water (H2O) are present in 36 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "1.0 moles", "B": "20.0 moles", "C": "2.0 moles", "D": "4.0 moles"},
     "answer": "C",
     "explanation": "Moles = Mass / Molar mass. 36 g / 18 g/mol = 2.0 moles."},
    {"question": "How many moles of water (H2O) are present in 54 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "1.5 moles", "B": "6.0 moles", "C": "30.0 moles", "D": "3.0 moles"},
     "answer": "D",
     "explanation": "Moles = Mass / Molar mass. 54 g / 18 g/mol = 3.0 moles."},
    {"question": "How many moles of water (H2O) are present in 72 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "2.0 moles", "B": "8.0 moles", "C": "40.0 moles", "D": "4.0 moles"},
     "answer": "D",
     "explanation": "Moles = Mass / Molar mass. 72 g / 18 g/mol = 4.0 moles."},
    {"question": "How many moles of water (H2O) are present in 90 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "2.5 moles", "B": "10.0 moles", "C": "5.0 moles", "D": "50.0 moles"},
     "answer": "C",
     "explanation": "Moles = Mass / Molar mass. 90 g / 18 g/mol = 5.0 moles."},
    {"question": "How many moles of water (H2O) are present in 108 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "3.0 moles", "B": "6.0 moles", "C": "60.0 moles", "D": "12.0 moles"},
     "answer": "B",
     "explanation": "Moles = Mass / Molar mass. 108 g / 18 g/mol = 6.0 moles."},
    {"question": "How many moles of water (H2O) are present in 126 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "3.5 moles", "B": "70.0 moles", "C": "7.0 moles", "D": "14.0 moles"},
     "answer": "C",
     "explanation": "Moles = Mass / Molar mass. 126 g / 18 g/mol = 7.0 moles."},
    {"question": "How many moles of water (H2O) are present in 144 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "4.0 moles", "B": "16.0 moles", "C": "8.0 moles", "D": "80.0 moles"},
     "answer": "C",
     "explanation": "Moles = Mass / Molar mass. 144 g / 18 g/mol = 8.0 moles."},
    {"question": "How many moles of water (H2O) are present in 162 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "9.0 moles", "B": "90.0 moles", "C": "18.0 moles", "D": "4.5 moles"},
     "answer": "A",
     "explanation": "Moles = Mass / Molar mass. 162 g / 18 g/mol = 9.0 moles."},
    {"question": "How many moles of water (H2O) are present in 180 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "20.0 moles", "B": "10.0 moles", "C": "5.0 moles", "D": "100.0 moles"},
     "answer": "B",
     "explanation": "Moles = Mass / Molar mass. 180 g / 18 g/mol = 10.0 moles."},
    {"question": "How many moles of water (H2O) are present in 198 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "22.0 moles", "B": "11.0 moles", "C": "5.5 moles", "D": "110.0 moles"},
     "answer": "B",
     "explanation": "Moles = Mass / Molar mass. 198 g / 18 g/mol = 11.0 moles."},
    {"question": "How many moles of water (H2O) are present in 216 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "120.0 moles", "B": "12.0 moles", "C": "24.0 moles", "D": "6.0 moles"},
     "answer": "B",
     "explanation": "Moles = Mass / Molar mass. 216 g / 18 g/mol = 12.0 moles."},
    {"question": "How many moles of water (H2O) are present in 234 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "130.0 moles", "B": "26.0 moles", "C": "6.5 moles", "D": "13.0 moles"},
     "answer": "D",
     "explanation": "Moles = Mass / Molar mass. 234 g / 18 g/mol = 13.0 moles."},
    {"question": "How many moles of water (H2O) are present in 252 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "28.0 moles", "B": "7.0 moles", "C": "14.0 moles", "D": "140.0 moles"},
     "answer": "C",
     "explanation": "Moles = Mass / Molar mass. 252 g / 18 g/mol = 14.0 moles."},
    {"question": "How many moles of water (H2O) are present in 270 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "7.5 moles", "B": "15.0 moles", "C": "150.0 moles", "D": "30.0 moles"},
     "answer": "B",
     "explanation": "Moles = Mass / Molar mass. 270 g / 18 g/mol = 15.0 moles."},
    {"question": "How many moles of water (H2O) are present in 288 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "32.0 moles", "B": "160.0 moles", "C": "8.0 moles", "D": "16.0 moles"},
     "answer": "D",
     "explanation": "Moles = Mass / Molar mass. 288 g / 18 g/mol = 16.0 moles."},
    {"question": "How many moles of water (H2O) are present in 306 grams of water? (Molar mass of H2O = 18 g/mol)",
     "options": {"A": "34.0 moles", "B": "170.0 moles", "C": "8.5 moles", "D": "17.0 moles"},
     "answer": "D",
     "explanation": "Moles = Mass / Molar mass. 306 g / 18 g/mol = 17.0 moles."},
    {"question": "What is the chemical formula of an acyclic alkane with 2 carbon atoms?",
     "options": {"A": "C2H4", "B": "C2H8", "C": "C2H2", "D": "C2H6"},
     "answer": "D",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=2, it is C2H6."},
    {"question": "What is the chemical formula of an acyclic alkane with 3 carbon atoms?",
     "options": {"A": "C3H10", "B": "C3H3", "C": "C3H6", "D": "C3H8"},
     "answer": "D",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=3, it is C3H8."},
    {"question": "What is the chemical formula of an acyclic alkane with 4 carbon atoms?",
     "options": {"A": "C4H12", "B": "C4H8", "C": "C4H4", "D": "C4H10"},
     "answer": "D",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=4, it is C4H10."},
    {"question": "What is the chemical formula of an acyclic alkane with 5 carbon atoms?",
     "options": {"A": "C5H14", "B": "C5H10", "C": "C5H5", "D": "C5H12"},
     "answer": "D",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=5, it is C5H12."},
    {"question": "What is the chemical formula of an acyclic alkane with 6 carbon atoms?",
     "options": {"A": "C6H14", "B": "C6H12", "C": "C6H6", "D": "C6H16"},
     "answer": "A",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=6, it is C6H14."},
    {"question": "What is the chemical formula of an acyclic alkane with 7 carbon atoms?",
     "options": {"A": "C7H7", "B": "C7H16", "C": "C7H14", "D": "C7H18"},
     "answer": "B",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=7, it is C7H16."},
    {"question": "What is the chemical formula of an acyclic alkane with 8 carbon atoms?",
     "options": {"A": "C8H20", "B": "C8H16", "C": "C8H8", "D": "C8H18"},
     "answer": "D",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=8, it is C8H18."},
    {"question": "What is the chemical formula of an acyclic alkane with 9 carbon atoms?",
     "options": {"A": "C9H9", "B": "C9H22", "C": "C9H18", "D": "C9H20"},
     "answer": "D",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=9, it is C9H20."},
    {"question": "What is the chemical formula of an acyclic alkane with 10 carbon atoms?",
     "options": {"A": "C10H10", "B": "C10H24", "C": "C10H20", "D": "C10H22"},
     "answer": "D",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=10, it is C10H22."},
    {"question": "What is the chemical formula of an acyclic alkane with 11 carbon atoms?",
     "options": {"A": "C11H11", "B": "C11H24", "C": "C11H26", "D": "C11H22"},
     "answer": "B",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=11, it is C11H24."},
    {"question": "What is the chemical formula of an acyclic alkane with 12 carbon atoms?",
     "options": {"A": "C12H12", "B": "C12H28", "C": "C12H24", "D": "C12H26"},
     "answer": "D",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=12, it is C12H26."},
    {"question": "What is the chemical formula of an acyclic alkane with 13 carbon atoms?",
     "options": {"A": "C13H26", "B": "C13H28", "C": "C13H13", "D": "C13H30"},
     "answer": "B",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=13, it is C13H28."},
    {"question": "What is the chemical formula of an acyclic alkane with 14 carbon atoms?",
     "options": {"A": "C14H14", "B": "C14H30", "C": "C14H28", "D": "C14H32"},
     "answer": "B",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=14, it is C14H30."},
    {"question": "What is the chemical formula of an acyclic alkane with 15 carbon atoms?",
     "options": {"A": "C15H32", "B": "C15H15", "C": "C15H30", "D": "C15H34"},
     "answer": "A",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=15, it is C15H32."},
    {"question": "What is the chemical formula of an acyclic alkane with 16 carbon atoms?",
     "options": {"A": "C16H32", "B": "C16H36", "C": "C16H16", "D": "C16H34"},
     "answer": "D",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=16, it is C16H34."},
    {"question": "What is the chemical formula of an acyclic alkane with 17 carbon atoms?",
     "options": {"A": "C17H36", "B": "C17H34", "C": "C17H17", "D": "C17H38"},
     "answer": "A",
     "explanation": "The general formula for an acyclic alkane is C_n H_2n+2. For n=17, it is C17H36."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 1.",
     "options": {"A": "0.67", "B": "0.11", "C": "0.33", "D": "1.00"},
     "answer": "C",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 1 gives (1³)/3 = 0.33."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 2.",
     "options": {"A": "5.33", "B": "0.89", "C": "2.67", "D": "8.00"},
     "answer": "C",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 2 gives (2³)/3 = 2.67."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 3.",
     "options": {"A": "18.00", "B": "3.00", "C": "27.00", "D": "9.00"},
     "answer": "D",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 3 gives (3³)/3 = 9.00."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 4.",
     "options": {"A": "42.67", "B": "7.11", "C": "21.33", "D": "64.00"},
     "answer": "C",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 4 gives (4³)/3 = 21.33."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 5.",
     "options": {"A": "125.00", "B": "41.67", "C": "83.33", "D": "13.89"},
     "answer": "B",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 5 gives (5³)/3 = 41.67."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 6.",
     "options": {"A": "24.00", "B": "216.00", "C": "72.00", "D": "144.00"},
     "answer": "C",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 6 gives (6³)/3 = 72.00."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 7.",
     "options": {"A": "114.33", "B": "343.00", "C": "228.67", "D": "38.11"},
     "answer": "A",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 7 gives (7³)/3 = 114.33."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 8.",
     "options": {"A": "341.33", "B": "170.67", "C": "512.00", "D": "56.89"},
     "answer": "B",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 8 gives (8³)/3 = 170.67."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 9.",
     "options": {"A": "729.00", "B": "486.00", "C": "81.00", "D": "243.00"},
     "answer": "D",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 9 gives (9³)/3 = 243.00."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 10.",
     "options": {"A": "1000.00", "B": "333.33", "C": "666.67", "D": "111.11"},
     "answer": "B",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 10 gives (10³)/3 = 333.33."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 11.",
     "options": {"A": "887.33", "B": "1331.00", "C": "147.89", "D": "443.67"},
     "answer": "D",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 11 gives (11³)/3 = 443.67."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 12.",
     "options": {"A": "192.00", "B": "576.00", "C": "1728.00", "D": "1152.00"},
     "answer": "B",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 12 gives (12³)/3 = 576.00."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 13.",
     "options": {"A": "2197.00", "B": "244.11", "C": "732.33", "D": "1464.67"},
     "answer": "C",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 13 gives (13³)/3 = 732.33."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 14.",
     "options": {"A": "1829.33", "B": "914.67", "C": "2744.00", "D": "304.89"},
     "answer": "B",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 14 gives (14³)/3 = 914.67."},
    {"question": "Evaluate the definite integral of x² dx from x = 0 to x = 15.",
     "options": {"A": "3375.00", "B": "375.00", "C": "2250.00", "D": "1125.00"},
     "answer": "D",
     "explanation": "The antiderivative of x² is x³/3. Evaluating from 0 to 15 gives (15³)/3 = 1125.00."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 3x + 2 = 0?",
     "options": {"A": "3", "B": "-2", "C": "-3", "D": "2"},
     "answer": "A",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-3)/1 = 3."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 6x + 4 = 0?",
     "options": {"A": "-6", "B": "4", "C": "-4", "D": "6"},
     "answer": "D",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-6)/1 = 6."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 9x + 6 = 0?",
     "options": {"A": "6", "B": "-9", "C": "-6", "D": "9"},
     "answer": "D",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-9)/1 = 9."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 12x + 8 = 0?",
     "options": {"A": "-12", "B": "12", "C": "8", "D": "-8"},
     "answer": "B",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-12)/1 = 12."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 15x + 10 = 0?",
     "options": {"A": "-15", "B": "10", "C": "15", "D": "-10"},
     "answer": "C",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-15)/1 = 15."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 18x + 12 = 0?",
     "options": {"A": "-12", "B": "-18", "C": "18", "D": "12"},
     "answer": "C",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-18)/1 = 18."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 21x + 14 = 0?",
     "options": {"A": "-14", "B": "14", "C": "21", "D": "-21"},
     "answer": "C",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-21)/1 = 21."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 24x + 16 = 0?",
     "options": {"A": "-24", "B": "-16", "C": "24", "D": "16"},
     "answer": "C",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-24)/1 = 24."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 27x + 18 = 0?",
     "options": {"A": "27", "B": "18", "C": "-27", "D": "-18"},
     "answer": "A",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-27)/1 = 27."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 30x + 20 = 0?",
     "options": {"A": "-30", "B": "-20", "C": "30", "D": "20"},
     "answer": "C",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-30)/1 = 30."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 33x + 22 = 0?",
     "options": {"A": "-33", "B": "33", "C": "22", "D": "-22"},
     "answer": "B",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-33)/1 = 33."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 36x + 24 = 0?",
     "options": {"A": "-36", "B": "-24", "C": "36", "D": "24"},
     "answer": "C",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-36)/1 = 36."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 39x + 26 = 0?",
     "options": {"A": "-26", "B": "-39", "C": "26", "D": "39"},
     "answer": "D",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-39)/1 = 39."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 42x + 28 = 0?",
     "options": {"A": "28", "B": "-42", "C": "42", "D": "-28"},
     "answer": "C",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-42)/1 = 42."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 45x + 30 = 0?",
     "options": {"A": "30", "B": "-30", "C": "-45", "D": "45"},
     "answer": "D",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-45)/1 = 45."},
    {"question": "What is the sum of the roots of the quadratic equation x² - 48x + 32 = 0?",
     "options": {"A": "-32", "B": "-48", "C": "32", "D": "48"},
     "answer": "D",
     "explanation": "For ax² + bx + c = 0, the sum of roots is -b/a. Here, -(-48)/1 = 48."}
]

_FALLBACK_WEEKLY_PUZZLES = [
    {
        "question": "An infinite grid of 1-ohm resistors is connected. What is the equivalent resistance between two adjacent nodes?",
        "options": {
            "A": "0.5 ohms",
            "B": "1.0 ohms",
            "C": "2.0 ohms",
            "D": "0.25 ohms"
        },
        "answer": "A",
        "explanation": "Using superposition: if we inject 1A of current at node A and extract it at infinity, 1/4 A flows through each of the 4 adjacent resistors. If we extract 1A from node B and inject it at infinity, 1/4 A flows into B from each adjacent resistor. Superimposing both, a current of 1/4 + 1/4 = 1/2 A flows directly from A to B. Since the total current injected is 1A, by Ohm's law, R_eff = V/I = (1/2 A * 1 ohm) / 1A = 0.5 ohms."
    },
    {
        "question": "A solid cylinder of mass M and radius R rolls without slipping down an inclined plane of angle theta. What is the minimum coefficient of static friction required to prevent slipping?",
        "options": {
            "A": "(1/3) * tan(theta)",
            "B": "(2/3) * tan(theta)",
            "C": "(1/2) * tan(theta)",
            "D": "(3/5) * tan(theta)"
        },
        "answer": "A",
        "explanation": "For a solid cylinder, the moment of inertia I = 0.5*M*R^2. The acceleration along the incline is a = g * sin(theta) / (1 + I/(M*R^2)) = (2/3) * g * sin(theta). The force of friction is f = I * alpha / R = I * a / R^2 = 0.5 * M * a = (1/3) * M * g * sin(theta). The normal force is N = M * g * cos(theta). To prevent slipping, f <= mu * N => (1/3) * M * g * sin(theta) <= mu * M * g * cos(theta) => mu >= (1/3) * tan(theta)."
    }
]

def _clean_json_response(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    
    raw = raw.strip()

    first_brace = raw.find("{")
    first_bracket = raw.find("[")
    
    start_idx = -1
    if first_brace != -1 and first_bracket != -1:
        start_idx = min(first_brace, first_bracket)
    elif first_brace != -1:
        start_idx = first_brace
    elif first_bracket != -1:
        start_idx = first_bracket
        
    last_brace = raw.rfind("}")
    last_bracket = raw.rfind("]")
    
    end_idx = -1
    if last_brace != -1 and last_bracket != -1:
        end_idx = max(last_brace, last_bracket)
    elif last_brace != -1:
        end_idx = last_brace
    elif last_bracket != -1:
        end_idx = last_bracket
        
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        return raw[start_idx:end_idx + 1].strip()
        
    return raw.strip()

def safe_load_json(raw: str) -> dict:
    cleaned = _clean_json_response(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        import re
        cleaned_no_trailing = re.sub(r',(?=\s*?[}\]])', '', cleaned)
        try:
            return json.loads(cleaned_no_trailing)
        except json.JSONDecodeError:
            return {}

def clean_message_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    text = text.replace("**", "").replace("*", "").replace("__", "").replace("_", "").replace("`", "")
    text = "\n".join(line.strip() for line in text.split("\n") if line.strip())
    if len(text) > 1800:
        text = text[:1797] + "..."
    return text.strip()


def strip_latex(text: str) -> str:
    """Convert LaTeX math notation to readable plain text / Unicode for Discord.
    Discord cannot render LaTeX, so we convert common patterns to readable equivalents."""
    if not text:
        return text
    # Fast path: no LaTeX detected (no $, no backslash commands, no math delimiters)
    if '$' not in text and '\\' not in text and '\\[' not in text:
        return text

    # Greek letters -> Unicode
    _GREEK = {
        r'\alpha': 'α', r'\beta': 'β', r'\gamma': 'γ', r'\delta': 'δ',
        r'\epsilon': 'ε', r'\zeta': 'ζ', r'\eta': 'η', r'\theta': 'θ',
        r'\iota': 'ι', r'\kappa': 'κ', r'\lambda': 'λ', r'\mu': 'μ',
        r'\nu': 'ν', r'\xi': 'ξ', r'\pi': 'π', r'\rho': 'ρ',
        r'\sigma': 'σ', r'\tau': 'τ', r'\upsilon': 'υ', r'\phi': 'φ',
        r'\chi': 'χ', r'\psi': 'ψ', r'\omega': 'ω',
        r'\Alpha': 'Α', r'\Beta': 'Β', r'\Gamma': 'Γ', r'\Delta': 'Δ',
        r'\Epsilon': 'Ε', r'\Zeta': 'Ζ', r'\Eta': 'Η', r'\Theta': 'Θ',
        r'\Lambda': 'Λ', r'\Xi': 'Ξ', r'\Pi': 'Π', r'\Sigma': 'Σ',
        r'\Phi': 'Φ', r'\Psi': 'Ψ', r'\Omega': 'Ω',
        r'\infty': '∞', r'\pm': '±', r'\mp': '∓', r'\times': '×',
        r'\div': '÷', r'\cdot': '·', r'\leq': '≤', r'\geq': '≥',
        r'\neq': '≠', r'\approx': '≈', r'\equiv': '≡', r'\propto': '∝',
        r'\partial': '∂', r'\nabla': '∇', r'\sum': 'Σ', r'\prod': 'Π',
        r'\int': '∫', r'\sqrt': '√', r'\leftarrow': '←', r'\rightarrow': '→',
        r'\Leftarrow': '⇐', r'\Rightarrow': '⇒', r'\leftrightarrow': '↔',
        r'\in': '∈', r'\notin': '∉', r'\subset': '⊂', r'\supset': '⊃',
        r'\cup': '∪', r'\cap': '∩', r'\forall': '∀', r'\exists': '∃',
        r'\angle': '∠', r'\degree': '°', r'\circ': '°',
        r'\dagger': '†', r'\ddagger': '‡',
        r'\hbar': 'ℏ', r'\ell': 'ℓ',
    }

    # Superscript digits
    _SUPER = str.maketrans('0123456789+-=()ni', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ')
    # Subscript digits
    _SUB = str.maketrans('0123456789+-=()aeiou', '₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎ₐₑᵢₒᵤ')

    # Replace Greek and math symbols
    for latex_cmd, unicode_char in _GREEK.items():
        text = text.replace(latex_cmd, unicode_char)

    # \frac{a}{b} -> (a)/(b)
    text = re.sub(r'\\frac\{([^}]*)\}\{([^}]*)\}', r'(\1)/(\2)', text)

    # \sqrt{x} -> √(x)
    text = re.sub(r'\\sqrt\{([^}]*)\}', r'√(\1)', text)

    # \tilde{x} -> x̃
    text = re.sub(r'\\tilde\{([^}]*)\}', r'\1̃', text)
    # \hat{x} -> x̂
    text = re.sub(r'\\hat\{([^}]*)\}', r'\1̂', text)
    # \bar{x} -> x̄
    text = re.sub(r'\\bar\{([^}]*)\}', r'\1̄', text)
    # \vec{x} -> x⃗
    text = re.sub(r'\\vec\{([^}]*)\}', r'\1⃗', text)

    # \mathbb{R} -> ℝ, \mathbb{Z} -> ℤ, etc.
    _MATHBB = {'R': 'ℝ', 'Z': 'ℤ', 'N': 'ℕ', 'Q': 'ℚ', 'C': 'ℂ'}
    def _replace_mathbb(m):
        return _MATHBB.get(m.group(1), m.group(1))
    text = re.sub(r'\\mathbb\{([A-Z])\}', _replace_mathbb, text)

    # ^{...} -> superscript  (simple cases)
    def _superscript(m):
        return m.group(1).translate(_SUPER)
    text = re.sub(r'\^\{([^}]*)\}', _superscript, text)
    # ^x for single char
    text = re.sub(r'\^([0-9n])', lambda m: m.group(1).translate(_SUPER), text)

    # _{...} -> subscript
    def _subscript(m):
        return m.group(1).translate(_SUB)
    text = re.sub(r'_\{([^}]*)\}', _subscript, text)
    # _x for single char
    text = re.sub(r'_([0-9])', lambda m: m.group(1).translate(_SUB), text)

    # \text{...} -> just the text
    text = re.sub(r'\\text\{([^}]*)\}', r'\1', text)
    # \mathrm{...} -> just the text
    text = re.sub(r'\\mathrm\{([^}]*)\}', r'\1', text)
    # \mathbf{...} -> bold markers
    text = re.sub(r'\\mathbf\{([^}]*)\}', r'**\1**', text)

    # \left( \right) -> ( )
    text = re.sub(r'\\left([(\[|])', r'\1', text)
    text = re.sub(r'\\right([)\]|])', r'\1', text)
    text = text.replace(r'\left\{', '{').replace(r'\right\}', '}')

    # \sim -> ~
    text = text.replace(r'\sim', '~')
    # \quad, \qquad -> space
    text = text.replace(r'\qquad', '  ').replace(r'\quad', ' ')
    # \, \; \: \! -> thin spaces or nothing
    text = re.sub(r'\\[,;:!]', ' ', text)

    # --- LaTeX environments (\begin{...} / \end{...}) ---
    text = re.sub(r'\\begin\{[^}]*\}', '', text)
    text = re.sub(r'\\end\{[^}]*\}', '', text)

    # --- \boxed{...} -> [...] ---
    text = re.sub(r'\\boxed\{([^}]*)\}', r'[\1]', text)

    # --- \overline{...} -> x̅ ---
    text = re.sub(r'\\overline\{([^}]*)\}', r'\1̅', text)

    # --- \underline{...} -> keep text ---
    text = re.sub(r'\\underline\{([^}]*)\}', r'\1', text)

    # --- \displaystyle, \textstyle, \limits -> nothing ---
    text = re.sub(r'\\(?:display|text)style\b', '', text)
    text = text.replace(r'\limits', '')

    # --- Trig / math function commands -> plain text ---
    _MATH_FUNCS = [
        'log', 'ln', 'sin', 'cos', 'tan', 'sec', 'csc', 'cot',
        'arcsin', 'arccos', 'arctan', 'sinh', 'cosh', 'tanh',
        'lim', 'max', 'min', 'sup', 'inf', 'det', 'exp', 'gcd',
    ]
    for func in _MATH_FUNCS:
        text = text.replace(f'\\{func}', func)

    # --- \binom{n}{k} -> C(n,k) ---
    text = re.sub(r'\\binom\{([^}]*)\}\{([^}]*)\}', r'C(\1,\2)', text)

    # --- \choose -> C notation (legacy LaTeX) ---
    text = re.sub(r'\{([^}]*)\s*\\choose\s*([^}]*)\}', r'C(\1,\2)', text)

    # Strip display math delimiters: \[...\] and \(...\)
    text = text.replace(r'\[', '').replace(r'\]', '')
    text = text.replace(r'\(', '').replace(r'\)', '')

    # Strip dollar sign delimiters: $$...$$ and $...$
    text = re.sub(r'\$\$(.+?)\$\$', r'\1', text, flags=re.DOTALL)
    text = re.sub(r'\$(.+?)\$', r'\1', text)

    # Clean remaining backslash commands we missed (e.g. \psi_n)
    text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)

    # Clean up stray curly braces
    text = text.replace('{', '').replace('}', '')

    # Clean up multiple spaces
    text = re.sub(r'  +', ' ', text)

    return text.strip()


# ============================================================
# 1. GENERATE PUZZLE WITH REFINEMENT & DOUBLE SOLVER
# ============================================================

async def generate_puzzle(topic: str = "mixed", is_weekly: bool = False) -> dict:
    """
    Generates a daily or weekly puzzle using an iterative refinement pipeline
    (3 rounds of Brainstormer and Refiner feedback) and double-solver logic verification.
    """
    if is_weekly:
        challenge_desc = "an extremely difficult, deep conceptual weekly mega puzzle (covering mathematics, advanced science, logic, or programming). It must require multi-step logical deduction or deep conceptual understanding, and have no time limit to solve. It should be challenging even for very smart students. You have no token limit. Explain the problem, choices, and solution in extreme depth with full mathematical/logical rigor."
        pref = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]
        tokens = 8192
        timeout_val = 120.0
    elif topic == "logic":
        challenge_desc = "a tricky logic puzzle or lateral thinking brain teaser — no equations needed. Keep the question, options, and explanation extremely brief and concise (under 80 words total). Do not write long introductions. Save tokens."
        pref = ["gemini-3.6-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
        tokens = 512
        timeout_val = 20.0
    else:
        topic_map = {
            "jee":   "a JEE-level Physics, Chemistry, or Mathematics MCQ (not trivial — something that requires actual thinking)",
            "mixed": "either a JEE-level MCQ or a logic puzzle — whichever would make the more interesting challenge today",
        }
        topic_desc = topic_map.get(topic, topic_map["mixed"])
        challenge_desc = f"{topic_desc} suitable for Indian JEE aspirants (age 16-18), solvable in under 2 minutes. Keep the explanation reasonable and precise."
        pref = ["gemini-3.6-flash", "gemini-3.6-flash-lite", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        tokens = 2048
        timeout_val = 45.0

    for attempt in range(3):
        logging.info(f"[PUZZLE PIPELINE] Starting attempt {attempt + 1}/3... Weekly={is_weekly}")

        # Stage 1: Initial Draft
        draft_prompt = f"""You are the Brainstormer. Generate a draft of {challenge_desc}.
It must have 4 options (A, B, C, D) and only one correct option.
Output the puzzle draft including the question, the options, the correct answer, and your initial explanation.

LATEX & MATH MANDATE: You MUST use standard LaTeX math notation ($...$, \\frac{{a}}{{b}}, \\sqrt{{x}}, \\alpha, \\theta, \\int, \\sum, x^2, \\lim, etc.) for ALL mathematical expressions, formulas, physics equations, and answer options! Our bot automatically renders all LaTeX formulas into crisp, high-res dark-mode images for Discord. ALWAYS write proper LaTeX ($...$) for any mathematical content.

CHEMISTRY NOTATION MANDATE: For Chemistry puzzles, you MUST use proper chemistry notation:
- Use IUPAC nomenclature (e.g., 2-methylpropan-1-ol, ethanoic acid, benzene-1,4-diol)
- Write structural formulas clearly (CH₃COOH, C₂H₅OH, C₆H₅NH₂)
- Use proper reaction arrows: → for forward, ⇌ for equilibrium
- Denote functional groups explicitly: —OH (hydroxyl), —COOH (carboxyl), —NH₂ (amine), —CHO (aldehyde), C=O (carbonyl)
- Name reagents/catalysts above reaction arrows
- Our bot renders molecule names (benzene, ethanol, glucose, etc.) and chemical reactions as structural diagrams automatically."""
        draft = await _call_gemini(draft_prompt, fallback="", timeout=timeout_val, model_preference=pref, max_output_tokens=tokens)
        if not draft:
            logging.warning("[PUZZLE PIPELINE] Failed to get draft.")
            continue

        # Cycle 1: Critique & Refine
        critique_prompt_1 = f"""You are the Refiner. Critique the following puzzle draft for clarity, ambiguity, difficulty, and accuracy.
Identify any logical loopholes or trickiness that is too unfair, and make sure the options are completely distinct and correct.
Draft:
{draft}

Provide constructive critique and suggestions for improvement."""
        critique_1 = await _call_gemini(critique_prompt_1, fallback="", timeout=timeout_val, model_preference=pref, max_output_tokens=tokens)
        if not critique_1:
            logging.warning("[PUZZLE PIPELINE] Failed to get critique 1.")
            continue

        refine_prompt_1 = f"""You are the Brainstormer. Revise the puzzle draft using the feedback provided.
Original Draft:
{draft}

Feedback:
{critique_1}

Output the revised puzzle draft clearly."""
        revision_1 = await _call_gemini(refine_prompt_1, fallback="", timeout=timeout_val, model_preference=pref, max_output_tokens=tokens)
        if not revision_1:
            logging.warning("[PUZZLE PIPELINE] Failed to get revision 1.")
            continue

        # Cycle 2: Critique & Refine
        critique_prompt_2 = f"""You are the Refiner. Analyze this revised puzzle draft.
Is there any ambiguity left? Are the question and answer choices mathematically/logically sound?
Revised Draft:
{revision_1}

Provide further feedback or final suggestions to polish it."""
        critique_2 = await _call_gemini(critique_prompt_2, fallback="", timeout=timeout_val, model_preference=pref, max_output_tokens=tokens)
        if not critique_2:
            logging.warning("[PUZZLE PIPELINE] Failed to get critique 2.")
            continue

        refine_prompt_2 = f"""You are the Brainstormer. Take the second round of feedback and refine the puzzle further.
Current Draft:
{revision_1}

Feedback:
{critique_2}

Output the updated puzzle clearly."""
        revision_2 = await _call_gemini(refine_prompt_2, fallback="", timeout=timeout_val, model_preference=pref, max_output_tokens=tokens)
        if not revision_2:
            logging.warning("[PUZZLE PIPELINE] Failed to get revision 2.")
            continue

        # Cycle 3: Critique & Final JSON
        critique_prompt_3 = f"""You are the Refiner. Perform a final check on this revised draft.
Are the question, options, correct answer, and explanation 100% correct and ready?
Revised Draft:
{revision_2}

Provide final polish feedback or state if it is ready."""
        critique_3 = await _call_gemini(critique_prompt_3, fallback="", timeout=timeout_val, model_preference=pref, max_output_tokens=tokens)
        if not critique_3:
            logging.warning("[PUZZLE PIPELINE] Failed to get critique 3.")
            continue

        final_prompt = f"""You are the Brainstormer. Produce the final puzzle based on all feedback.
Ensure it is free of all ambiguities. You must format the final output as a single valid JSON object.

Final Draft:
{revision_2}

Feedback:
{critique_3}

LATEX & MATH MANDATE:
- You MUST use standard LaTeX ($...$, \\frac{{a}}{{b}}, \\sqrt{{x}}, \\alpha, \\theta, \\int, \\sum, etc.) for all math equations, formulas, expressions, and options.
- Keep JSON structure strictly valid.

CHEMISTRY NOTATION MANDATE (for Chemistry puzzles):
- Use proper IUPAC names and structural formulas (CH₃COOH, C₆H₅OH, etc.)
- Use → for forward reactions, ⇌ for equilibrium
- Write functional groups explicitly: —OH, —COOH, —NH₂, —CHO, C=O
- Our bot renders these as structural diagrams automatically.

Respond ONLY with a JSON object in this format (no markdown, no extra text):
{{
  "question": "...",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "answer": "A/B/C/D",
  "explanation": "..."
}}"""
        final_json_raw = await _call_gemini(final_prompt, fallback="", timeout=timeout_val, model_preference=pref, max_output_tokens=tokens)
        if not final_json_raw:
            logging.warning("[PUZZLE PIPELINE] Failed to get final JSON.")
            continue

        try:
            candidate = safe_load_json(final_json_raw)
            if not isinstance(candidate, dict): continue
            required_keys = {"question", "options", "answer", "explanation"}
            if not required_keys.issubset(candidate):
                continue
            if not isinstance(candidate["options"], dict) or not set("ABCD").issubset(candidate["options"].keys()):
                continue
            candidate["answer"] = candidate["answer"].strip().upper()
            if candidate["answer"] not in {"A", "B", "C", "D"}:
                continue
            if not candidate["options"].get(candidate["answer"]):
                continue
        except Exception as e:
            logging.warning(f"[PUZZLE PIPELINE] JSON parse/validation failed: {e}")
            continue

        # Stage 3: Fresh solver session 1
        solver_prompt = f"""Solve this puzzle step-by-step and determine which option (A, B, C, or D) is correct.
Do not look at any other information. Solve it completely fresh and show your reasoning.

Question: {candidate['question']}
Options:
A: {candidate['options']['A']}
B: {candidate['options']['B']}
C: {candidate['options']['C']}
D: {candidate['options']['D']}

Respond ONLY with this JSON format (no markdown, no extra text):
{{
  "solved_answer": "A/B/C/D",
  "step_by_step_solution": "..."
}}"""
        raw_solve_1 = await _call_gemini(solver_prompt, fallback="", timeout=timeout_val, model_preference=pref, max_output_tokens=tokens)
        if not raw_solve_1:
            logging.warning("[PUZZLE PIPELINE] Solver 1 failed to respond.")
            continue

        try:
            solve_1 = safe_load_json(raw_solve_1)
            ans_1 = solve_1.get("solved_answer", "").strip().upper()
            if ans_1 != candidate["answer"]:
                logging.warning(f"[PUZZLE PIPELINE] Solver 1 disagreed! Intended: {candidate['answer']}, Solved: {ans_1}")
                continue
        except Exception as e:
            logging.warning(f"[PUZZLE PIPELINE] Solver 1 parsing failed: {e}")
            continue

        # Stage 4: Fresh solver session 2
        solver_prompt_2 = f"""Analyze and solve this multiple-choice question carefully. Solve it independently.

Question: {candidate['question']}
Options:
A: {candidate['options']['A']}
B: {candidate['options']['B']}
C: {candidate['options']['C']}
D: {candidate['options']['D']}

Respond ONLY with a JSON object:
{{
  "solved_answer": "A/B/C/D",
  "reasoning": "..."
}}"""
        raw_solve_2 = await _call_gemini(solver_prompt_2, fallback="", timeout=timeout_val, model_preference=pref, max_output_tokens=tokens)
        if not raw_solve_2:
            logging.warning("[PUZZLE PIPELINE] Solver 2 failed to respond.")
            continue

        try:
            solve_2 = safe_load_json(raw_solve_2)
            ans_2 = solve_2.get("solved_answer", "").strip().upper()
            if ans_2 != candidate["answer"]:
                logging.warning(f"[PUZZLE PIPELINE] Solver 2 disagreed! Intended: {candidate['answer']}, Solved: {ans_2}")
                continue
        except Exception as e:
            logging.warning(f"[PUZZLE PIPELINE] Solver 2 parsing failed: {e}")
            continue

        logging.info(f"[PUZZLE PIPELINE] Puzzle successfully verified twice! Topic: {topic}, Weekly: {is_weekly}")
        # Return candidate intact (raw LaTeX preserved for mathtext image renderer; readability checkpoint in puzzle_cog will handle Discord text sanitization)
        return candidate

    logging.warning("[PUZZLE PIPELINE] All attempts failed to verify. Using static fallback.")
    if is_weekly:
        return random.choice(_FALLBACK_WEEKLY_PUZZLES)
    else:
        return random.choice(_FALLBACK_PUZZLES)

_FALLBACK_KICK_MESSAGES = [
    "{username}, {hours_today}h today? That's how you prepare for JEE? Your {hours_alltime}h all-time is laughing at your {streak}-day streak. You've missed {missed_days} days. Get back to work.",
    "Is this a joke, {username}? {hours_today}h today won't even get you through the gate. {hours_alltime}h all-time means nothing if you drop your {streak}-day streak and miss {missed_days} days.",
    'Wake up, {username}. {hours_today}h is unacceptable. You have {hours_alltime}h all-time and a {streak}-day streak, yet you missed {missed_days} days. Stop slacking.',
    "You call yourself an aspirant, {username}? {hours_today}h today is pathetic. Don't let your {hours_alltime}h all-time go to waste over a {streak}-day streak and {missed_days} missed days.",
    "Excuses don't clear JEE, {username}. {hours_today}h today? Your {hours_alltime}h all-time, {streak}-day streak, and {missed_days} missed days show you're not serious.",
    "Top rankers don't sleep on {hours_today}h, {username}. With {hours_alltime}h all-time and a {streak}-day streak, missing {missed_days} days is a disgrace.",
    "{username}, {hours_today}h is a warm-up, not a day's work. You have {hours_alltime}h all-time, a {streak}-day streak, but {missed_days} missed days? Do better.",
    'This is why competition beats you, {username}. {hours_today}h today. {hours_alltime}h all-time. A {streak}-day streak ruined by {missed_days} missed days. Fix it.',
    'Do you want to fail, {username}? Because {hours_today}h today is how you fail. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Prove you belong here.',
    "{username}, you're embarrassing yourself. {hours_today}h today? Remember your {hours_alltime}h all-time and {streak}-day streak. Missing {missed_days} days is unacceptable.",
    'Is {hours_today}h your limit, {username}? Because JEE demands more. Your {hours_alltime}h all-time and {streak}-day streak are overshadowed by {missed_days} missed days.',
    'Stop pretending to study, {username}. {hours_today}h today is fake effort. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Get serious.',
    "{username}, {hours_today}h today is an insult to your goals. You've built {hours_alltime}h all-time and a {streak}-day streak. Don't let {missed_days} missed days destroy it.",
    "You're falling behind, {username}. {hours_today}h today won't cut it. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Start working.",
    "{username}, JEE doesn't care about your {hours_today}h. It cares about results. Your {hours_alltime}h all-time and {streak}-day streak mean nothing with {missed_days} missed days.",
    "You think {hours_today}h is enough, {username}? You're delusional. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Wake up.",
    "{username}, your competition studied double your {hours_today}h today. Your {hours_alltime}h all-time and {streak}-day streak can't save you from {missed_days} missed days.",
    'This is mediocrity, {username}. {hours_today}h today? With {hours_alltime}h all-time and a {streak}-day streak, missing {missed_days} days is pathetic.',
    "{username}, {hours_today}h is the bare minimum. You have {hours_alltime}h all-time and a {streak}-day streak. Don't throw it away on {missed_days} missed days.",
    'Are you even trying, {username}? {hours_today}h today. {hours_alltime}h all-time. {streak}-day streak. {missed_days} missed days. Do you want this or not?',
    '{username}, {hours_today}h today is a joke. Your {hours_alltime}h all-time and {streak}-day streak demand respect. Missing {missed_days} days is disrespecting yourself.',
    "You're wasting time, {username}. {hours_today}h today. {hours_alltime}h all-time. {streak}-day streak. {missed_days} missed days. Get to the desk.",
    "{username}, {hours_today}h today is a ticket to failure. You have {hours_alltime}h all-time and a {streak}-day streak. Don't let {missed_days} missed days define you.",
    'Is this your best, {username}? {hours_today}h today? Your {hours_alltime}h all-time and {streak}-day streak say otherwise. {missed_days} missed days is unacceptable.',
    "{username}, {hours_today}h today? You're playing games with your future. {hours_alltime}h all-time, {streak}-day streak, {missed_days} missed days. Stop playing."
]

_FALLBACK_WAKEUP_MESSAGES = [
    "Good morning {username}. You did {yesterday_hours}h yesterday. Your streak is {streak}. Today's goal is {goal_hours}h. Let's conquer.",
    'Wake up {username}! {yesterday_hours}h yesterday was just the start. Keep your {streak}-day streak alive. Hit {goal_hours}h today.',
    'The sun is up, {username}. You logged {yesterday_hours}h yesterday with a {streak}-day streak. Time to aim for {goal_hours}h today.',
    '{username}, morning! {yesterday_hours}h yesterday is history. Your {streak}-day streak needs {goal_hours}h today to survive.',
    'Rise and grind {username}. {yesterday_hours}h yesterday, {streak}-day streak. Your {goal_hours}h goal for today is waiting.',
    'Time to work {username}. You hit {yesterday_hours}h yesterday and hold a {streak}-day streak. Get that {goal_hours}h today.',
    '{username}, the competition is already awake. {yesterday_hours}h yesterday, {streak}-day streak. Achieve {goal_hours}h today.',
    'Morning {username}. {yesterday_hours}h yesterday is in the past. Focus on your {streak}-day streak and {goal_hours}h goal today.',
    "Wakey wakey {username}. {yesterday_hours}h yesterday, {streak}-day streak. Let's smash the {goal_hours}h target today.",
    "{username}, time to study. {yesterday_hours}h yesterday, {streak}-day streak. Your {goal_hours}h goal won't achieve itself.",
    'Good morning {username}. Building on {yesterday_hours}h yesterday and a {streak}-day streak. Target: {goal_hours}h today.',
    'Rise {username}. {yesterday_hours}h yesterday, {streak}-day streak. Make today count with {goal_hours}h.',
    '{username}, start strong. {yesterday_hours}h yesterday, {streak}-day streak. Focus on your {goal_hours}h goal.',
    "Morning {username}! {yesterday_hours}h yesterday, {streak}-day streak. Let's get to {goal_hours}h today.",
    'Wake up {username}. {yesterday_hours}h yesterday, {streak}-day streak. Time to conquer {goal_hours}h today.',
    '{username}, the grind starts now. {yesterday_hours}h yesterday, {streak}-day streak. Aim for {goal_hours}h.',
    "Morning {username}. {yesterday_hours}h yesterday, {streak}-day streak. Today's mission: {goal_hours}h.",
    "Rise and shine {username}. {yesterday_hours}h yesterday, {streak}-day streak. Let's hit {goal_hours}h today.",
    '{username}, time to focus. {yesterday_hours}h yesterday, {streak}-day streak. Target: {goal_hours}h.',
    'Good morning {username}. {yesterday_hours}h yesterday, {streak}-day streak. Your {goal_hours}h goal awaits.',
    "Wake up {username}. {yesterday_hours}h yesterday, {streak}-day streak. Let's achieve {goal_hours}h today.",
    '{username}, morning! {yesterday_hours}h yesterday, {streak}-day streak. Time to work for {goal_hours}h.',
    'Rise {username}. {yesterday_hours}h yesterday, {streak}-day streak. Focus on {goal_hours}h today.',
    '{username}, start your day. {yesterday_hours}h yesterday, {streak}-day streak. Target: {goal_hours}h.',
    "Morning {username}. {yesterday_hours}h yesterday, {streak}-day streak. Let's smash {goal_hours}h today."
]

_FALLBACK_DROPPED_OFF_MESSAGES = [
    "{username}, you did {hours_today}h but you're {gap}h short of your {goal_hours}h goal. You have {hours_left}h left at {time_str}. Get back to work.",
    'Why stop now, {username}? {hours_today}h is good, but you need {gap}h more for your {goal_hours}h goal. {hours_left}h left ({time_str}).',
    "{username}, don't quit early. {hours_today}h done, {gap}h to go for {goal_hours}h. It's {time_str}, you have {hours_left}h left.",
    "You're not done, {username}. {hours_today}h is a start. Close the {gap}h gap to {goal_hours}h. {hours_left}h left at {time_str}.",
    '{username}, get back in there. {hours_today}h done, {gap}h left for your {goal_hours}h goal. {hours_left}h remaining ({time_str}).',
    "Don't lose momentum, {username}. {hours_today}h done, {gap}h to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    '{username}, you left early. {hours_today}h done, {gap}h remaining for {goal_hours}h. {hours_left}h left ({time_str}).',
    "Finish what you started, {username}. {hours_today}h done, {gap}h to go for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, the day isn't over. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str}).",
    "Keep going, {username}. {hours_today}h done, {gap}h left to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, you're almost there. {hours_today}h done, {gap}h to go for {goal_hours}h. {hours_left}h left ({time_str}).",
    "Don't stop, {username}. {hours_today}h done, {gap}h remaining for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    '{username}, get back to it. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str}).',
    "Stay focused, {username}. {hours_today}h done, {gap}h left to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    '{username}, you can do more. {hours_today}h done, {gap}h to go for {goal_hours}h. {hours_left}h left ({time_str}).',
    "Don't give up, {username}. {hours_today}h done, {gap}h remaining for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    '{username}, push through. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str}).',
    "Keep pushing, {username}. {hours_today}h done, {gap}h left to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, you're close. {hours_today}h done, {gap}h to go for {goal_hours}h. {hours_left}h left ({time_str}).",
    "Don't let up, {username}. {hours_today}h done, {gap}h remaining for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    '{username}, stay strong. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str}).',
    "Keep working, {username}. {hours_today}h done, {gap}h left to hit {goal_hours}h. It's {time_str}, {hours_left}h left.",
    "{username}, you've got this. {hours_today}h done, {gap}h to go for {goal_hours}h. {hours_left}h left ({time_str}).",
    "Don't stop now, {username}. {hours_today}h done, {gap}h remaining for {goal_hours}h. It's {time_str}, {hours_left}h left.",
    '{username}, finish strong. {hours_today}h done, {gap}h gap to {goal_hours}h. {hours_left}h remaining ({time_str}).'
]

_FALLBACK_NOT_STARTED_MESSAGES = [
    "{username}, it's {time_str} and you have 0 hours. You have {hours_left}h left to hit your {goal_hours}h goal. Start now.",
    'Zero hours, {username}? At {time_str}? You have {hours_left}h left for your {goal_hours}h goal. Get moving.',
    '{username}, 0 hours at {time_str} is unacceptable. {hours_left}h left to reach {goal_hours}h. Work.',
    'What are you doing, {username}? 0 hours at {time_str}. {hours_left}h left for {goal_hours}h. Start studying.',
    "{username}, it's {time_str} and you haven't started. {hours_left}h left to hit {goal_hours}h. Go.",
    "0 hours logged, {username}. It's {time_str}. You have {hours_left}h left for your {goal_hours}h goal. Begin.",
    '{username}, stop wasting time. 0 hours at {time_str}. {hours_left}h left to reach {goal_hours}h. Study.',
    'Unacceptable, {username}. 0 hours at {time_str}. {hours_left}h left for {goal_hours}h. Get to work.',
    "{username}, you're falling behind. 0 hours at {time_str}. {hours_left}h left to hit {goal_hours}h. Start.",
    "0 hours, {username}. Seriously? It's {time_str}. You have {hours_left}h left for your {goal_hours}h goal.",
    "{username}, it's {time_str} and you have 0 hours. {hours_left}h left to reach {goal_hours}h. Work now.",
    'Stop procrastinating, {username}. 0 hours at {time_str}. {hours_left}h left for {goal_hours}h. Study.',
    '{username}, 0 hours at {time_str} is a joke. {hours_left}h left to hit {goal_hours}h. Start.',
    "What's your excuse, {username}? 0 hours at {time_str}. You have {hours_left}h left for your {goal_hours}h goal.",
    '{username}, get to work. 0 hours at {time_str}. {hours_left}h left to reach {goal_hours}h.',
    "0 hours, {username}. It's {time_str}. {hours_left}h left for {goal_hours}h. Start studying.",
    "{username}, you're wasting the day. 0 hours at {time_str}. {hours_left}h left to hit {goal_hours}h.",
    'Unbelievable, {username}. 0 hours at {time_str}. You have {hours_left}h left for your {goal_hours}h goal.',
    '{username}, start now. 0 hours at {time_str}. {hours_left}h left to reach {goal_hours}h.',
    "0 hours logged, {username}. It's {time_str}. {hours_left}h left for {goal_hours}h. Work.",
    '{username}, stop stalling. 0 hours at {time_str}. {hours_left}h left to hit {goal_hours}h.',
    'This is bad, {username}. 0 hours at {time_str}. You have {hours_left}h left for your {goal_hours}h goal.',
    "{username}, it's {time_str} and 0 hours. {hours_left}h left to reach {goal_hours}h. Study.",
    "0 hours, {username}. It's {time_str}. {hours_left}h left for {goal_hours}h. Get moving.",
    '{username}, start working. 0 hours at {time_str}. {hours_left}h left to hit {goal_hours}h.'
]

_FALLBACK_GOAL_CONGRATS_MESSAGES = [
    'Awesome job {username}! You hit {hours_today}h today, crushing your {goal_hours}h goal.',
    'Congratulations {username}! {hours_today}h logged today. Your {goal_hours}h goal is done.',
    '{username}, you did it! {hours_today}h today, beating your {goal_hours}h goal. Great work.',
    'Way to go {username}! {hours_today}h today. You smashed your {goal_hours}h goal.',
    'Excellent work {username}! {hours_today}h logged. Your {goal_hours}h goal is history.',
    '{username}, fantastic job! {hours_today}h today, surpassing your {goal_hours}h goal.',
    'Brilliant {username}! {hours_today}h today. You crushed your {goal_hours}h goal.',
    'Great effort {username}! {hours_today}h logged today, beating your {goal_hours}h goal.',
    '{username}, superb work! {hours_today}h today. You smashed your {goal_hours}h goal.',
    'Outstanding {username}! {hours_today}h today, crushing your {goal_hours}h goal.',
    'Phenomenal {username}! {hours_today}h logged. Your {goal_hours}h goal is done.',
    '{username}, incredible job! {hours_today}h today, beating your {goal_hours}h goal.',
    'Amazing {username}! {hours_today}h today. You smashed your {goal_hours}h goal.',
    'Top notch {username}! {hours_today}h logged today, surpassing your {goal_hours}h goal.',
    '{username}, stellar work! {hours_today}h today. You crushed your {goal_hours}h goal.',
    'Fantastic {username}! {hours_today}h today, beating your {goal_hours}h goal.',
    'Superb {username}! {hours_today}h logged. Your {goal_hours}h goal is history.',
    '{username}, excellent job! {hours_today}h today, smashing your {goal_hours}h goal.',
    'Brilliant effort {username}! {hours_today}h today. You crushed your {goal_hours}h goal.',
    'Great job {username}! {hours_today}h logged today, surpassing your {goal_hours}h goal.',
    '{username}, awesome work! {hours_today}h today. You smashed your {goal_hours}h goal.',
    'Outstanding effort {username}! {hours_today}h today, beating your {goal_hours}h goal.',
    'Phenomenal work {username}! {hours_today}h logged. Your {goal_hours}h goal is done.',
    '{username}, incredible effort! {hours_today}h today, surpassing your {goal_hours}h goal.',
    'Amazing job {username}! {hours_today}h today. You crushed your {goal_hours}h goal.'
]

_FALLBACK_PUSH_PAST_LIMIT_MESSAGES = [
    '{username}, you hit {hours_today}h and your {goal_hours}h goal, but you have {hours_left}h left. Push for {extra_target}h.',
    "Great job hitting {goal_hours}h, {username}. You're at {hours_today}h. With {hours_left}h left, aim for {extra_target}h.",
    '{username}, {hours_today}h is good, but your {goal_hours}h goal is just a milestone. {hours_left}h left. Hit {extra_target}h.',
    'You reached {goal_hours}h, {username}. Currently at {hours_today}h. {hours_left}h remaining. Go for {extra_target}h.',
    '{username}, {hours_today}h logged. {goal_hours}h achieved. You have {hours_left}h left. Can you reach {extra_target}h?',
    "Don't stop at {goal_hours}h, {username}. {hours_today}h done, {hours_left}h left. Push to {extra_target}h.",
    '{username}, you beat your {goal_hours}h goal with {hours_today}h. With {hours_left}h left, target {extra_target}h.',
    'Good work on {goal_hours}h, {username}. {hours_today}h done. {hours_left}h remaining. Aim for {extra_target}h.',
    '{username}, {hours_today}h logged. {goal_hours}h crushed. You have {hours_left}h left. Hit {extra_target}h.',
    'Keep going, {username}. {goal_hours}h done, currently at {hours_today}h. {hours_left}h left. Go for {extra_target}h.',
    '{username}, you hit {hours_today}h and your {goal_hours}h goal. With {hours_left}h left, push for {extra_target}h.',
    "Great job hitting {goal_hours}h, {username}. You're at {hours_today}h. {hours_left}h remaining. Aim for {extra_target}h.",
    '{username}, {hours_today}h is good, but your {goal_hours}h goal is done. {hours_left}h left. Hit {extra_target}h.',
    'You reached {goal_hours}h, {username}. Currently at {hours_today}h. With {hours_left}h left, go for {extra_target}h.',
    '{username}, {hours_today}h logged. {goal_hours}h achieved. {hours_left}h remaining. Can you reach {extra_target}h?',
    "Don't stop at {goal_hours}h, {username}. {hours_today}h done, {hours_left}h left. Push to {extra_target}h.",
    '{username}, you beat your {goal_hours}h goal with {hours_today}h. {hours_left}h remaining. Target {extra_target}h.',
    'Good work on {goal_hours}h, {username}. {hours_today}h done. With {hours_left}h left, aim for {extra_target}h.',
    '{username}, {hours_today}h logged. {goal_hours}h crushed. {hours_left}h remaining. Hit {extra_target}h.',
    'Keep going, {username}. {goal_hours}h done, currently at {hours_today}h. With {hours_left}h left, go for {extra_target}h.',
    '{username}, you hit {hours_today}h and your {goal_hours}h goal. {hours_left}h remaining. Push for {extra_target}h.',
    "Great job hitting {goal_hours}h, {username}. You're at {hours_today}h. With {hours_left}h left, aim for {extra_target}h.",
    '{username}, {hours_today}h is good, but your {goal_hours}h goal is done. {hours_left}h remaining. Hit {extra_target}h.',
    'You reached {goal_hours}h, {username}. Currently at {hours_today}h. With {hours_left}h left, go for {extra_target}h.',
    '{username}, {hours_today}h logged. {goal_hours}h achieved. {hours_left}h remaining. Can you reach {extra_target}h?'
]

_FALLBACK_STUDY_REMINDER_MESSAGES = [
    "{username}, you're at {hours_today}h. You have a {gap}h gap at {time_str}. Keep going.",
    'Study time, {username}. {hours_today}h done, {gap}h remaining at {time_str}.',
    "{username}, reminder: {hours_today}h logged, {gap}h to go. It's {time_str}.",
    'Keep studying, {username}. {hours_today}h done, {gap}h gap at {time_str}.',
    '{username}, stay focused. {hours_today}h logged, {gap}h remaining. Time: {time_str}.',
    'Study reminder, {username}. {hours_today}h done, {gap}h to go at {time_str}.',
    "{username}, back to work. {hours_today}h logged, {gap}h gap. It's {time_str}.",
    'Keep pushing, {username}. {hours_today}h done, {gap}h remaining at {time_str}.',
    "{username}, don't stop. {hours_today}h logged, {gap}h to go. Time: {time_str}.",
    'Focus time, {username}. {hours_today}h done, {gap}h gap at {time_str}.',
    "{username}, you're at {hours_today}h. You have a {gap}h gap at {time_str}. Keep going.",
    'Study time, {username}. {hours_today}h done, {gap}h remaining at {time_str}.',
    "{username}, reminder: {hours_today}h logged, {gap}h to go. It's {time_str}.",
    'Keep studying, {username}. {hours_today}h done, {gap}h gap at {time_str}.',
    '{username}, stay focused. {hours_today}h logged, {gap}h remaining. Time: {time_str}.',
    'Study reminder, {username}. {hours_today}h done, {gap}h to go at {time_str}.',
    "{username}, back to work. {hours_today}h logged, {gap}h gap. It's {time_str}.",
    'Keep pushing, {username}. {hours_today}h done, {gap}h remaining at {time_str}.',
    "{username}, don't stop. {hours_today}h logged, {gap}h to go. Time: {time_str}.",
    'Focus time, {username}. {hours_today}h done, {gap}h gap at {time_str}.',
    "{username}, you're at {hours_today}h. You have a {gap}h gap at {time_str}. Keep going.",
    'Study time, {username}. {hours_today}h done, {gap}h remaining at {time_str}.',
    "{username}, reminder: {hours_today}h logged, {gap}h to go. It's {time_str}.",
    'Keep studying, {username}. {hours_today}h done, {gap}h gap at {time_str}.',
    '{username}, stay focused. {hours_today}h logged, {gap}h remaining. Time: {time_str}.'
]

# ============================================================
# PERSONALIZED NOTIFICATION GENERATORS
# ============================================================

async def personalized_kick_msg(username: str, hours_today: float, hours_alltime: float, streak: int, puzzle_solved: bool, missed_days: int) -> str:
    prompt = f"""Write a brutal, toxic, yet highly motivating wake-up kick message for a JEE aspirant named {username} who failed to solve the daily puzzle.

Context:
- They studied {hours_today:.1f}h today.
- They have {hours_alltime:.1f}h all-time.
- Their study streak was {streak} days.
- They missed {missed_days} consecutive days of study/puzzle solving.

Rules:
- 3 sentences MAX.
- Tone: Extremely blunt, disappointed, high-standards, JEE-focused. Point out that JEE ranks aren't won by slackers.
- Use their actual stats (hours today, alltime, streak) to critique them.
- Tell them to use `/verify` and solve 3 archived puzzles to prove they belong back.
- Plain text only, no markdown."""

    try:
        fallback = random.choice(_FALLBACK_KICK_MESSAGES).format(username=username, hours_today=hours_today, hours_alltime=hours_alltime, streak=streak, missed_days=missed_days)
    except KeyError:
        fallback = "Fallback error. Please check your inputs."
    res = await _call_gemini_fast(prompt, fallback=fallback, max_output_tokens=256)
    return clean_message_text(res)

async def personalized_wakeup_msg(username: str, yesterday_hours: float, streak: int, goal_hours: float) -> str:
    prompt = f"""Write a short, sharp 6 AM wake-up study reminder for a JEE aspirant named {username}.

Context:
- Yesterday they studied {yesterday_hours:.1f}h.
- Their current streak is {streak} days.
- Their daily study goal is {goal_hours:.1f}h.

Rules:
- 2 sentences MAX.
- Tone: Action-oriented, direct, motivating.
- Reference their yesterday's study hours: if yesterday was 0, be harsh/demanding; if yesterday was good, be encouraging but remind them today starts at 0.
- End with a strong call to action to get in a study voice channel immediately.
- Plain text only."""

    try:
        fallback = random.choice(_FALLBACK_WAKEUP_MESSAGES).format(username=username, yesterday_hours=yesterday_hours, streak=streak, goal_hours=goal_hours)
    except KeyError:
        fallback = "Fallback error. Please check your inputs."
    res = await _call_gemini_fast(prompt, fallback=fallback, max_output_tokens=256)
    return clean_message_text(res)

async def dropped_off_reminder(username: str, hours_today: float, goal_hours: float, hours_left: float, time_str: str, peer_name: str = "", peer_hours: float = 0.0) -> str:
    gap = max(0.0, goal_hours - hours_today)
    peer_ctx = f"Their study partner {peer_name} currently has {peer_hours:.1f}h today." if peer_name else ""

    prompt = f"""Write a short, encouraging Discord DM for a JEE aspirant named {username} who studied {hours_today:.1f}h today but has stopped and left their study channel.

Context: It's {time_str} IST. They're {gap:.1f}h short of their {goal_hours:.1f}h daily goal. {hours_left:.1f}h left in the day. {peer_ctx}

Tone: Warm but urgent. They showed up — acknowledge that. Push them to come back and finish.
- 2-3 sentences MAX
- Reference their actual hours
- End with a specific call to action
- Plain text only, no markdown"""

    try:
        fallback = random.choice(_FALLBACK_DROPPED_OFF_MESSAGES).format(username=username, hours_today=hours_today, gap=gap, goal_hours=goal_hours, hours_left=hours_left, time_str=time_str)
    except KeyError:
        fallback = "Fallback error. Please check your inputs."
    res = await _call_gemini_fast(prompt, fallback=fallback, max_output_tokens=256)
    return clean_message_text(res)

async def not_started_reminder(username: str, time_str: str, goal_hours: float, hours_left: float, peer_name: str = "", peer_hours: float = 0.0) -> str:
    peer_ctx = f"{peer_name} already has {peer_hours:.1f}h logged today." if peer_name else ""

    prompt = f"""Write a blunt, no-nonsense Discord DM to a JEE aspirant named {username} who has studied ZERO hours today.

Context: It's {time_str} IST. Their daily goal is {goal_hours:.1f}h. {hours_left:.1f}h left in the day. {peer_ctx}

Rules:
- 3 sentences MAXIMUM
- No sympathy — zero hours is unacceptable
- Be specific: mention it's {time_str} and they have {hours_left:.1f}h left
- End with: get in a study channel RIGHT NOW
- Plain text only, no markdown, vary the phrasing each time"""

    try:
        fallback = random.choice(_FALLBACK_NOT_STARTED_MESSAGES).format(username=username, time_str=time_str, hours_left=hours_left, goal_hours=goal_hours)
    except KeyError:
        fallback = "Fallback error. Please check your inputs."
    res = await _call_gemini_fast(prompt, fallback=fallback, max_output_tokens=256)
    return clean_message_text(res)

async def goal_congrats_msg(username: str, hours_today: float, goal_hours: float) -> str:
    prompt = f"""Write a genuine, energetic congratulations Discord DM for a JEE aspirant named {username} who just crossed their daily study goal.

Stats: Studied {hours_today:.1f}h today, goal was {goal_hours:.1f}h.

Rules:
- 2-3 sentences MAX
- Genuine praise, not hollow
- Acknowledge specifically how much they did
- End by telling them they've earned their rest — no more reminders today
- Plain text only"""

    try:
        fallback = random.choice(_FALLBACK_GOAL_CONGRATS_MESSAGES).format(username=username, hours_today=hours_today, goal_hours=goal_hours)
    except KeyError:
        fallback = "Fallback error. Please check your inputs."
    res = await _call_gemini_fast(prompt, fallback=fallback, max_output_tokens=256)
    return clean_message_text(res)

async def push_past_limit_msg(username: str, hours_today: float, goal_hours: float, hours_left: float) -> str:
    extra_target = goal_hours + 2.0

    prompt = f"""Write a hype, challenge-style Discord DM for a JEE aspirant named {username} who just hit their {goal_hours:.1f}h daily goal and has {hours_left:.1f}h left in the day.

Goal: Push them to keep going beyond the goal. Top rankers don't stop at the minimum.

Rules:
- 2-3 sentences MAX
- Challenging and motivating, topper energy
- Reference that they have {hours_left:.1f}h left — why stop now?
- Suggest pushing to {extra_target:.0f}h total
- Plain text only, no markdown"""

    try:
        fallback = random.choice(_FALLBACK_PUSH_PAST_LIMIT_MESSAGES).format(username=username, hours_today=hours_today, goal_hours=goal_hours, hours_left=hours_left, extra_target=extra_target)
    except KeyError:
        fallback = "Fallback error. Please check your inputs."
    res = await _call_gemini_fast(prompt, fallback=fallback, max_output_tokens=256)
    return clean_message_text(res)

async def personalized_study_reminder(username: str, hours_today: float, goal_hours: float, time_str: str, peer_name: str = "", peer_hours: float = 0.0) -> str:
    gap = max(0.0, goal_hours - hours_today)
    peer_ctx = f"{peer_name} has {peer_hours:.1f}h today." if peer_name else ""

    prompt = f"""Write a short, direct study reminder Discord DM for a JEE aspirant named {username}.

Context: It's {time_str} IST. Studied {hours_today:.1f}h today. Goal: {goal_hours:.1f}h. {"Behind by " + str(round(gap, 1)) + "h." if gap > 0 else "GOAL ALREADY HIT — push further."} {peer_ctx}

Rules:
- 2 sentences MAX
- Direct, no filler words
- Reference their actual numbers
- Plain text only"""

    try:
        fallback = random.choice(_FALLBACK_STUDY_REMINDER_MESSAGES).format(username=username, hours_today=hours_today, gap=gap, time_str=time_str)
    except KeyError:
        fallback = "Fallback error. Please check your inputs."
    res = await _call_gemini_fast(prompt, fallback=fallback, max_output_tokens=256)
    return clean_message_text(res)


# ============================================================
# LOGIC / MENTAL APTITUDE VERIFICATION PUZZLES
# Curated for high quality, clarity, and fast solving.
# ============================================================
_LOGIC_VERIFICATION_PUZZLES = [
    {
        "question": "A clock loses 10 minutes every hour. It was set correctly at 12:00 PM (noon). What time will it show when the actual time is 6:00 PM on the same day?",
        "options": {
            "A": "5:00 PM",
            "B": "5:10 PM",
            "C": "4:50 PM",
            "D": "5:20 PM"
        },
        "answer": "A",
        "explanation": "From 12:00 PM to 6:00 PM is exactly 6 hours. Since the clock loses 10 minutes per hour, in 6 hours it will lose 6 * 10 = 60 minutes (1 hour). Therefore, it will show 5:00 PM instead of 6:00 PM."
    },
    {
        "question": "A drawer contains 10 black socks and 10 white socks. What is the minimum number of socks you must pull out in the dark to guarantee that you have at least one matching pair?",
        "options": {
            "A": "3",
            "B": "4",
            "C": "11",
            "D": "2"
        },
        "answer": "A",
        "explanation": "There are only 2 colors. If you pull 3 socks, by the Pigeonhole Principle, at least two of them must be of the same color (either 2 black + 1 white, or 1 black + 2 white)."
    },
    {
        "question": "Lily pads in a lake double in size every day. If it takes 48 days for the lily pads to completely cover the lake, how many days does it take to cover exactly half of the lake?",
        "options": {
            "A": "24 days",
            "B": "47 days",
            "C": "12 days",
            "D": "46 days"
        },
        "answer": "B",
        "explanation": "Since the lily pads double in size every day, on the day before the lake is fully covered, it must have been half covered. Thus, it was half covered on day 47."
    },
    {
        "question": "If 5 machines take 5 minutes to make 5 widgets, how long would it take 100 machines to make 100 widgets?",
        "options": {
            "A": "100 minutes",
            "B": "5 minutes",
            "C": "20 minutes",
            "D": "50 minutes"
        },
        "answer": "B",
        "explanation": "If 5 machines make 5 widgets in 5 minutes, it means each machine takes 5 minutes to make 1 widget. If you run 100 machines concurrently, they will make 100 widgets in the same 5 minutes."
    },
    {
        "question": "A bear walks 1 mile South, then 1 mile East, and then 1 mile North, ending up exactly where it started. What color is the bear?",
        "options": {
            "A": "Black",
            "B": "Brown",
            "C": "White",
            "D": "Grey"
        },
        "answer": "C",
        "explanation": "The only place on Earth where you can walk 1 mile South, 1 mile East, and 1 mile North and return to the starting point is the North Pole. The bears at the North Pole are polar bears, which are white."
    },
    {
        "question": "A man is looking at a portrait. He says: 'Brothers and sisters I have none, but this man's father is my father's son.' Who is in the portrait?",
        "options": {
            "A": "The man himself",
            "B": "The man's father",
            "C": "The man's son",
            "D": "The man's uncle"
        },
        "answer": "C",
        "explanation": "Since the man has no siblings, 'my father's son' must be the man himself. Therefore, the phrase simplifies to 'this man's father is myself', meaning the portrait is of the man's son."
    },
    {
        "question": "A farmer has 17 sheep. All but 9 of them die in a sudden plague. How many living sheep does the farmer have left?",
        "options": {
            "A": "8",
            "B": "9",
            "C": "17",
            "D": "0"
        },
        "answer": "B",
        "explanation": "The statement says 'All but 9 die', which means 9 sheep did not die and are still alive."
    },
    {
        "question": "A cylinder has a height of 9 cm and a circumference of 4 cm. A string is wound symmetrically around it exactly 3 times from the bottom to the top. What is the minimum length of the string?",
        "options": {
            "A": "12 cm",
            "B": "15 cm",
            "C": "13 cm",
            "D": "18 cm"
        },
        "answer": "B",
        "explanation": "If you cut the cylinder along a vertical line and flatten it, it becomes a 9x4 rectangle. The string is split into 3 segments. Each segment has a vertical height of 9/3 = 3 cm and horizontal length equal to the circumference of 4 cm. By Pythagoras, length of each segment = √(3² + 4²) = 5 cm. Total length = 3 * 5 = 15 cm."
    },
    {
        "question": "You enter a cold, dark cabin in the woods. You only have a single match. Inside the cabin, there is a candle, a wood stove, and a kerosene lamp. What do you light first?",
        "options": {
            "A": "The candle",
            "B": "The match",
            "C": "The wood stove",
            "D": "The kerosene lamp"
        },
        "answer": "B",
        "explanation": "Before you can light the candle, wood stove, or kerosene lamp, you must first strike and light the match."
    },
    {
        "question": "If you write down all the numbers from 1 to 100, how many times does the digit '9' appear?",
        "options": {
            "A": "19",
            "B": "20",
            "C": "10",
            "D": "21"
        },
        "answer": "B",
        "explanation": "The digit 9 appears in the units place 10 times: 9, 19, 29, 39, 49, 59, 69, 79, 89, 99. It appears in the tens place 10 times: 90, 91, 92, 93, 94, 95, 96, 97, 98, 99. Total appearances = 10 + 10 = 20 (99 counts twice)."
    },
    {
        "question": "A bottle of water and a cup of tea cost $1.10 in total. The tea costs $1.00 more than the water. How much does the water cost?",
        "options": {
            "A": "$0.10",
            "B": "$0.05",
            "C": "$0.15",
            "D": "$0.01"
        },
        "answer": "B",
        "explanation": "Let water be x. Tea is x + 1.00. Total = x + x + 1.00 = 1.10 => 2x = 0.10 => x = 0.05. Water costs $0.05 (5 cents) and tea costs $1.05."
    }
]


async def generate_logic_puzzle() -> dict:
    """
    Generates a tricky logic puzzle using the AI brainstormer/refiner pipeline.
    Falls back to _LOGIC_VERIFICATION_PUZZLES if it fails or times out.
    """
    try:
        puzzle = await generate_puzzle(topic="logic", is_weekly=False)
        # If generate_puzzle returns one of the default JEE puzzles from _FALLBACK_PUZZLES,
        # replace it with a random puzzle from our premium logic set.
        if puzzle in _FALLBACK_PUZZLES:
            return random.choice(_LOGIC_VERIFICATION_PUZZLES)
        return puzzle
    except Exception:
        return random.choice(_LOGIC_VERIFICATION_PUZZLES)

async def fetch_gemini_chemistry_info(term: str) -> dict:
    """Uses Gemini AI to generate structured JSON for complex chemistry terms, mixtures, and non-2D structure concepts."""
    try:
        prompt = f"""Generate structured chemistry details for '{term}'.
Return ONLY a raw valid JSON object with NO markdown backticks, matching this exact schema:
{{
    "title": "Full Descriptive Name",
    "type": "Chemical Category / Type (e.g. Element, Mixture, Reaction, Concept)",
    "formula": "Chemical Formula or Main Composition",
    "description": "2-sentence clear chemistry overview.",
    "major_components": ["Component 1", "Component 2", "Component 3"],
    "reactions": ["Reaction equation or chemical process 1"]
}}"""
        resp = await ask_gemini(prompt)
        if not resp:
            return None
        cleaned = re.sub(r'```json\s*|\s*```', '', resp).strip()
        data = json.loads(cleaned)
        return data
    except Exception as e:
        logging.warning(f"[GEMINI CHEM INFO] Failed for '{term}': {e}")
        return None

async def fetch_gemini_math_info(query: str) -> dict:
    """Uses Gemini AI to solve any math, calculus, algebra, geometry, or physics problem step-by-step."""
    try:
        prompt = f"""Solve this mathematics/physics problem step-by-step for a top JEE student: '{query}'.
Return ONLY a raw valid JSON object with NO markdown backticks, matching this exact schema:
{{
    "title": "Topic or Problem Title",
    "type": "Math Category (e.g. Calculus, Algebra, Linear Algebra, Trigonometry, Mechanics)",
    "solution_steps": [
        "Step 1: ...",
        "Step 2: ...",
        "Step 3: ..."
    ],
    "final_answer": "Final exact answer",
    "latex_formula": "Key LaTeX formula representing the final answer or main step",
    "plot_expression": "Optional numpy plottable expression in x like np.sin(x)*np.exp(-x/5) or None"
}}"""
        resp = await ask_gemini(prompt)
        if not resp:
            return None
        cleaned = re.sub(r'```json\s*|\s*```', '', resp).strip()
        data = json.loads(cleaned)
        return data
    except Exception as e:
        logging.warning(f"[GEMINI MATH INFO] Failed for '{query}': {e}")
        return None
