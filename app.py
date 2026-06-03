import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import time

st.set_page_config(page_title="Suivi tir sportif", page_icon="🎯", layout="wide")

# -------------------------
# Helpers
# -------------------------

def init_state():
    defaults = {
        "events": [],
        "current_block": 1,
        "current_series": 1,
        "phase": "idle",  # idle, rest, aim
        "phase_start": None,
        "last_rest_seconds": 0,
        "session_started": False,
        "shooter": "",
        "competition": "",
        "session_date": datetime.today().date(),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def elapsed_seconds():
    if st.session_state.phase_start is None:
        return 0
    return int(time.time() - st.session_state.phase_start)


def score_value(result: str) -> int:
    if result in ["X", "10"]:
        return 10
    return int(result)


def current_series_score():
    return sum(
        e["Score"]
        for e in st.session_state.events
        if e["Bloc"] == st.session_state.current_block
        and e["Série"] == st.session_state.current_series
        and e["Type"] == "Tir validé"
    )


def current_series_shots():
    return sum(
        1
        for e in st.session_state.events
        if e["Bloc"] == st.session_state.current_block
        and e["Série"] == st.session_state.current_series
        and e["Type"] == "Tir validé"
    )


def add_event(event_type, result="", rest_seconds=0, aim_seconds=0, score=0):
    st.session_state.events.append({
        "Date": str(st.session_state.session_date),
        "Tireur": st.session_state.shooter,
        "Compétition": st.session_state.competition,
        "Bloc": st.session_state.current_block,
        "Série": st.session_state.current_series,
        "N° action": len(st.session_state.events) + 1,
        "Type": event_type,
        "Résultat": result,
        "Temps repos (s)": rest_seconds,
        "Temps visée/tir (s)": aim_seconds,
        "Score": score,
        "Horodatage": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


def go_next_series():
    if st.session_state.current_series < 6:
        st.session_state.current_series += 1
        st.session_state.current_block = ((st.session_state.current_series - 1) // 2) + 1
    st.session_state.phase = "idle"
    st.session_state.phase_start = None
    st.session_state.last_rest_seconds = 0


def make_excel():
    detail = pd.DataFrame(st.session_state.events)

    summary_rows = []
    total_general = 0
    for s in range(1, 7):
        b = ((s - 1) // 2) + 1
        score = int(detail[(detail["Série"] == s) & (detail["Type"] == "Tir validé")]["Score"].sum()) if not detail.empty else 0
        shots = int(len(detail[(detail["Série"] == s) & (detail["Type"] == "Tir validé")])) if not detail.empty else 0
        rests_from_aim = int(len(detail[(detail["Série"] == s) & (detail["Type"] == "Visée reposée")])) if not detail.empty else 0
        total_general += score
        summary_rows.append({
            "Bloc": b,
            "Série": s,
            "Nb tirs validés": shots,
            "Nb visées reposées": rests_from_aim,
            "Score série": score,
        })

    summary = pd.DataFrame(summary_rows)
    block_summary = summary.groupby("Bloc", as_index=False).agg({"Score série": "sum"})
    block_summary = block_summary.rename(columns={"Score série": "Total bloc /200"})
    general = pd.DataFrame([{"Total général /600": total_general}])

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        detail.to_excel(writer, index=False, sheet_name="Données détaillées")
        summary.to_excel(writer, index=False, sheet_name="Résumé séries")
        block_summary.to_excel(writer, index=False, sheet_name="Résumé blocs")
        general.to_excel(writer, index=False, sheet_name="Total")
    output.seek(0)
    return output


init_state()

st.title("🎯 Suivi de match - Tir sportif")
st.caption("Premier jet : chrono repos, chrono visée/tir, tir validé ou visée reposée, puis export Excel.")

# -------------------------
# Session info
# -------------------------
with st.sidebar:
    st.header("Session")
    st.session_state.shooter = st.text_input("Nom du tireur / de la tireuse", value=st.session_state.shooter)
    st.session_state.competition = st.text_input("Compétition", value=st.session_state.competition)
    st.session_state.session_date = st.date_input("Date", value=st.session_state.session_date)

    st.divider()
    if st.button("🔄 Réinitialiser toute la session", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# -------------------------
# Main status
# -------------------------
col_a, col_b, col_c, col_d = st.columns(4)
col_a.metric("Bloc", st.session_state.current_block)
col_b.metric("Série", f"{st.session_state.current_series}/6")
col_c.metric("Tirs validés", f"{current_series_shots()}/10")
col_d.metric("Score série", f"{current_series_score()}/100")

phase_label = {
    "idle": "En attente",
    "rest": "Repos en cours",
    "aim": "Visée / tir en cours",
}[st.session_state.phase]

st.subheader(f"État : {phase_label}")
if st.session_state.phase in ["rest", "aim"]:
    st.info(f"Chrono actuel : {elapsed_seconds()} secondes")

# Auto refresh while timer runs
if st.session_state.phase in ["rest", "aim"]:
    time.sleep(1)
    st.rerun()

# -------------------------
# Action buttons
# -------------------------
st.divider()

if st.session_state.phase == "idle":
    if st.button("▶️ Démarrer repos", type="primary", use_container_width=True):
        st.session_state.phase = "rest"
        st.session_state.phase_start = time.time()
        st.rerun()

elif st.session_state.phase == "rest":
    if st.button("🎯 Fin repos / Démarrer visée", type="primary", use_container_width=True):
        st.session_state.last_rest_seconds = elapsed_seconds()
        st.session_state.phase = "aim"
        st.session_state.phase_start = time.time()
        st.rerun()

elif st.session_state.phase == "aim":
    st.write("Quand la personne tire, clique sur le résultat. Si elle lève, vise, puis décide de reposer sans tirer, clique sur **Visée reposée**.")

    result_cols = st.columns(7)
    results = ["X", "10", "9", "8", "7", "6", "5"]
    for col, result in zip(result_cols, results):
        if col.button(result, use_container_width=True):
            aim = elapsed_seconds()
            add_event(
                event_type="Tir validé",
                result=result,
                rest_seconds=st.session_state.last_rest_seconds,
                aim_seconds=aim,
                score=score_value(result),
            )
            st.session_state.phase = "idle"
            st.session_state.phase_start = None
            st.session_state.last_rest_seconds = 0
            st.rerun()

    if st.button("⭕ Visée reposée sans tirer", use_container_width=True):
        aim = elapsed_seconds()
        add_event(
            event_type="Visée reposée",
            result="R",
            rest_seconds=st.session_state.last_rest_seconds,
            aim_seconds=aim,
            score=0,
        )
        # Après une visée reposée, on repart directement sur un repos.
        st.session_state.phase = "rest"
        st.session_state.phase_start = time.time()
        st.session_state.last_rest_seconds = 0
        st.rerun()

# -------------------------
# Series controls
# -------------------------
st.divider()
ctrl1, ctrl2, ctrl3 = st.columns(3)

if ctrl1.button("✅ Terminer série / passer à la suivante", use_container_width=True):
    go_next_series()
    st.rerun()

if ctrl2.button("↩️ Annuler dernière action", use_container_width=True):
    if st.session_state.events:
        st.session_state.events.pop()
    st.rerun()

if ctrl3.button("⏸️ Stop chrono", use_container_width=True):
    st.session_state.phase = "idle"
    st.session_state.phase_start = None
    st.session_state.last_rest_seconds = 0
    st.rerun()

# -------------------------
# Data display
# -------------------------
st.divider()
st.subheader("Données enregistrées")

if st.session_state.events:
    df = pd.DataFrame(st.session_state.events)
    st.dataframe(df, use_container_width=True)

    excel_file = make_excel()
    filename = f"suivi_tir_{st.session_state.shooter or 'tireur'}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    st.download_button(
        "📥 Télécharger le fichier Excel",
        data=excel_file,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
else:
    st.write("Aucune donnée pour le moment.")
