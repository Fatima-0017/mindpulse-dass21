import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional

DB_PATH = "dass_data.db"

# Official DASS-21 Items & Subscale Mapping (D = Depression, A = Anxiety, S = Stress)
DASS_21_ITEMS = [
    {"id": 1, "subscale": "S", "text": "I found it hard to wind down"},
    {"id": 2, "subscale": "A", "text": "I was aware of dryness of my mouth"},
    {"id": 3, "subscale": "D", "text": "I couldn't seem to experience any positive feeling at all"},
    {"id": 4, "subscale": "A", "text": "I experienced breathing difficulty (e.g., excessively rapid breathing, breathlessness in the absence of physical exertion)"},
    {"id": 5, "subscale": "D", "text": "I found it difficult to work up the initiative to do things"},
    {"id": 6, "subscale": "S", "text": "I tended to over-react to situations"},
    {"id": 7, "subscale": "A", "text": "I experienced trembling (e.g., in the hands)"},
    {"id": 8, "subscale": "S", "text": "I felt that I was using a lot of nervous energy"},
    {"id": 9, "subscale": "A", "text": "I was worried about situations in which I might panic and make a fool of myself"},
    {"id": 10, "subscale": "D", "text": "I felt that I had nothing to look forward to"},
    {"id": 11, "subscale": "S", "text": "I found myself getting agitated"},
    {"id": 12, "subscale": "S", "text": "I found it difficult to relax"},
    {"id": 13, "subscale": "D", "text": "I felt down-hearted and blue"},
    {"id": 14, "subscale": "S", "text": "I was intolerant of anything that kept me from getting on with what I was doing"},
    {"id": 15, "subscale": "A", "text": "I felt I was close to panic"},
    {"id": 16, "subscale": "D", "text": "I was unable to become enthusiastic about anything"},
    {"id": 17, "subscale": "D", "text": "I felt I wasn't worth much as a person"},
    {"id": 18, "subscale": "S", "text": "I felt that I was rather touchy"},
    {"id": 19, "subscale": "A", "text": "I was aware of the action of my heart in the absence of physical exertion (e.g., sense of heart rate increase, heart missing a beat)"},
    {"id": 20, "subscale": "A", "text": "I felt scared without any good reason"},
    {"id": 21, "subscale": "D", "text": "I felt that life was meaningless"},
]

SUBSCALE_TIPS = {
    "Depression": (
        "Low mood and low energy respond best to small, low-friction wins rather than big goals. "
        "Try stepping outside for 5 minutes of daylight, drinking a glass of water, or completing one tiny 2-minute task."
    ),
    "Anxiety": (
        "Physical tension and racing thoughts benefit from grounding your nervous system first. "
        "Try physiological sighing (two quick inhales through the nose, one long slow exhale through the mouth) for 60 seconds."
    ),
    "Stress": (
        "Chronic overload comes from carrying too many open loops at once. "
        "Write down the top 3 things demanding your attention today, pick only one to tackle first, and give yourself a 10-minute screen-free break."
    ),
    "Balanced": (
        "Your scores are currently in the normal range across all three areas. "
        "Keep protecting your sleep schedule and checking in regularly to spot early shifts before they build up."
    ),
}

CRISIS_RESOURCES = {
    "message": (
        "Your responses indicate severe distress. This tool tracks wellness patterns and is not a medical diagnosis—"
        "please consider reaching out to a mental health professional or a confidential support line today."
    ),
    "helplines": [
        "Umang Pakistan (24/7 Mental Health Helpline): 0311-7786264",
        "Rozan Counseling Helpline: 0800-22444 / 0304-111-1741",
        "International Resources: findahelpline.com",
    ],
}


def get_severity(subscale: str, score: int) -> str:
    """Returns official DASS-21 severity label (using multiplied 0-42 scores)."""
    if subscale == "Depression":
        if score <= 9:
            return "Normal"
        elif score <= 13:
            return "Mild"
        elif score <= 20:
            return "Moderate"
        elif score <= 27:
            return "Severe"
        return "Extremely Severe"

    elif subscale == "Anxiety":
        if score <= 7:
            return "Normal"
        elif score <= 9:
            return "Mild"
        elif score <= 14:
            return "Moderate"
        elif score <= 19:
            return "Severe"
        return "Extremely Severe"

    elif subscale == "Stress":
        if score <= 14:
            return "Normal"
        elif score <= 18:
            return "Mild"
        elif score <= 25:
            return "Moderate"
        elif score <= 33:
            return "Severe"
        return "Extremely Severe"

    return "Unknown"


