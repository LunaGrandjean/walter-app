from __future__ import annotations

import io
import time
from datetime import date, datetime
from typing import Any

import pandas as pd
import streamlit as st


RESULTS = ["X", "10", "9", "8 et -"]
PHASE_LABELS = {
    "no_series": "Pas de série en cours",
    "series_ready": "Série en cours - prêt pour le repos",
    "rest_running": "Repos en cours",
    "aim_running": "Visée en cours",
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
        "pending_rest_seconds": None,
        "pending_x_index": None,
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


def start_next_rest() -> None:
    st.session_state.rest_start = time.time()
    st.session_state.aim_start = None
    st.session_state.pending_rest_seconds = None
    st.session_state.phase = "rest_running"


def make_action(
    result: str,
    score: float | int | None,
    action_type: str,
    aim_seconds: float | None = None,
) -> dict[str, Any]:
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


def add_action(result: str, score: float | int | None, action_type: str) -> None:
    st.session_state.actions.append(make_action(result, score, action_type))
    start_next_rest()


def add_pending_x() -> None:
    action = make_action("X", None, "Tir validé", elapsed_seconds(st.session_state.aim_start))
    st.session_state.actions.append(action)
    st.session_state.pending_x_index = len(st.session_state.actions) - 1
    start_next_rest()


def has_pending_x() -> bool:
    index = st.session_state.pending_x_index
    return (
        isinstance(index, int)
        and 0 <= index < len(st.session_state.actions)
        and st.session_state.actions[index]["Resultat"] == "X"
        and st.session_state.actions[index]["Score"] is None
    )


def validate_pending_x(score: float) -> None:
    if has_pending_x():
        st.session_state.actions[st.session_state.pending_x_index]["Score"] = round(score, 1)
    st.session_state.pending_x_index = None


def start_new_series() -> None:
    st.session_state.current_series += 1
    start_next_rest()


def switch_to_aim() -> None:
    st.session_state.pending_rest_seconds = elapsed_seconds(st.session_state.rest_start)
    st.session_state.aim_start = time.time()
    st.session_state.phase = "aim_running"


def finish_series() -> None:
    st.session_state.phase = "series_finished"
    st.session_state.rest_start = None
    st.session_state.aim_start = None
    st.session_state.pending_rest_seconds = None


def undo_last_action() -> None:
    if st.session_state.actions:
        last_index = len(st.session_state.actions) - 1
        if st.session_state.pending_x_index == last_index:
            st.session_state.pending_x_index = None
        st.session_state.actions.pop()


def series_summary(actions: list[dict[str, Any]]) -> dict[str, Any]:
    if not actions:
        return {
            "Score total": 0,
            "Tirs validés": 0,
            "Nombre de X": 0,
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
        "Nombre de X": sum(1 for a in valid_shots if a["Resultat"] == "X"),
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
                "Nombre de X": summary["Nombre de X"],
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
        "Nombre total de X": int(summaries["Nombre de X"].sum()) if not summaries.empty else 0,
        "Moyenne par série": round(score_total / total_series, 2) if total_series else 0.0,
        "Temps moyen repos global": round(sum(rest_times) / len(rest_times), 2)
        if rest_times
        else 0.0,
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


def render_metrics(summary: dict[str, Any]) -> None:
    cols = st.columns(5)
    cols[0].metric("Score série", summary["Score total"])
    cols[1].metric("Tirs validés", summary["Tirs validés"])
    cols[2].metric("Nombre de X", summary["Nombre de X"])
    cols[3].metric("Repos moyen", fmt_seconds(summary["Temps moyen repos"]))
    cols[4].metric("Visée moyenne", fmt_seconds(summary["Temps moyen visée"]))


def render_status() -> None:
    phase = st.session_state.phase
    status = PHASE_LABELS.get(phase, phase)
    st.subheader(status)

    if st.session_state.current_series:
        st.caption(f"Série actuelle : {st.session_state.current_series}")

    if phase == "rest_running":
        st.info(f"Chrono repos du prochain tir : {fmt_seconds(elapsed_seconds(st.session_state.rest_start))}")
    elif phase == "aim_running":
        st.info(
            "Repos enregistré : "
            f"{fmt_seconds(st.session_state.pending_rest_seconds)} | "
            f"Chrono visée : {fmt_seconds(elapsed_seconds(st.session_state.aim_start))}"
        )


def render_pending_x() -> None:
    if not has_pending_x():
        return

    action = st.session_state.actions[st.session_state.pending_x_index]
    st.warning(
        f"Mouche à compléter pour l'action {action['Action n°']}. "
        "Le repos du tir suivant est déjà en cours."
    )
    col1, col2 = st.columns([2, 1])
    with col1:
        mouche_score = st.number_input(
            "Valeur de la mouche",
            min_value=0.0,
            max_value=10.9,
            value=10.0,
            step=0.1,
            format="%.1f",
            key=f"mouche_score_{st.session_state.pending_x_index}",
        )
    with col2:
        st.write("")
        st.write("")
        if st.button("Valider la mouche", type="primary", use_container_width=True):
            validate_pending_x(float(mouche_score))
            st.rerun()


def render_session_form() -> None:
    with st.sidebar:
        st.header("Session")
        st.text_input("Nom de l'athlète", key="athlete_name")
        st.date_input("Date", key="session_date")
        st.text_input("Compétition", key="competition")
        st.text_area("Commentaire", key="session_comment", height=100)

        st.divider()
        st.checkbox("Confirmer la réinitialisation", key="confirm_reset")
        if st.button(
            "Réinitialiser toute la session",
            type="secondary",
            use_container_width=True,
            disabled=not st.session_state.confirm_reset,
        ):
            reset_session()
            st.rerun()


def render_finish_button(container: Any) -> None:
    disabled = has_pending_x()
    if container.button("Fin de série", type="secondary", use_container_width=True, disabled=disabled):
        finish_series()
        st.rerun()
    if disabled:
        container.caption("Validez d'abord la mouche en attente.")


def render_controls() -> None:
    phase = st.session_state.phase

    if phase == "no_series":
        if st.button("Commencer une nouvelle série", type="primary", use_container_width=True):
            start_new_series()
            st.rerun()
        return

    if phase == "session_finished":
        return

    if phase == "series_ready":
        col1, col2 = st.columns(2)
        if col1.button("Démarrer repos", type="primary", use_container_width=True):
            start_next_rest()
            st.rerun()
        render_finish_button(col2)

    elif phase == "rest_running":
        col1, col2, col3 = st.columns(3)
        if col1.button("Fin repos / Démarrer visée", type="primary", use_container_width=True):
            switch_to_aim()
            st.rerun()
        if col2.button(
            "Annuler dernière action",
            use_container_width=True,
            disabled=not bool(current_series_actions()),
        ):
            undo_last_action()
            st.rerun()
        render_finish_button(col3)

    elif phase == "aim_running":
        st.write("Résultat du tir")
        cols = st.columns(4)
        pending_x = has_pending_x()
        for index, result in enumerate(RESULTS):
            with cols[index % 4]:
                if st.button(f"Résultat {result}", use_container_width=True, disabled=result == "X" and pending_x):
                    if result == "X":
                        add_pending_x()
                    else:
                        add_action(result, int(result), "Tir validé")
                    st.rerun()

        col1, col2 = st.columns(2)
        if col1.button("Reposée sans tirer", type="secondary", use_container_width=True):
            add_action("R", None, "Visée reposée")
            st.rerun()
        render_finish_button(col2)

    elif phase == "series_finished":
        st.success("Série terminée. Voulez-vous commencer une nouvelle série ?")
        col1, col2 = st.columns(2)
        if col1.button("Oui", type="primary", use_container_width=True):
            start_new_series()
            st.rerun()
        if col2.button("Non", type="secondary", use_container_width=True):
            st.session_state.phase = "session_finished"
            st.rerun()


def render_current_series() -> None:
    if not st.session_state.current_series:
        return

    serie_actions = current_series_actions()
    st.divider()
    st.subheader(f"Série {st.session_state.current_series}")
    render_metrics(series_summary(serie_actions))

    st.write("Actions de la série en cours")
    st.dataframe(display_actions_df(serie_actions), use_container_width=True, hide_index=True)


def render_global_summary() -> None:
    st.divider()
    st.subheader("Résumé global")
    summary = session_summary()
    cols = st.columns(4)
    cols[0].metric("Score total", summary["Score total"])
    cols[1].metric("Séries", summary["Nombre total de séries"])
    cols[2].metric("Tirs validés", summary["Tirs validés"])
    cols[3].metric("Total X", summary["Nombre total de X"])

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


def main() -> None:
    st.set_page_config(page_title="Suivi match", page_icon="target", layout="wide")
    init_state()

    st.markdown(
        """
        <style>
        div.stButton > button, div.stDownloadButton > button {
            min-height: 3rem;
            font-size: 1.05rem;
            font-weight: 700;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.7rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    render_session_form()

    st.title("Suivi de match")
    render_status()
    render_pending_x()
    render_controls()
    render_current_series()

    if st.session_state.phase == "session_finished":
        render_global_summary()


if __name__ == "__main__":
    main()
