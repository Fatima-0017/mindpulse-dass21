import time
import pandas as pd
import plotly.express as px
import streamlit as st

from core_engine import (
    DASS_21_ITEMS,
    analyze_hesitation,
    analyze_reflection,
    analyze_response_quality,
    calculate_scores,
    check_live_rushing,
    check_reliable_change,
    get_user_history,
    init_db,
    save_assessment,
    seed_demo_history,
)

# --- PAGE CONFIG & INITIALIZATION ---
st.set_page_config(
    page_title="MindPulse | DASS-21 Wellness Tracker",
    page_icon="🌿",
    layout="centered",
)
init_db()

st.markdown(
    """
    <style>
    .question-card {
        background-color: #FFFFFF;
        padding: 1.75rem;
        border-radius: 12px;
        border: 1px solid #CBD5E1;
        margin-bottom: 1.25rem;
        box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
    }
    .question-text {
        font-size: 1.25rem;
        font-weight: 600;
        color: #0F172A;
        margin: 0;
    }
    .sub-caption {
        font-size: 0.85rem;
        color: #64748B;
        margin-bottom: 0.4rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- SESSION STATE SETUP ---
if "page" not in st.session_state:
    st.session_state.page = "welcome"
if "user_id" not in st.session_state:
    st.session_state.user_id = "demo_user"
if "q_index" not in st.session_state:
    st.session_state.q_index = 0
if "answers" not in st.session_state:
    st.session_state.answers = [None] * 21
if "timings" not in st.session_state:
    st.session_state.timings = [0.0] * 21
if "q_start_time" not in st.session_state:
    st.session_state.q_start_time = time.time()
if "latest_result" not in st.session_state:
    st.session_state.latest_result = None


def reset_quiz(target_page: str = "quiz"):
    st.session_state.q_index = 0
    st.session_state.answers = [None] * 21
    st.session_state.timings = [0.0] * 21
    st.session_state.q_start_time = time.time()
    st.session_state.page = target_page


# --- SCREEN 1: WELCOME & ONBOARDING ---
if st.session_state.page == "welcome":
    st.title("🌿 MindPulse Check-In")
    st.markdown(
        "A smart, private reflection tool powered by the **DASS-21** scale—designed for "
        "**weekly baseline tracking** or **daily check-ins** during high-stress periods."
    )

    st.info(
        "**Note:** This tool is designed for personal wellness tracking and self-reflection. "
        "It does not provide a medical or clinical diagnosis."
    )

    user_input = st.text_input(
        "Enter a nickname or User ID to track your history:",
        value=st.session_state.user_id,
        help="Use 'demo_user' to test with pre-loaded multi-week trend data, or enter your own name.",
    )
    st.session_state.user_id = user_input.strip() or "guest_user"

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Start 21-Item Check-In →", type="primary", use_container_width=True):
            reset_quiz("quiz")
            st.rerun()

    with col2:
        if st.button("📊 View Trend Dashboard", use_container_width=True):
            if st.session_state.user_id.lower() == "demo_user":
                seed_demo_history("demo_user")
            st.session_state.latest_result = None
            st.session_state.page = "results"
            st.rerun()


# --- SCREEN 2: FOCUS-MODE QUIZ (ONE QUESTION AT A TIME) ---
elif st.session_state.page == "quiz":
    idx = st.session_state.q_index
    item = DASS_21_ITEMS[idx]

    # Top bar with progress + End Check-In Anytime button
    top_left, top_right = st.columns([4, 1])
    with top_left:
        st.caption(f"Question {idx + 1} of 21  •  Reflect on how much this applied to you **over the past week**")
    with top_right:
        if st.button("✕ End", help="Exit check-in and return to home without saving", use_container_width=True):
            reset_quiz("welcome")
            st.rerun()

    st.progress((idx + 1) / 21)

    # Mid-quiz gentle pace nudge if rushing detected
    if check_live_rushing(st.session_state.timings, idx):
        st.info(
            "🌿 **Gentle Pace Reminder:** You're moving quite fast through these statements. "
            "Pausing just 3–4 seconds to reflect makes your personal insights much more accurate."
        )

    st.markdown(
        f"""
        <div class="question-card">
            <p class="sub-caption">Statement #{item['id']}</p>
            <p class="question-text">"{item['text']}"</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    options = {
        0: "0 — Did not apply to me at all",
        1: "1 — Applied to me to some degree, or some of the time",
        2: "2 — Applied to me to a considerable degree, or a good part of time",
        3: "3 — Applied to me very much, or most of the time",
    }

    default_choice = st.session_state.answers[idx] if st.session_state.answers[idx] is not None else 0
    selected = st.radio(
        "Select your response:",
        options=list(options.keys()),
        format_func=lambda x: options[x],
        index=default_choice,
        key=f"radio_q_{idx}",
    )

    col_back, col_next = st.columns([1, 2])
    with col_back:
        if idx > 0:
            if st.button("← Previous", use_container_width=True):
                st.session_state.q_index -= 1
                st.session_state.q_start_time = time.time()
                st.rerun()

    with col_next:
        btn_label = "Continue to Reflection →" if idx == 20 else "Next Question →"
        if st.button(btn_label, type="primary", use_container_width=True):
            elapsed = time.time() - st.session_state.q_start_time
            st.session_state.answers[idx] = selected
            st.session_state.timings[idx] += elapsed

            if idx < 20:
                st.session_state.q_index += 1
                st.session_state.q_start_time = time.time()
                st.rerun()
            else:
                st.session_state.page = "reflection"
                st.rerun()


# --- SCREEN 3: OPTIONAL 2-SENTENCE FREE-TEXT REFLECTION ---
elif st.session_state.page == "reflection":
    top_l, top_r = st.columns([4, 1])
    with top_l:
        st.title("📝 Quick Context Note")
    with top_r:
        st.write("")
        if st.button("✕ End", help="Exit check-in without saving", use_container_width=True):
            reset_quiz("welcome")
            st.rerun()

    st.markdown(
        "Numbers only tell part of the story. Add 1–2 sentences about what has been on "
        "your mind (exams, work, sleep, or anything else)—or skip straight to your results."
    )

    reflection_note = st.text_area(
        "Optional reflection:",
        placeholder="e.g., Feeling exhausted from project deadlines and haven't been sleeping well...",
        height=110,
    )

    if st.button("Calculate Results & Insights ✨", type="primary", use_container_width=True):
        prior_history = get_user_history(st.session_state.user_id)
        previous_scores = None
        previous_date = None
        if prior_history:
            last = prior_history[-1]
            previous_scores = {
                "Depression": last["Depression"],
                "Anxiety": last["Anxiety"],
                "Stress": last["Stress"],
            }
            previous_date = last["date"]

        score_data = calculate_scores(st.session_state.answers)
        hesitations = analyze_hesitation(st.session_state.timings, min_seconds=8.0)
        reflection_data = analyze_reflection(reflection_note)
        quality_data = analyze_response_quality(st.session_state.answers, st.session_state.timings)
        rci_data = check_reliable_change(score_data["scores"], previous_scores, previous_date)

        save_assessment(
            user_id=st.session_state.user_id,
            scores=score_data["scores"],
            reflection_note=reflection_note,
            hesitation_items=hesitations,
            source="web",
        )

        st.session_state.latest_result = {
            "score_data": score_data,
            "hesitations": hesitations,
            "reflection_data": reflection_data,
            "quality_data": quality_data,
            "rci_data": rci_data,
        }
        st.session_state.page = "results"
        st.rerun()


# --- SCREEN 4: RESULTS, PARADATA INSIGHTS & LONGITUDINAL TRENDS ---
elif st.session_state.page == "results":
    st.title(f"📊 Wellness Insights — `{st.session_state.user_id}`")

    if st.session_state.latest_result:
        res = st.session_state.latest_result
        score_data = res["score_data"]
        quality_data = res.get("quality_data")

        # Safety Net Banner if Severe or Extremely Severe
        if score_data["crisis_alert"] and score_data["crisis_resources"]:
            crisis = score_data["crisis_resources"]
            helpline_bullets = "\n".join([f"- **{h}**" for h in crisis["helplines"]])
            st.error(f"### 🤍 Support Is Available\n{crisis['message']}\n\n{helpline_bullets}")

        # Reflection Quality / Validity Callout
        if quality_data:
            if quality_data["is_valid"]:
                st.success(
                    f"🧭 **{quality_data['confidence_label']}** • Completed in {quality_data['total_seconds']}s "
                    f"with consistent, thoughtful pacing."
                )
            else:
                flag_bullets = "\n".join([f"- {f}" for f in quality_data["flags"]])
                st.warning(
                    f"⚠️ **{quality_data['confidence_label']}**\n\n{flag_bullets}\n\n"
                    "Your scores are still shown below, or you can retake the check-in at a slower pace."
                )
                if st.button("🔄 Retake Check-In at a Slower Pace"):
                    reset_quiz("quiz")
                    st.rerun()

        # Three Subscale Score Cards
        st.subheader("Current Subscale Scores (0–42 Scale)")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(
                label="Depression",
                value=f"{score_data['scores']['Depression']} / 42",
                delta=score_data["severities"]["Depression"],
                delta_color="off",
            )
        with c2:
            st.metric(
                label="Anxiety",
                value=f"{score_data['scores']['Anxiety']} / 42",
                delta=score_data["severities"]["Anxiety"],
                delta_color="off",
            )
        with c3:
            st.metric(
                label="Stress",
                value=f"{score_data['scores']['Stress']} / 42",
                delta=score_data["severities"]["Stress"],
                delta_color="off",
            )

        # Subscale-Matched Actionable Advice
        st.info(f"**Tailored Focus ({score_data['primary_focus']}):** {score_data['recommended_tip']}")

        # Adaptive Daily / Weekly Change Comparison
        rci_data = res.get("rci_data")
        if isinstance(rci_data, dict):
            st.subheader(f"🔄 {rci_data['cadence_label']}")
            for note in rci_data["notes"]:
                st.write(note)
        elif res.get("rci_notes"):
            st.subheader("🔄 Check-In Comparison")
            for note in res["rci_notes"]:
                st.write(note)

        # Paradata (Hesitation) + NLP Reflection Themes
        st.subheader("🔍 Deeper Reflection Signals")
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("**Items You Paused Longest On**")
            if res["hesitations"]:
                for h in res["hesitations"]:
                    st.write(f"- **Q{h['id']} ({h['seconds']}s):** *\"{h['text']}\"*")
            else:
                st.caption("You answered all items at a steady pace (no extended pauses detected).")

        with col_right:
            st.markdown("**Reflection Note Themes**")
            ref = res["reflection_data"]
            if ref["has_note"]:
                st.write("**Detected Themes:** " + ", ".join(ref["themes"]))
                if ref["matched_keywords"]:
                    st.caption("Keywords spotted: " + ", ".join(ref["matched_keywords"]))
            else:
                st.caption("No free-text reflection note was added for this session.")

        st.divider()

    # Longitudinal Trend Chart
    # Longitudinal Trend Chart
    st.subheader("📈 Daily & Weekly Trajectory")

    if "demo_feedback" in st.session_state and st.session_state.demo_feedback:
        st.success(st.session_state.demo_feedback)
        st.session_state.demo_feedback = None

    history = get_user_history(st.session_state.user_id)

    if len(history) >= 2:
        df = pd.DataFrame(history)
        df_melted = df.melt(
            id_vars=["date"],
            value_vars=["Depression", "Anxiety", "Stress"],
            var_name="Subscale",
            value_name="Score",
        )
        fig = px.line(
            df_melted,
            x="date",
            y="Score",
            color="Subscale",
            markers=True,
            color_discrete_map={
                "Depression": "#2A6F7B",
                "Anxiety": "#D97706",
                "Stress": "#DC2626",
            },
        )
        fig.update_layout(
            yaxis_range=[0, 42],
            xaxis_title="Check-In Timestamp",
            yaxis_title="DASS-21 Score (Multiplied)",
            legend_title="",
            margin=dict(l=10, r=10, t=20, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)
    elif len(history) == 1:
        st.caption("1 check-in recorded so far. Complete a second check-in (or click 'Seed 4-Week Demo Data' below) to view your trend line.")
    else:
        st.caption("No check-in history found for this User ID yet.")

    # Bottom Navigation & Demo Seeder
    nav1, nav2, nav3 = st.columns(3)
    with nav1:
        if st.button("Take New Check-In", type="primary", use_container_width=True):
            reset_quiz("quiz")
            st.rerun()
    with nav2:
        if st.button("Seed 4-Week Demo Data", use_container_width=True):
            added = seed_demo_history(st.session_state.user_id)
            if added:
                st.session_state.demo_feedback = "📈 Added 4 prior weeks of sample history (-28d, -21d, -14d, -7d) to your chart!"
            else:
                st.session_state.demo_feedback = "ℹ️ Multi-week sample history is already loaded for this user."
            st.rerun()
    with nav3:
        if st.button("← Change User", use_container_width=True):
            st.session_state.page = "welcome"
            st.rerun()