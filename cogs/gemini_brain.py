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
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite"
]

_current_key_idx = 0
_cached_models: dict[tuple[str, str], object] = {}   # (key, model_name) -> GenerativeModel instance
_rotation_lock = asyncio.Lock()
_init_lock = asyncio.Lock()  # Serialize model init

async def _get_model_instance(key: str, model_name: str):
    """Returns the Gemini model instance for a key, initializing if needed."""
    cache_key = (key, model_name)
    if cache_key not in _cached_models:
        async with _init_lock:
            if cache_key in _cached_models:
                return _cached_models[cache_key]
            try:
                from google.generativeai import client as genai_client
                genai.configure(api_key=key)
                model = genai.GenerativeModel(model_name)
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

async def _call_gemini(prompt: str, fallback: str, timeout: float = 18.0, model_preference: list = None, max_output_tokens: int = 1024) -> str:
    """Calls Gemini API with rotation, fallback, and max output tokens."""
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

        for model_name in pref:
            model = await _get_model_instance(key, model_name)
            if model is None:
                continue

            try:
                loop = asyncio.get_running_loop()
                gen_config = {"max_output_tokens": max_output_tokens, "temperature": 0.7}
                response = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda m=model: m.generate_content(prompt, generation_config=gen_config)),
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
                if "api_key" in err_str or "invalid" in err_str or "403" in err_str or "blocked" in err_str:
                    logging.error(f"[GEMINI] Key #{key_idx + 1} is invalid/forbidden/blocked — moving to next key. Error: {e}")
                    break
                else:
                    logging.warning(f"[GEMINI] Key #{key_idx + 1} failed with '{model_name}': {e} — trying next model")

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
     "explanation": "The component of gravity along the incline is g sin(θ). Since θ = 30° and sin(30°) = 0.5, acceleration = g sin(30°) = g/2."}
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
        
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return raw.strip()

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
        pref = ["gemini-3.5-flash", "gemini-2.5-flash"]
        tokens = 3072
    elif topic == "logic":
        challenge_desc = "a tricky logic puzzle or lateral thinking brain teaser — no equations needed. Keep the question, options, and explanation extremely brief and concise (under 80 words total). Do not write long introductions. Save tokens."
        pref = ["gemini-2.5-flash-lite", "gemini-3.5-flash", "gemini-2.5-flash"]
        tokens = 512
    else:
        topic_map = {
            "jee":   "a JEE-level Physics, Chemistry, or Mathematics MCQ (not trivial — something that requires actual thinking)",
            "mixed": "either a JEE-level MCQ or a logic puzzle — whichever would make the more interesting challenge today",
        }
        topic_desc = topic_map.get(topic, topic_map["mixed"])
        challenge_desc = f"{topic_desc} suitable for Indian JEE aspirants (age 16-18), solvable in under 2 minutes. Keep the explanation reasonable and precise."
        pref = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]
        tokens = 1536

    for attempt in range(3):
        logging.info(f"[PUZZLE PIPELINE] Starting attempt {attempt + 1}/3... Weekly={is_weekly}")

        # Stage 1: Initial Draft
        draft_prompt = f"""You are the Brainstormer. Generate a draft of {challenge_desc}.
It must have 4 options (A, B, C, D) and only one correct option.
Output the puzzle draft including the question, the options, the correct answer, and your initial explanation.
Provide it in clear text."""
        draft = await _call_gemini(draft_prompt, fallback="", timeout=20.0, model_preference=pref, max_output_tokens=tokens)
        if not draft:
            logging.warning("[PUZZLE PIPELINE] Failed to get draft.")
            continue

        # Cycle 1: Critique & Refine
        critique_prompt_1 = f"""You are the Refiner. Critique the following puzzle draft for clarity, ambiguity, difficulty, and accuracy.
Identify any logical loopholes or trickiness that is too unfair, and make sure the options are completely distinct and correct.
Draft:
{draft}

Provide constructive critique and suggestions for improvement."""
        critique_1 = await _call_gemini(critique_prompt_1, fallback="", timeout=20.0, model_preference=pref, max_output_tokens=tokens)
        if not critique_1:
            logging.warning("[PUZZLE PIPELINE] Failed to get critique 1.")
            continue

        refine_prompt_1 = f"""You are the Brainstormer. Revise the puzzle draft using the feedback provided.
Original Draft:
{draft}

Feedback:
{critique_1}

Output the revised puzzle draft clearly."""
        revision_1 = await _call_gemini(refine_prompt_1, fallback="", timeout=20.0, model_preference=pref, max_output_tokens=tokens)
        if not revision_1:
            logging.warning("[PUZZLE PIPELINE] Failed to get revision 1.")
            continue

        # Cycle 2: Critique & Refine
        critique_prompt_2 = f"""You are the Refiner. Analyze this revised puzzle draft.
Is there any ambiguity left? Are the question and answer choices mathematically/logically sound?
Revised Draft:
{revision_1}

Provide further feedback or final suggestions to polish it."""
        critique_2 = await _call_gemini(critique_prompt_2, fallback="", timeout=20.0, model_preference=pref, max_output_tokens=tokens)
        if not critique_2:
            logging.warning("[PUZZLE PIPELINE] Failed to get critique 2.")
            continue

        refine_prompt_2 = f"""You are the Brainstormer. Take the second round of feedback and refine the puzzle further.
Current Draft:
{revision_1}

Feedback:
{critique_2}

Output the updated puzzle clearly."""
        revision_2 = await _call_gemini(refine_prompt_2, fallback="", timeout=20.0, model_preference=pref, max_output_tokens=tokens)
        if not revision_2:
            logging.warning("[PUZZLE PIPELINE] Failed to get revision 2.")
            continue

        # Cycle 3: Critique & Final JSON
        critique_prompt_3 = f"""You are the Refiner. Perform a final check on this revised draft.
Are the question, options, correct answer, and explanation 100% correct and ready?
Revised Draft:
{revision_2}

Provide final polish feedback or state if it is ready."""
        critique_3 = await _call_gemini(critique_prompt_3, fallback="", timeout=20.0, model_preference=pref, max_output_tokens=tokens)
        if not critique_3:
            logging.warning("[PUZZLE PIPELINE] Failed to get critique 3.")
            continue

        final_prompt = f"""You are the Brainstormer. Produce the final puzzle based on all feedback.
Ensure it is free of all ambiguities. You must format the final output as a single valid JSON object.

Final Draft:
{revision_2}

Feedback:
{critique_3}

Respond ONLY with a JSON object in this format (no markdown, no extra text):
{{
  "question": "...",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "answer": "A/B/C/D",
  "explanation": "..."
}}"""
        final_json_raw = await _call_gemini(final_prompt, fallback="", timeout=25.0, model_preference=pref, max_output_tokens=tokens)
        if not final_json_raw:
            logging.warning("[PUZZLE PIPELINE] Failed to get final JSON.")
            continue

        try:
            candidate = json.loads(_clean_json_response(final_json_raw))
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
        raw_solve_1 = await _call_gemini(solver_prompt, fallback="", timeout=20.0, model_preference=pref, max_output_tokens=tokens)
        if not raw_solve_1:
            logging.warning("[PUZZLE PIPELINE] Solver 1 failed to respond.")
            continue

        try:
            solve_1 = json.loads(_clean_json_response(raw_solve_1))
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
        raw_solve_2 = await _call_gemini(solver_prompt_2, fallback="", timeout=20.0, model_preference=pref, max_output_tokens=tokens)
        if not raw_solve_2:
            logging.warning("[PUZZLE PIPELINE] Solver 2 failed to respond.")
            continue

        try:
            solve_2 = json.loads(_clean_json_response(raw_solve_2))
            ans_2 = solve_2.get("solved_answer", "").strip().upper()
            if ans_2 != candidate["answer"]:
                logging.warning(f"[PUZZLE PIPELINE] Solver 2 disagreed! Intended: {candidate['answer']}, Solved: {ans_2}")
                continue
        except Exception as e:
            logging.warning(f"[PUZZLE PIPELINE] Solver 2 parsing failed: {e}")
            continue

        logging.info(f"[PUZZLE PIPELINE] Puzzle successfully verified twice! Topic: {topic}, Weekly: {is_weekly}")
        return candidate

    logging.warning("[PUZZLE PIPELINE] All attempts failed to verify. Using static fallback.")
    if is_weekly:
        return random.choice(_FALLBACK_WEEKLY_PUZZLES)
    else:
        return random.choice(_FALLBACK_PUZZLES)

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

    fallback = (
        f"{username}, you missed the puzzle and barely showed up today. "
        f"This server exists for serious JEE aspirants, and right now you're not acting like one. "
        f"Your {hours_alltime:.0f} hours all-time should mean more than this. "
        f"Use /verify to rejoin — solve 3 puzzles and prove you belong here."
    )
    return await _call_gemini(prompt, fallback=fallback, max_output_tokens=256)

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

    fallback = (
        f"It's 6 AM, {username}. "
        f"{'Yesterday was ' + str(round(yesterday_hours, 1)) + 'h — build on it today.' if yesterday_hours > 0 else 'Yesterday was a zero. Today is your redemption.'} "
        f"Open your notes and get in a study VC now."
    )
    return await _call_gemini(prompt, fallback=fallback, max_output_tokens=256)

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

    fallback = (
        f"Good start with {hours_today:.1f}h, {username}! "
        f"You're only {gap:.1f}h away from your daily goal — don't let today's effort go to waste. "
        f"Get back in a study channel and finish what you started."
    )
    return await _call_gemini(prompt, fallback=fallback, max_output_tokens=256)

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

    fallback = (
        f"{username}, it's {time_str} and you have 0 hours studied today. "
        f"{'Your partner ' + peer_name + ' already has ' + str(round(peer_hours, 1)) + 'h. ' if peer_name else ''}"
        f"Get in a study channel right now — {hours_left:.1f}h left in the day."
    )
    return await _call_gemini(prompt, fallback=fallback, max_output_tokens=256)

async def goal_congrats_msg(username: str, hours_today: float, goal_hours: float) -> str:
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
    return await _call_gemini(prompt, fallback=fallback, max_output_tokens=256)

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

    fallback = (
        f"Goal hit — but why stop at {goal_hours:.1f}h, {username}? "
        f"You've got {hours_left:.1f}h left today. "
        f"Toppers push to {extra_target:.0f}h+ on good days. One more session."
    )
    return await _call_gemini(prompt, fallback=fallback, max_output_tokens=256)

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

    fallback = (
        f"It's {time_str}, {username} — {hours_today:.1f}h done, "
        f"{gap:.1f}h to go. Get back in a study channel."
    )
    return await _call_gemini(prompt, fallback=fallback, max_output_tokens=256)


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


