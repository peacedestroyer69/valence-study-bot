# ============================================================
# GEMINI AI BRAIN — YPT Study Bot (v2 — Multi-Key Rotation)
# ============================================================
# Uses up to 4 Gemini API keys in rotation.
# On quota exhaustion (429) or any API error, automatically
# switches to the next key. Falls back to curated static banks
# only if ALL keys fail.
#
# KEYS: Set GEMINI_API_KEY_1 through GEMINI_API_KEY_4 in .env
# and in Render environment variables.
# Never hardcode keys in source — they stay in .env (gitignored).
# ============================================================

import os
import json
import logging
import asyncio
import random

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False
    logging.warning("[GEMINI] google-generativeai not installed. Run: pip install google-generativeai")

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
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite"
]

_current_key_idx = 0
_cached_models: dict[tuple[str, str], object] = {}   # (key, model_name) -> GenerativeModel instance
_rotation_lock = asyncio.Lock()
_init_lock = __import__("threading").Lock()  # Serialize model init (genai.configure is global state)


def _get_model_instance(key: str, model_name: str):
    """Returns the Gemini model instance for a key, initializing if needed."""
    cache_key = (key, model_name)
    if cache_key not in _cached_models:
        # Serialize model initialization because genai.configure() sets global state.
        # Without this lock, concurrent calls could configure key A, then create a
        # model that inadvertently uses key B's configuration.
        with _init_lock:
            # Double-check after acquiring lock (another thread may have initialized it)
            if cache_key in _cached_models:
                return _cached_models[cache_key]
            try:
                from google.generativeai import client as genai_client
                genai.configure(api_key=key)
                model = genai.GenerativeModel(model_name)
                # Immediately capture and bind the client so the model is decoupled
                # from any future genai.configure() calls
                model._client = genai_client.get_default_generative_client()
                _cached_models[cache_key] = model
                logging.info(f"[GEMINI] Initialized model '{model_name}' for key (ends with ...{key[-8:]})")
            except Exception as e:
                logging.error(f"[GEMINI] Failed to init model '{model_name}' for key: {e}")
                return None
    return _cached_models[cache_key]


async def _rotate_key():
    """Rotate to the next available API key."""
    global _current_key_idx
    async with _rotation_lock:
        _current_key_idx = (_current_key_idx + 1) % max(len(_KEYS), 1)
        logging.warning(f"[GEMINI] Rotated to key #{_current_key_idx + 1}")


# ============================================================
# CORE: Call Gemini with automatic key rotation on quota errors
# ============================================================

async def _call_gemini(prompt: str, fallback: str, timeout: float = 18.0, model_preference: list = None) -> str:
    """
    Calls Gemini API. Tries the best model first, then falls back to worse/cheaper models.
    On key error or if all models fail on a key, rotates to the next key.
    Returns fallback string if all keys and models fail.
    """
    if not _GENAI_AVAILABLE or not _KEYS:
        return fallback

    pref = model_preference or _MODEL_PREFERENCE

    keys_tried = set()
    while len(keys_tried) < len(_KEYS):
        key_idx = _current_key_idx % len(_KEYS)
        if key_idx in keys_tried:
            break
        keys_tried.add(key_idx)
        key = _KEYS[key_idx]

        # For the current key, try each model in preference order
        for model_name in pref:
            model = _get_model_instance(key, model_name)
            if model is None:
                continue

            try:
                loop = asyncio.get_running_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda m=model: m.generate_content(prompt)),
                    timeout=timeout,
                )
                text = response.text.strip()
                if text:
                    logging.info(f"[GEMINI] Successful generation using model '{model_name}' on key #{key_idx + 1}")
                    return text
            except asyncio.TimeoutError:
                logging.warning(f"[GEMINI] Key #{key_idx + 1} timed out using '{model_name}' — trying next model/key")
            except Exception as e:
                err_str = str(e).lower()
                # If key is totally invalid, forbidden, or blocked, stop trying other models on this key
                if "api_key" in err_str or "invalid" in err_str or "403" in err_str or "blocked" in err_str:
                    logging.error(f"[GEMINI] Key #{key_idx + 1} is invalid/forbidden/blocked — moving to next key. Error: {e}")
                    break  # Break out of model loop, rotate key
                else:
                    logging.warning(f"[GEMINI] Key #{key_idx + 1} failed with '{model_name}': {e} — trying next model")

        # Rotate key since all models failed or we broke out of loop
        await _rotate_key()

    logging.warning("[GEMINI] All keys and models exhausted — using static fallback")
    return fallback


