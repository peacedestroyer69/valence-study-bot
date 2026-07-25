import re
import os

with open(r'C:\Users\ROG\Documents\antigravity\A\cogs\gemini_brain.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Add _call_gemini_fast
fast_func = """
async def _call_gemini_fast(prompt: str, fallback: str, timeout: float = 15.0, max_output_tokens: int = 512) -> str:
    \"\"\"Calls Gemini API with fast strategy: cycle models within each key before rotating to next key.\"\"\"
    if not _GENAI_AVAILABLE or not _KEYS:
        return fallback

    pref = _MODEL_PREFERENCE

    for attempt in range(len(_KEYS)):
        key_idx = (_current_key_idx + attempt) % len(_KEYS)
        key = _KEYS[key_idx]
        client = _get_client(key)
        if client is None:
            continue
            
        key_num = key_idx + 1
        _record_key_attempt(key_num)
        
        for model_name in pref:
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
                    logging.info(f"[GEMINI FAST] ✅ Success using '{model_name}' on key #{key_num}")
                    return text
            except asyncio.TimeoutError:
                _record_key_error(key_num, model_name, "timeout", "asyncio timeout exceeded")
                logging.warning(f"[GEMINI FAST] Key #{key_num} timed out using '{model_name}' — trying next model")
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
                    
        await asyncio.sleep(1.0)

    logging.warning("[GEMINI FAST] ❌ All keys and models exhausted — using static fallback")
    return fallback
"""
code = code.replace(
    'logging.warning("[GEMINI] ❌ All models and all keys exhausted — using static fallback")\n    return fallback\n',
    'logging.warning("[GEMINI] ❌ All models and all keys exhausted — using static fallback")\n    return fallback\n' + fast_func
)

# 2. Update generate_puzzle configuration
old_cfg = """    if is_weekly:
        challenge_desc = "an extremely difficult, deep conceptual weekly mega puzzle (covering mathematics, advanced science, logic, or programming). It must require multi-step logical deduction or deep conceptual understanding, and have no time limit to solve. It should be challenging even for very smart students. You have no token limit. Explain the problem, choices, and solution in extreme depth with full mathematical/logical rigor."
        pref = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
        tokens = 3072
    elif topic == "logic":
        challenge_desc = "a tricky logic puzzle or lateral thinking brain teaser — no equations needed. Keep the question, options, and explanation extremely brief and concise (under 80 words total). Do not write long introductions. Save tokens."
        pref = ["gemini-3.6-flash-lite", "gemini-3.5-flash-lite", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.0-flash"]
        tokens = 512
    else:
        topic_map = {
            "jee":   "a JEE-level Physics, Chemistry, or Mathematics MCQ (not trivial — something that requires actual thinking)",
            "mixed": "either a JEE-level MCQ or a logic puzzle — whichever would make the more interesting challenge today",
        }
        topic_desc = topic_map.get(topic, topic_map["mixed"])
        challenge_desc = f"{topic_desc} suitable for Indian JEE aspirants (age 16-18), solvable in under 2 minutes. Keep the explanation reasonable and precise."
        pref = ["gemini-3.6-flash", "gemini-3.6-flash-lite", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash", "gemini-2.0-flash-lite"]
        tokens = 1536"""

new_cfg = """    if is_weekly:
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
        timeout_val = 45.0"""
code = code.replace(old_cfg, new_cfg)

# Replace timeout=20.0 and timeout=25.0 with timeout=timeout_val inside generate_puzzle ONLY
start_idx = code.find('def generate_puzzle')
end_idx = code.find('def personalized_kick_msg')
if start_idx != -1 and end_idx != -1:
    puzzle_func = code[start_idx:end_idx]
    puzzle_func = puzzle_func.replace('timeout=20.0', 'timeout=timeout_val').replace('timeout=25.0', 'timeout=timeout_val')
    code = code[:start_idx] + puzzle_func + code[end_idx:]

# 3. Update all notification/message functions to use _call_gemini_fast
start_idx = code.find('def personalized_kick_msg')
if start_idx != -1:
    notif_code = code[start_idx:]
    notif_code = notif_code.replace('await _call_gemini(', 'await _call_gemini_fast(')
    code = code[:start_idx] + notif_code

with open(r'C:\Users\ROG\Documents\antigravity\A\cogs\gemini_brain.py', 'w', encoding='utf-8') as f:
    f.write(code)

print('File updated successfully.')