def calculate_scores(answers: List[int]) -> Dict:
    """
    Takes 21 responses (each 0-3), calculates multiplied D/A/S totals,
    assigns severity labels, selects tailored advice, and checks crisis thresholds.
    """
    if len(answers) != 21:
        raise ValueError(f"Expected 21 answers, got {len(answers)}.")

    raw_totals = {"D": 0, "A": 0, "S": 0}
    for item, val in zip(DASS_21_ITEMS, answers):
        raw_totals[item["subscale"]] += int(val)

    scores = {
        "Depression": raw_totals["D"] * 2,
        "Anxiety": raw_totals["A"] * 2,
        "Stress": raw_totals["S"] * 2,
    }

    severities = {sub: get_severity(sub, val) for sub, val in scores.items()}

    severity_rank = {"Normal": 0, "Mild": 1, "Moderate": 2, "Severe": 3, "Extremely Severe": 4}
    highest_sub = max(
        scores.keys(),
        key=lambda k: (severity_rank[severities[k]], scores[k])
    )

    primary_focus = "Balanced" if severity_rank[severities[highest_sub]] == 0 else highest_sub

    crisis_alert = any(
        severities[sub] in ("Severe", "Extremely Severe") for sub in scores
    )

    return {
        "scores": scores,
        "severities": severities,
        "primary_focus": primary_focus,
        "recommended_tip": SUBSCALE_TIPS[primary_focus],
        "crisis_alert": crisis_alert,
        "crisis_resources": CRISIS_RESOURCES if crisis_alert else None,
    }


def check_live_rushing(timings: List[float], current_idx: int, min_sec: float = 1.2) -> bool:
    """
    Mid-quiz check: returns True if the user clicked through the last 5 items
    faster than human reading speed (< 1.2s each).
    """
    if current_idx < 5:
        return False
    recent = timings[current_idx - 5 : current_idx]
    return len(recent) == 5 and all(0 < t < min_sec for t in recent)


def analyze_response_quality(answers: List[int], timings: List[float]) -> Dict:
    """
    Evaluates Insufficient Effort Responding (IER) across 4 psychometric signals:
    1. Impossible reading speed (< 35s total or 5+ consecutive clicks < 1.2s)
    2. Straightlining (7+ identical non-zero responses in a row, or rushed all-zeros)
    3. Repeating zig-zag click patterns (e.g., 1-2-1-2-1-2 or 0-1-2-3-0-1-2-3)
    4. Semantic twin inconsistency across closely related DASS-21 pairs
    """
    clean_answers = [int(a if a is not None else 0) for a in answers]
    total_seconds = round(sum(timings), 1)
    flags = []

    fast_streak = 0
    max_fast_streak = 0
    for t in timings:
        if 0 < t < 1.2:
            fast_streak += 1
            max_fast_streak = max(max_fast_streak, fast_streak)
        else:
            fast_streak = 0

    if total_seconds < 35.0 or max_fast_streak >= 5:
        flags.append(
            f"Rapid completion pace ({total_seconds}s total) — some statements may have been skipped without full reading."
        )

    same_streak = 1
    max_nonzero_streak = 0
    for i in range(1, len(clean_answers)):
        if clean_answers[i] == clean_answers[i - 1]:
            same_streak += 1
            if clean_answers[i] != 0:
                max_nonzero_streak = max(max_nonzero_streak, same_streak)
        else:
            same_streak = 1

    if max_nonzero_streak >= 7:
        flags.append(
            f"Repeated identical option ({max_nonzero_streak} times in a row) — check whether each statement was evaluated individually."
        )
    elif all(a == 0 for a in clean_answers) and total_seconds < 35.0:
        flags.append(
            "All items were marked '0' at a very rapid pace — consider retaking slowly if you didn't read each statement."
        )

    has_cycle = False
    for i in range(len(clean_answers) - 5):
        w = clean_answers[i : i + 6]
        if w[0] == w[2] == w[4] and w[1] == w[3] == w[5] and w[0] != w[1]:
            has_cycle = True
            break
    if not has_cycle:
        for i in range(len(clean_answers) - 7):
            w = clean_answers[i : i + 8]
            if w[:4] == w[4:] and len(set(w[:4])) > 1:
                has_cycle = True
                break

    if has_cycle:
        flags.append(
            "Repeating rhythmic selection pattern detected across consecutive questions."
        )

    twin_pairs = [(0, 11), (2, 15), (10, 17)]
    severe_mismatches = sum(
        1 for i, j in twin_pairs if abs(clean_answers[i] - clean_answers[j]) >= 3
    )
    if severe_mismatches >= 2:
        flags.append(
            "Opposite answers (0 vs. 3) appeared across closely related statements — responses may reflect inconsistent reading."
        )

    if len(flags) == 0:
        confidence = "High Reflection Depth"
    elif len(flags) == 1:
        confidence = "Moderate Reflection Confidence"
    else:
        confidence = "Low Reflection Confidence (Rushed / Pattern Detected)"

    return {
        "is_valid": len(flags) == 0,
        "confidence_label": confidence,
        "flags": flags,
        "total_seconds": total_seconds,
    }