# ============================================================
# FALLBACK BANKS (used only when ALL Gemini keys fail)
# ============================================================

_FALLBACK_PUZZLES = [
    {"question": "A train travels from A to B at 60 km/h and returns at 40 km/h. What is the average speed?",
     "options": {"A": "48 km/h", "B": "50 km/h", "C": "52 km/h", "D": "45 km/h"},
     "answer": "A",
     "explanation": "Average speed = 2×60×40/(60+40) = 48 km/h. Always use harmonic mean for same-distance round trips."},
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
    {"question": "A clerk at the butcher shop is 5 feet 10 inches tall and wears size 11 shoes. What does he weigh?",
     "options": {"A": "150 lbs", "B": "Meat", "C": "200 lbs", "D": "Vegetables"},
     "answer": "B",
     "explanation": "He is a clerk at a *butcher* shop, so his job is to weigh meat!"},
    {"question": "Some months have 30 days, some have 31. How many months have 28 days?",
     "options": {"A": "1", "B": "6", "C": "12", "D": "4"},
     "answer": "C",
     "explanation": "All 12 months have at least 28 days!"},
    {"question": "Find the sum of the first 100 positive integers: 1 + 2 + 3 + ... + 100.",
     "options": {"A": "5000", "B": "5050", "C": "5100", "D": "4950"},
     "answer": "B",
     "explanation": "Sum of first n integers = n(n+1)/2. For n=100: 100 × 101 / 2 = 5050."},
    {"question": "What is the pH of a 10^-8 M solution of HCl at 25°C?",
     "options": {"A": "8.0", "B": "6.0", "C": "Slightly less than 7.0 (around 6.98)", "D": "7.0"},
     "answer": "C",
     "explanation": "Since HCl is extremely dilute, we must include the H+ concentration from the auto-ionization of water (10^-7 M). The total [H+] is 1.1x10^-7 M, giving pH ≈ 6.98 (slightly acidic)."},
    {"question": "If the speed of light in a medium is 2.0 × 10^8 m/s, what is the refractive index of the medium?",
     "options": {"A": "1.0", "B": "1.33", "C": "1.5", "D": "2.0"},
     "answer": "C",
     "explanation": "Refractive index n = c/v, where c = 3.0×10^8 m/s. So n = 3.0×10^8 / 2.0×10^8 = 1.5."},
    {"question": "How many subsets can be formed from a set containing 5 distinct elements?",
     "options": {"A": "5", "B": "10", "C": "25", "D": "32"},
     "answer": "D",
     "explanation": "The number of subsets of a set with n elements is 2^n. For n=5: 2^5 = 32 subsets (including the empty set)."},
    {"question": "What has keys but no locks, space but no room, you can enter but can't go outside?",
     "options": {"A": "A keyboard", "B": "A prison cell", "C": "A spacecraft", "D": "An elevator"},
     "answer": "A",
     "explanation": "A computer keyboard has keys, a space bar, and an Enter key!"},
    {"question": "What is the hybridization of the central carbon atom in a methane (CH4) molecule?",
     "options": {"A": "sp", "B": "sp2", "C": "sp3", "D": "dsp2"},
     "answer": "C",
     "explanation": "Carbon in CH4 forms 4 single covalent bonds (sigma bonds) with hydrogen, requiring 4 hybrid orbitals, which corresponds to sp3 hybridization."}
]


# ============================================================
# 1. GENERATE DAILY PUZZLE
# ============================================================

