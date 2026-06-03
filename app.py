from __future__ import annotations

import io
import time
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st


LOW_SCORES = ["8", "7", "6", "5", "4", "3", "2", "1", "Hors-temps"]
PHASE_LABELS = {
    "no_series": "Accueil",
    "rest_running": "Repos en cours",
    "aim_running": "Visée en cours",
    "score_choice": "Résultat du tir",
    "low_score_choice": "Score 8 ou moins",
    "series_finished": "Série terminée",
    "session_finished": "Session terminée",
}
DISPLAY_RENAME = {
    "Serie": "Série",
    "Resultat": "Résultat",
    "Temps visee secondes": "Temps visée secondes",
}


def init_state() -> None:
    defaults: dict[str, Any] = {
        "athlete_name": "",
        "session_date": date.today(),
        "competition": "",
        "session_comment": "",
        "actions": [],
        "current_series": 0,
        "phase": "no_series",
        "rest_start": None,
        "aim_start": None,
        "pending_rest_seconds": 0.0,
        "current_aim_type": "Visée",
        "pending_aim_seconds": None,
        "pending_aim_type": "Visée",
        "confirm_reset": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_session() -> None:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    init_state()


def elapsed_seconds(start: float | None) -> float:
    if start is None:
        return 0.0
    return max(0.0, time.time() - start)


def fmt_seconds(value: float | int | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.1f} s"


def actions_df(actions: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    data = st.session_state.actions if actions is None else actions
    columns = [
        "Serie",
        "Action n°",
        "Type action",
        "Resultat",
        "Score",
        "Temps repos secondes",
        "Temps visee secondes",
        "Horodatage",
    ]
    return pd.DataFrame(data, columns=columns)


def display_actions_df(actions: list[dict[str, Any]] | None = None) -> pd.DataFrame:
    return actions_df(actions).rename(columns=DISPLAY_RENAME)


def current_series_actions() -> list[dict[str, Any]]:
    serie = st.session_state.current_series
    return [a for a in st.session_state.actions if a["Serie"] == serie]


def next_action_number() -> int:
    return len(current_series_actions()) + 1


def start_rest() -> None:
    st.session_state.rest_start = time.time()
    st.session_state.aim_start = None
    st.session_state.pending_aim_seconds = None
    st.session_state.phase = "rest_running"


def start_new_series() -> None:
    st.session_state.current_series += 1


def start_aim(aim_type: str) -> None:
    if st.session_state.current_series == 0:
        start_new_series()
    st.session_state.current_aim_type = aim_type
    st.session_state.pending_aim_type = aim_type
    st.session_state.pending_rest_seconds = elapsed_seconds(st.session_state.rest_start)
    st.session_state.rest_start = None
    st.session_state.aim_start = time.time()
    st.session_state.phase = "aim_running"


def make_action(result: str, score: float | int | None, action_type: str, aim_seconds: float | None = None) -> dict[str, Any]:
    return {
        "Serie": st.session_state.current_series,
        "Action n°": next_action_number(),
        "Type action": action_type,
        "Resultat": result,
        "Score": score,
        "Temps repos secondes": round(float(st.session_state.pending_rest_seconds or 0), 2),
        "Temps visee secondes": round(
            elapsed_seconds(st.session_state.aim_start) if aim_seconds is None else aim_seconds,
            2,
        ),
        "Horodatage": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def save_action_and_start_rest(result: str, score: float | int | None, action_type: str) -> None:
    st.session_state.actions.append(make_action(result, score, action_type))
    start_rest()


def prepare_score_choice() -> None:
    st.session_state.pending_aim_seconds = elapsed_seconds(st.session_state.aim_start)
    st.session_state.pending_aim_type = st.session_state.current_aim_type
    st.session_state.phase = "score_choice"


def save_score(result: str, score: float | int | None) -> None:
    action_type = f"Tir validé - {st.session_state.pending_aim_type}"
    st.session_state.actions.append(
        make_action(result, score, action_type, aim_seconds=st.session_state.pending_aim_seconds)
    )
    start_rest()


def save_rest_without_shot() -> None:
    action_type = f"Repos sans tirer - {st.session_state.current_aim_type}"
    save_action_and_start_rest("R", None, action_type)


def finish_series() -> None:
    st.session_state.phase = "series_finished"
    st.session_state.rest_start = None
    st.session_state.aim_start = None
    st.session_state.pending_rest_seconds = 0.0


def undo_last_action() -> None:
    if st.session_state.actions:
        st.session_state.actions.pop()


def series_summary(actions: list[dict[str, Any]]) -> dict[str, Any]:
    if not actions:
        return {
            "Score total": 0,
            "Tirs validés": 0,
            "Nombre de 10x": 0,
            "Temps total repos": 0.0,
            "Temps total visée": 0.0,
            "Temps moyen repos": 0.0,
            "Temps moyen visée": 0.0,
        }

    valid_shots = [a for a in actions if a["Resultat"] != "R"]
    rest_times = [float(a["Temps repos secondes"]) for a in actions]
    aim_times = [float(a["Temps visee secondes"]) for a in actions]
    score_total = sum(float(a["Score"] or 0) for a in valid_shots)
    return {
        "Score total": round(score_total, 2),
        "Tirs validés": len(valid_shots),
        "Nombre de 10x": sum(1 for a in valid_shots if a["Resultat"] == "10x"),
        "Temps total repos": round(sum(rest_times), 2),
        "Temps total visée": round(sum(aim_times), 2),
        "Temps moyen repos": round(sum(rest_times) / len(rest_times), 2),
        "Temps moyen visée": round(sum(aim_times) / len(aim_times), 2),
    }


def all_series_summary_df() -> pd.DataFrame:
    rows = []
    for serie in range(1, st.session_state.current_series + 1):
        serie_actions = [a for a in st.session_state.actions if a["Serie"] == serie]
        summary = series_summary(serie_actions)
        rows.append(
            {
                "Série": serie,
                "Score total": summary["Score total"],
                "Tirs validés": summary["Tirs validés"],
                "Nombre de 10x": summary["Nombre de 10x"],
                "Temps total repos": summary["Temps total repos"],
                "Temps total visée": summary["Temps total visée"],
                "Temps moyen repos": summary["Temps moyen repos"],
                "Temps moyen visée": summary["Temps moyen visée"],
            }
        )
    return pd.DataFrame(rows)


def session_summary() -> dict[str, Any]:
    summaries = all_series_summary_df()
    actions = st.session_state.actions
    rest_times = [float(a["Temps repos secondes"]) for a in actions]
    aim_times = [float(a["Temps visee secondes"]) for a in actions]
    score_total = float(summaries["Score total"].sum()) if not summaries.empty else 0.0
    total_series = st.session_state.current_series
    return {
        "Athlète": st.session_state.athlete_name,
        "Date": st.session_state.session_date.isoformat()
        if hasattr(st.session_state.session_date, "isoformat")
        else str(st.session_state.session_date),
        "Compétition": st.session_state.competition,
        "Nombre total de séries": total_series,
        "Score total": round(score_total, 2),
        "Tirs validés": int(summaries["Tirs validés"].sum()) if not summaries.empty else 0,
        "Nombre total de 10x": int(summaries["Nombre de 10x"].sum()) if not summaries.empty else 0,
        "Moyenne par série": round(score_total / total_series, 2) if total_series else 0.0,
        "Temps moyen repos global": round(sum(rest_times) / len(rest_times), 2) if rest_times else 0.0,
        "Temps moyen visée global": round(sum(aim_times) / len(aim_times), 2) if aim_times else 0.0,
        "Commentaire": st.session_state.session_comment,
    }


def excel_bytes() -> bytes:
    actions = display_actions_df().copy()
    if not actions.empty:
        actions.insert(0, "Athlète", st.session_state.athlete_name)
        actions.insert(
            1,
            "Date",
            st.session_state.session_date.isoformat()
            if hasattr(st.session_state.session_date, "isoformat")
            else str(st.session_state.session_date),
        )
        actions.insert(2, "Compétition", st.session_state.competition)
        actions["Commentaire session"] = st.session_state.session_comment
    else:
        actions = pd.DataFrame(
            columns=[
                "Athlète",
                "Date",
                "Compétition",
                "Série",
                "Action n°",
                "Type action",
                "Résultat",
                "Score",
                "Temps repos secondes",
                "Temps visée secondes",
                "Horodatage",
                "Commentaire session",
            ]
        )

    session_rows = [{"Information": key, "Valeur": value} for key, value in session_summary().items()]
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        actions.to_excel(writer, sheet_name="Actions détaillées", index=False)
        all_series_summary_df().to_excel(writer, sheet_name="Résumé séries", index=False)
        pd.DataFrame(session_rows).to_excel(writer, sheet_name="Résumé session", index=False)
    return output.getvalue()


def render_session_form() -> None:
    st.markdown('<div class="mobile-card">', unsafe_allow_html=True)
    st.subheader("Étape 1 - Informations")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Prénom", key="athlete_name", placeholder="Ex : Luna")
    with col2:
        st.text_input("Compétition", key="competition", placeholder="Ex : Départemental 10 m")
    st.date_input("Date", key="session_date")
    with st.expander("Commentaire optionnel"):
        st.text_area("Commentaire", key="session_comment", height=90)
    st.markdown('</div>', unsafe_allow_html=True)


def render_status() -> None:
    phase = st.session_state.phase
    st.subheader(PHASE_LABELS.get(phase, phase))

    if st.session_state.current_series:
        st.caption(f"Série actuelle : {st.session_state.current_series}")

    if phase == "rest_running":
        st.info(f"Chrono repos du prochain tir : {fmt_seconds(elapsed_seconds(st.session_state.rest_start))}")
    elif phase == "aim_running":
        st.info(
            f"{st.session_state.current_aim_type} | "
            f"Repos enregistré : {fmt_seconds(st.session_state.pending_rest_seconds)} | "
            f"Chrono visée : {fmt_seconds(elapsed_seconds(st.session_state.aim_start))}"
        )
    elif phase in {"score_choice", "low_score_choice"}:
        st.info(f"Temps de visée enregistré : {fmt_seconds(st.session_state.pending_aim_seconds)}")


def render_start_aim_buttons() -> None:
    col1, col2 = st.columns(2)
    if col1.button("Démarrer visée", type="primary", use_container_width=True):
        start_aim("Visée")
        st.rerun()
    if col2.button("Visée main faible", type="primary", use_container_width=True):
        start_aim("Visée main faible")
        st.rerun()


def render_finish_button() -> None:
    if st.button("Arrêter la série", type="secondary", use_container_width=True):
        finish_series()
        st.rerun()


def render_controls() -> None:
    phase = st.session_state.phase

    st.markdown('<div class="mobile-card controls-card">', unsafe_allow_html=True)

    if phase == "no_series":
        st.write("Lance une série directement avec un chrono de visée.")
        render_start_aim_buttons()

    elif phase == "rest_running":
        st.write("Quand le repos est fini, démarre la prochaine visée.")
        render_start_aim_buttons()
        col1, col2 = st.columns(2)
        if col1.button("Annuler dernière action", use_container_width=True, disabled=not bool(current_series_actions())):
            undo_last_action()
            st.rerun()
        with col2:
            render_finish_button()

    elif phase == "aim_running":
        col1, col2 = st.columns(2)
        if col1.button("Tir", type="primary", use_container_width=True):
            prepare_score_choice()
            st.rerun()
        if col2.button("Repos sans tirer", type="secondary", use_container_width=True):
            save_rest_without_shot()
            st.rerun()

    elif phase == "score_choice":
        st.write("Choisis le résultat du tir.")
        cols = st.columns(4)
        if cols[0].button("10x", type="primary", use_container_width=True):
            save_score("10x", 10)
            st.rerun()
        if cols[1].button("10", type="primary", use_container_width=True):
            save_score("10", 10)
            st.rerun()
        if cols[2].button("9", type="primary", use_container_width=True):
            save_score("9", 9)
            st.rerun()
        if cols[3].button("8 ou -", type="secondary", use_container_width=True):
            st.session_state.phase = "low_score_choice"
            st.rerun()

    elif phase == "low_score_choice":
        st.write("Sélectionne le score exact.")
        cols = st.columns(3)
        for index, label in enumerate(LOW_SCORES):
            with cols[index % 3]:
                if st.button(label, use_container_width=True):
                    score = 0 if label == "Hors-temps" else int(label)
                    save_score(label, score)
                    st.rerun()

    elif phase == "series_finished":
        st.success("Série arrêtée. Tu veux en commencer une autre ?")
        col1, col2 = st.columns(2)
        if col1.button("Commencer une autre série", type="primary", use_container_width=True):
            start_new_series()
            st.session_state.phase = "rest_running"
            st.session_state.rest_start = time.time()
            st.rerun()
        if col2.button("Terminer la session", type="secondary", use_container_width=True):
            st.session_state.phase = "session_finished"
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def render_metrics(summary: dict[str, Any]) -> None:
    cols = st.columns(4)
    cols[0].metric("Score", summary["Score total"])
    cols[1].metric("Tirs", summary["Tirs validés"])
    cols[2].metric("10x", summary["Nombre de 10x"])
    cols[3].metric("Visée moy.", fmt_seconds(summary["Temps moyen visée"]))


def render_current_series() -> None:
    if not st.session_state.current_series:
        return

    serie_actions = current_series_actions()
    st.divider()
    st.subheader(f"Série {st.session_state.current_series}")
    render_metrics(series_summary(serie_actions))

    with st.expander("Voir les actions de la série"):
        st.dataframe(display_actions_df(serie_actions), use_container_width=True, hide_index=True)


def render_global_summary() -> None:
    st.divider()
    st.subheader("Résumé global")
    summary = session_summary()
    cols = st.columns(4)
    cols[0].metric("Score total", summary["Score total"])
    cols[1].metric("Séries", summary["Nombre total de séries"])
    cols[2].metric("Tirs", summary["Tirs validés"])
    cols[3].metric("10x", summary["Nombre total de 10x"])

    st.dataframe(all_series_summary_df(), use_container_width=True, hide_index=True)

    athlete = st.session_state.athlete_name.strip() or "session"
    filename = f"suivi_match_{athlete}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx".replace(" ", "_")
    st.download_button(
        "Télécharger le fichier Excel",
        data=excel_bytes(),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        use_container_width=True,
    )


def render_reset_zone() -> None:
    with st.expander("Réinitialiser la session"):
        st.checkbox("Je confirme la réinitialisation", key="confirm_reset")
        if st.button(
            "Réinitialiser toute la session",
            type="secondary",
            use_container_width=True,
            disabled=not st.session_state.confirm_reset,
        ):
            reset_session()
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="Suivi match", page_icon="🎯", layout="centered")
    init_state()

    st.markdown(
        """
        <style>
        .block-container {
            max-width: 760px;
            padding-top: 1rem;
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }
        .mobile-card {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 18px;
            padding: 1rem;
            margin-bottom: 1rem;
            background: rgba(250, 250, 250, 0.03);
        }
        .controls-card {
            position: sticky;
            top: 0.4rem;
            z-index: 10;
            backdrop-filter: blur(8px);
        }
        div.stButton > button, div.stDownloadButton > button {
            min-height: 3.8rem;
            font-size: 1.08rem;
            font-weight: 800;
            border-radius: 14px;
            white-space: normal;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.45rem;
        }
        @media (max-width: 640px) {
            .block-container {
                padding-left: 0.55rem;
                padding-right: 0.55rem;
            }
            div[data-testid="column"] {
                width: 100% !important;
                flex: 1 1 100% !important;
            }
            div.stButton > button, div.stDownloadButton > button {
                min-height: 4.2rem;
                font-size: 1.05rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🎯 Suivi de match")
    render_session_form()
    render_status()
    render_controls()
    render_current_series()

    if st.session_state.phase == "session_finished":
        render_global_summary()

    render_reset_zone()


if __name__ == "__main__":
    main()