def analyze_hesitation(timings: List[float], min_seconds: float = 8.0) -> List[Dict]:
    """Identifies up to 2 questions where the user paused significantly longer than usual."""
    if len(timings) != 21:
        return []

    paired = []
    for item, sec in zip(DASS_21_ITEMS, timings):
        if sec >= min_seconds:
            paired.append({
                "id": item["id"],
                "subscale": item["subscale"],
                "text": item["text"],
                "seconds": round(sec, 1),
            })

    paired.sort(key=lambda x: x["seconds"], reverse=True)
    return paired[:2]


def analyze_reflection(note_text: str) -> Dict:
    """Lightweight keyword/theme scanner for the optional 2-sentence reflection box."""
    if not note_text or not note_text.strip():
        return {"has_note": False, "themes": [], "matched_keywords": []}

    text_lower = note_text.lower()
    theme_lexicon = {
        "Sleep & Exhaustion": ["sleep", "insomnia", "tired", "exhausted", "fatigue", "awake", "burnout", "burned out"],
        "Worry & Panic": ["panic", "anxious", "worried", "overthinking", "heart", "scared", "nervous", "fear"],
        "Work & Academic Pressure": ["exam", "deadline", "work", "study", "pressure", "overwhelmed", "busy", "fail"],
        "Low Mood & Isolation": ["lonely", "alone", "hopeless", "sad", "empty", "pointless", "cry", "unmotivated"],
        "Positive & Grounded": ["better", "calm", "grateful", "good", "improving", "relaxed", "hopeful", "happy"],
    }

    detected_themes = []
    matched_words = []

    for theme, keywords in theme_lexicon.items():
        hits = [kw for kw in keywords if kw in text_lower]
        if hits:
            detected_themes.append(theme)
            matched_words.extend(hits)

    return {
        "has_note": True,
        "themes": detected_themes if detected_themes else ["General Reflection"],
        "matched_keywords": list(set(matched_words)),
    }


def check_reliable_change(
    current_scores: Dict[str, int],
    previous_scores: Optional[Dict[str, int]],
    previous_date: Optional[str] = None,
) -> Dict:
    """
    Adapts comparison framing to the actual check-in cadence (same-day, daily, or weekly)
    and evaluates Reliable Change Index (RCI >= 4 points on DASS-21 subscales).
    """
    if not previous_scores:
        return {
            "cadence_label": "Baseline Session",
            "notes": ["Baseline recorded. Check in daily during high-stress periods or weekly for long-term tracking."],
        }

    cadence_label = "Check-In Comparison"
    time_phrase = "since your last check-in"

    if previous_date:
        try:
            prev_dt = datetime.strptime(previous_date, "%Y-%m-%d %H:%M")
            delta = datetime.now() - prev_dt
            days = delta.days
            if days == 0:
                cadence_label = "Same-Day Check-In Comparison"
                time_phrase = "since your earlier check-in today (reflecting short-term mood shifts)"
            elif days == 1:
                cadence_label = "Daily Check-In Comparison"
                time_phrase = "since yesterday"
            elif days < 7:
                cadence_label = f"Multi-Day Comparison ({days} Days)"
                time_phrase = f"over the past {days} days"
            else:
                weeks = max(1, round(days / 7))
                cadence_label = f"Week-over-Week Change ({weeks}w)"
                time_phrase = f"over the past {days} days"
        except ValueError:
            pass

    insights = []
    for sub in ["Depression", "Anxiety", "Stress"]:
        diff = current_scores[sub] - previous_scores[sub]
        if diff >= 4:
            insights.append(f"⚠️ **{sub}** increased by **+{diff} points** {time_phrase} (meaningful upward shift).")
        elif diff <= -4:
            insights.append(f"✅ **{sub}** dropped by **{abs(diff)} points** {time_phrase} (meaningful improvement).")

    if not insights:
        insights.append(f"Your scores are steady (within ±3 points {time_phrase}).")

    return {
        "cadence_label": cadence_label,
        "notes": insights,
    }