def _clean_json_response(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()


async def generate_puzzle(topic: str = "mixed") -> dict:
    """
    Generates a fresh daily puzzle via a multi-stage brainstorming and double-solve logic verification pipeline.
    Falls back to curated bank if all keys/verifications fail.
    topic: 'jee', 'logic', or 'mixed'
    """
    topic_map = {
        "jee":   "a JEE-level Physics, Chemistry, or Mathematics MCQ (not trivial — something that requires actual thinking)",
        "logic": "a tricky logic puzzle or lateral thinking brain teaser — no equations needed",
        "mixed": "either a JEE-level MCQ or a logic puzzle — whichever would make the more interesting challenge today",
    }
    topic_desc = topic_map.get(topic, topic_map["mixed"])

    for attempt in range(3):
        logging.info(f"[PUZZLE PIPELINE] Starting attempt {attempt + 1}/3...")

        # Stage 1: Brainstorm 3 puzzles
        brainstorm_prompt = f"""Generate exactly 3 different options of {topic_desc} suitable for Indian JEE aspirants (age 16-18).
For each option:
- It must be genuinely challenging and require real logic or calculations.
- It must have 4 options (A, B, C, D) and only one correct option.
- It must have a clear explanation.

Respond ONLY with a JSON array of 3 objects containing "question", "options" (dict of A, B, C, D), "answer" (A/B/C/D), and "explanation". Do not add any markdown formatting or extra text.

[
  {{
    "question": "...",
    "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
    "answer": "A",
    "explanation": "..."
  }},
  ...
]"""
        raw_brainstorms = await _call_gemini(brainstorm_prompt, fallback="", timeout=25.0)
        if not raw_brainstorms:
            continue

        try:
            brainstorms = json.loads(_clean_json_response(raw_brainstorms))
            if not isinstance(brainstorms, list) or len(brainstorms) < 1:
                logging.warning("[PUZZLE PIPELINE] Stage 1 returned invalid candidates list structure.")
                continue
        except Exception as e:
            logging.warning(f"[PUZZLE PIPELINE] Stage 1 JSON parse failed: {e}")
            continue

        # Stage 2: Selection of the best candidate
        select_prompt = f"""Evaluate these candidate puzzles and select the absolute best, most challenging, and clearest one.
Candidates:
{json.dumps(brainstorms, indent=2)}

Respond ONLY with the selected puzzle as a single JSON object in this format (no markdown, no extra text):
{{
  "question": "...",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "answer": "A",
  "explanation": "..."
}}"""
        raw_selection = await _call_gemini(select_prompt, fallback="", timeout=20.0)
        if not raw_selection:
            continue

        try:
            candidate = json.loads(_clean_json_response(raw_selection))
            # Validate basic keys and structure
            required_keys = {"question", "options", "answer", "explanation"}
            if not required_keys.issubset(candidate):
                continue
            if not isinstance(candidate["options"], dict) or not set("ABCD").issubset(candidate["options"].keys()):
                continue
            if candidate["answer"] not in {"A", "B", "C", "D"}:
                continue
            if not candidate["options"].get(candidate["answer"]):
                continue
        except Exception as e:
            logging.warning(f"[PUZZLE PIPELINE] Stage 2 validation/parse failed: {e}")
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
        raw_solve_1 = await _call_gemini(solver_prompt, fallback="", timeout=20.0)
        if not raw_solve_1:
            continue

        try:
            solve_1 = json.loads(_clean_json_response(raw_solve_1))
            if solve_1.get("solved_answer") != candidate["answer"]:
                logging.warning(
                    f"[PUZZLE PIPELINE] Solver 1 disagreed! Intended: {candidate['answer']}, "
                    f"Solved: {solve_1.get('solved_answer')}"
                )
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
        raw_solve_2 = await _call_gemini(solver_prompt_2, fallback="", timeout=20.0)
        if not raw_solve_2:
            continue

        try:
            solve_2 = json.loads(_clean_json_response(raw_solve_2))
            if solve_2.get("solved_answer") != candidate["answer"]:
                logging.warning(
                    f"[PUZZLE PIPELINE] Solver 2 disagreed! Intended: {candidate['answer']}, "
                    f"Solved: {solve_2.get('solved_answer')}"
                )
                continue
        except Exception as e:
            logging.warning(f"[PUZZLE PIPELINE] Solver 2 parsing failed: {e}")
            continue

        # Success! Puzzle is verified twice
        logging.info(f"[PUZZLE PIPELINE] Puzzle successfully verified twice! Topic: {topic}")
        return candidate

    logging.warning("[PUZZLE PIPELINE] All attempts failed to verify. Using static fallback.")
    return random.choice(_FALLBACK_PUZZLES)


# ============================================================
# 2. PERSONALIZED KICK DM
# ============================================================

async def personalized_kick_msg(
    username: str,
    hours_today: float,
    hours_alltime: float,
    streak: int,
    puzzle_solved: bool,
    missed_days: int,
) -> str:
    """AI-generated personalized kick message using actual user stats."""
    context = []
    if hours_today < 0.5:
        context.append(f"studied almost nothing today ({hours_today:.1f}h)")
    else:
        context.append(f"only studied {hours_today:.1f}h today")
    if not puzzle_solved:
        context.append("couldn't solve today's daily puzzle")
    if streak == 0:
        context.append("has no active study streak (0 days)")
    if missed_days > 0:
        context.append(f"has missed {missed_days} consecutive days")
    context_str = " and ".join(context)

    prompt = f"""Write a harsh, personalized, brutally honest 4-sentence Discord DM to a JEE aspirant named {username} who just got kicked from their study server.

Facts: They {context_str}. All-time study: {hours_alltime:.0f}h.

Rules:
- 4 sentences MAXIMUM
- Brutally honest, name specific failings, no generic lines
- Tone: disappointed mentor who actually cares, NOT abusive
- Final sentence MUST be: "Use /verify to rejoin — solve 3 puzzles and prove you belong here."
- No markdown headers or bullet points. Plain text only."""

    fallback = (
        f"{username}, you missed the puzzle and barely showed up today. "
        f"This server exists for serious JEE aspirants, and right now you're not acting like one. "
        f"Your {hours_alltime:.0f} hours all-time should mean more than this. "
        f"Use /verify to rejoin — solve 3 puzzles and prove you belong here."
    )
    return await _call_gemini(prompt, fallback=fallback)


# ============================================================
# 3. PERSONALIZED 6 AM WAKE-UP
# ============================================================

async def personalized_wakeup_msg(
    username: str,
    yesterday_hours: float,
    streak: int,
    goal_hours: float,
) -> str:
    """AI-generated personalized 6 AM wake-up message."""
    if yesterday_hours >= goal_hours:
        context = f"yesterday was excellent ({yesterday_hours:.1f}h — hit their {goal_hours:.1f}h goal)"
    elif yesterday_hours > 0:
        context = f"yesterday was below par ({yesterday_hours:.1f}h, missed their {goal_hours:.1f}h goal)"
    else:
        context = "yesterday was a complete zero — didn't study at all"

    streak_ctx = f"{streak}-day streak" if streak > 0 else "no active streak (broken)"

    prompt = f"""Write a punchy, energetic 6 AM wake-up Discord DM for a JEE aspirant named {username}.

Context: {context}. Streak: {streak_ctx}. Daily goal: {goal_hours:.1f}h.

Rules:
- 3 sentences MAX
- High energy, direct, specific to their situation
- If yesterday was good: build on momentum. If bad: make them feel urgency.
- End with a concrete action: what to do RIGHT NOW (e.g., "Open your notes and get in a study VC.")
- Plain text, no markdown, no emojis in the text itself (they'll be added separately)"""

    fallback = (
        f"It's 6 AM, {username}. "
        f"{'Yesterday was ' + str(round(yesterday_hours, 1)) + 'h — build on it today.' if yesterday_hours > 0 else 'Yesterday was a zero. Today is your redemption.'} "
        f"Open your notes and get in a study VC now."
    )
    return await _call_gemini(prompt, fallback=fallback)


# ============================================================
# 4. PERSONALIZED DROPPED-OFF REMINDER (encouraging)
# ============================================================

async def dropped_off_reminder(
    username: str,
    hours_today: float,
    goal_hours: float,
    hours_left: float,
    time_str: str,
    peer_name: str = "",
    peer_hours: float = 0.0,
) -> str:
    """AI-generated encouraging reminder for users who studied some but stopped."""
    gap = max(0.0, goal_hours - hours_today)
    peer_ctx = f"Their study partner {peer_name} currently has {peer_hours:.1f}h today." if peer_name else ""

    prompt = f"""Write a short, encouraging Discord DM for a JEE aspirant named {username} who studied {hours_today:.1f}h today but has stopped and left their study channel.

Context: It's {time_str} IST. They're {gap:.1f}h short of their {goal_hours:.1f}h daily goal. {hours_left:.1f}h left in the day. {peer_ctx}

Tone: Warm but urgent. They showed up — acknowledge that. Push them to come back and finish.
- 2-3 sentences MAX
- Reference their actual hours
- End with a specific call to action
- Plain text only, no markdown"""

    fallback = (
        f"Good start with {hours_today:.1f}h, {username}! "
        f"You're only {gap:.1f}h away from your daily goal — don't let today's effort go to waste. "
        f"Get back in a study channel and finish what you started."
    )
    return await _call_gemini(prompt, fallback=fallback)


# ============================================================
# 5. HARSH REMINDER (never started today)
# ============================================================

async def not_started_reminder(
    username: str,
    time_str: str,
    goal_hours: float,
    hours_left: float,
    peer_name: str = "",
    peer_hours: float = 0.0,
) -> str:
    """AI-generated harsh reminder for users who haven't studied at all today."""
    peer_ctx = f"{peer_name} already has {peer_hours:.1f}h logged today." if peer_name else ""

    prompt = f"""Write a blunt, no-nonsense Discord DM to a JEE aspirant named {username} who has studied ZERO hours today.

Context: It's {time_str} IST. Their daily goal is {goal_hours:.1f}h. {hours_left:.1f}h left in the day. {peer_ctx}

Rules:
- 3 sentences MAXIMUM
- No sympathy — zero hours is unacceptable
- Be specific: mention it's {time_str} and they have {hours_left:.1f}h left
- End with: get in a study channel RIGHT NOW
- Plain text only, no markdown, vary the phrasing each time"""

    fallback = (
        f"{username}, it's {time_str} and you have 0 hours studied today. "
        f"{'Your partner ' + peer_name + ' already has ' + str(round(peer_hours, 1)) + 'h. ' if peer_name else ''}"
        f"Get in a study channel right now — {hours_left:.1f}h left in the day."
    )
    return await _call_gemini(prompt, fallback=fallback)


# ============================================================
# 6. GOAL CROSSED — CONGRATS
# ============================================================

async def goal_congrats_msg(
    username: str,
    hours_today: float,
    goal_hours: float,
) -> str:
    """AI-generated congratulations when user crosses their daily goal."""
    prompt = f"""Write a genuine, energetic congratulations Discord DM for a JEE aspirant named {username} who just crossed their daily study goal.

Stats: Studied {hours_today:.1f}h today, goal was {goal_hours:.1f}h.

Rules:
- 2-3 sentences MAX
- Genuine praise, not hollow
- Acknowledge specifically how much they did
- End by telling them they've earned their rest — no more reminders today
- Plain text only"""

    fallback = (
        f"You did it, {username}! {hours_today:.1f}h today — goal hit. "
        f"That's the kind of consistency that builds rank. Rest up, no more reminders from me today."
    )
    return await _call_gemini(prompt, fallback=fallback)


# ============================================================
# 7. PUSH PAST THE LIMIT (sent after congrats)
# ============================================================

async def push_past_limit_msg(
    username: str,
    hours_today: float,
    goal_hours: float,
    hours_left: float,
) -> str:
    """AI-generated message challenging the user to go beyond their daily goal."""
    extra_target = goal_hours + 2.0

    prompt = f"""Write a hype, challenge-style Discord DM for a JEE aspirant named {username} who just hit their {goal_hours:.1f}h daily goal and has {hours_left:.1f}h left in the day.

Goal: Push them to keep going beyond the goal. Top rankers don't stop at the minimum.

Rules:
- 2-3 sentences MAX
- Challenging and motivating, topper energy
- Reference that they have {hours_left:.1f}h left — why stop now?
- Suggest pushing to {extra_target:.0f}h total
- Plain text only, no markdown"""

    fallback = (
        f"Goal hit — but why stop at {goal_hours:.1f}h, {username}? "
        f"You've got {hours_left:.1f}h left today. "
        f"Toppers push to {extra_target:.0f}h+ on good days. One more session."
    )
    return await _call_gemini(prompt, fallback=fallback)


# ============================================================
# 8. PERSONALIZED STUDY REMINDER (general / hourly nag)
# ============================================================

async def personalized_study_reminder(
    username: str,
    hours_today: float,
    goal_hours: float,
    time_str: str,
    peer_name: str = "",
    peer_hours: float = 0.0,
) -> str:
    """Smart study reminder — used for hourly nags, 2 PM check-ins, etc."""
    gap = max(0.0, goal_hours - hours_today)
    peer_ctx = f"{peer_name} has {peer_hours:.1f}h today." if peer_name else ""

    prompt = f"""Write a short, direct study reminder Discord DM for a JEE aspirant named {username}.

Context: It's {time_str} IST. Studied {hours_today:.1f}h today. Goal: {goal_hours:.1f}h. {"Behind by " + str(round(gap, 1)) + "h." if gap > 0 else "GOAL ALREADY HIT — push further."} {peer_ctx}

Rules:
- 2 sentences MAX
- Direct, no filler words
- Reference their actual numbers
- Plain text only"""

    fallback = (
        f"It's {time_str}, {username} — {hours_today:.1f}h done, "
        f"{gap:.1f}h to go. Get back in a study channel."
    )
    return await _call_gemini(prompt, fallback=fallback)