# --- SQLITE DATABASE MEMORY (API-READY SCHEMA) ---

def init_db(db_path: str = DB_PATH) -> None:
    """Creates the SQLite database and sessions table if they don't exist yet."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            source TEXT DEFAULT 'web',
            created_at TEXT NOT NULL,
            depression INTEGER NOT NULL,
            anxiety INTEGER NOT NULL,
            stress INTEGER NOT NULL,
            reflection_note TEXT,
            hesitation_json TEXT
        )
    """)
    conn.commit()
    conn.close()


def save_assessment(
    user_id: str,
    scores: Dict[str, int],
    reflection_note: str = "",
    hesitation_items: Optional[List[Dict]] = None,
    source: str = "web",
    created_at: Optional[str] = None,
    db_path: str = DB_PATH,
) -> None:
    """Saves a completed assessment to SQLite."""
    init_db(db_path)
    timestamp = created_at or datetime.now().strftime("%Y-%m-%d %H:%M")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO assessments (user_id, source, created_at, depression, anxiety, stress, reflection_note, hesitation_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id.strip().lower(),
            source,
            timestamp,
            scores["Depression"],
            scores["Anxiety"],
            scores["Stress"],
            reflection_note,
            json.dumps(hesitation_items or []),
        ),
    )
    conn.commit()
    conn.close()


def get_user_history(user_id: str, db_path: str = DB_PATH) -> List[Dict]:
    """Fetches all past assessments for a user ordered chronologically."""
    init_db(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT created_at, depression, anxiety, stress, reflection_note, hesitation_json, source
        FROM assessments
        WHERE user_id = ?
        ORDER BY created_at ASC
        """,
        (user_id.strip().lower(),),
    )
    rows = cur.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append({
            "date": row[0],
            "Depression": row[1],
            "Anxiety": row[2],
            "Stress": row[3],
            "reflection_note": row[4],
            "hesitations": json.loads(row[5]) if row[5] else [],
            "source": row[6],
        })
    return history


def seed_demo_history(user_id: str = "demo_user", db_path: str = DB_PATH) -> bool:
    """
    Backfills 4 prior weekly check-ins (-28d, -21d, -14d, -7d) whenever the user
    doesn't already have multi-week history—even if they ran multiple tests today.
    """
    existing = get_user_history(user_id, db_path)
    cutoff = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d %H:%M")
    if any(row["date"] <= cutoff for row in existing):
        return False

    now = datetime.now()
    sample_weeks = [
        {"days_ago": 28, "scores": {"Depression": 16, "Anxiety": 14, "Stress": 24}, "note": "Midterm deadlines piling up and not sleeping well."},
        {"days_ago": 21, "scores": {"Depression": 18, "Anxiety": 16, "Stress": 26}, "note": "Feeling burned out and overwhelmed with exams."},
        {"days_ago": 14, "scores": {"Depression": 12, "Anxiety": 10, "Stress": 18}, "note": "Finished exams, catching up on sleep."},
        {"days_ago": 7,  "scores": {"Depression": 8,  "Anxiety": 6,  "Stress": 12}, "note": "Feeling much calmer and more hopeful this week."},
    ]
    for entry in sample_weeks:
        dt = (now - timedelta(days=entry["days_ago"])).strftime("%Y-%m-%d %H:%M")
        save_assessment(
            user_id=user_id,
            scores=entry["scores"],
            reflection_note=entry["note"],
            created_at=dt,
            db_path=db_path,
        )
    return True