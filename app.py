
# -*- coding: utf-8 -*-
import random, io, json
from typing import Optional, Dict, List
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Team Builder", page_icon="⚽", layout="centered")

def compute_target_sizes(n_players: int, num_teams: int):
    base = n_players // num_teams
    remainder = n_players % num_teams
    return [base + (1 if i < remainder else 0) for i in range(num_teams)]

def balanced_random_teams_with_caps(df: pd.DataFrame, num_teams: int, level_caps: Optional[Dict[int, Optional[int]]] = None):
    warnings = []
    buckets = {
        3: df[df["stärke"] == 3].to_dict("records"),
        2: df[df["stärke"] == 2].to_dict("records"),
        1: df[df["stärke"] == 1].to_dict("records"),
    }
    for b in buckets.values():
        random.shuffle(b)
    teams: List[List[dict]] = [[] for _ in range(num_teams)]
    caps = compute_target_sizes(len(df), num_teams)
    counts = [{1: 0, 2: 0, 3: 0} for _ in range(num_teams)]

    def can_add(idx): return len(teams[idx]) < caps[idx]

    def rr_assign_with_limits(items, level):
        i = 0
        leftovers = []
        for it in items:
            placed = False
            for attempts in range(num_teams):
                idx = (i + attempts) % num_teams
                if not can_add(idx): continue
                if level_caps and level_caps.get(level) is not None:
                    if counts[idx][level] >= level_caps[level]:
                        continue
                teams[idx].append(it)
                counts[idx][level] += 1
                i = idx + 1
                placed = True
                break
            if not placed: leftovers.append(it)
        return leftovers

    leftovers_all = []
    for lvl in (3, 2, 1):
        leftovers_all.extend(rr_assign_with_limits(buckets[lvl], lvl))

    if leftovers_all:
        warnings.append("Einige Spieler wurden im Fallback ohne Stärke-Limits verteilt.")
        i = 0
        for it in leftovers_all:
            placed = False
            for attempts in range(num_teams):
                idx = (i + attempts) % num_teams
                if can_add(idx):
                    lvl = it["stärke"]
                    teams[idx].append(it)
                    counts[idx][lvl] += 1
                    i = idx + 1
                    placed = True
                    break
            if not placed:
                smallest_idx = min(range(num_teams), key=lambda k: len(teams[k]))
                lvl = it["stärke"]
                teams[smallest_idx].append(it)
                counts[smallest_idx][lvl] += 1

    for t in teams: random.shuffle(t)
    return teams, warnings

def build_teams_df(players_df: pd.DataFrame, num_teams: int, seed: Optional[int], level_caps: Optional[Dict[int, Optional[int]]], team_names: Optional[List[str]]):
    if seed is not None: random.seed(seed)
    df = players_df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    if "name" not in df.columns or "stärke" not in df.columns:
        raise ValueError("Spalten müssen 'Name' und 'Stärke' heißen.")
    df = df.dropna(subset=["name", "stärke"])
    df["stärke"] = pd.to_numeric(df["stärke"], errors="coerce").astype("Int64")
    df = df[df["stärke"].isin([1, 2, 3])]
    if df.empty: raise ValueError("Keine gültigen Spieler. Stärke muss 1, 2 oder 3 sein.")
    if num_teams < 1: raise ValueError("Anzahl Teams muss mindestens 1 sein.")
    if num_teams > len(df): raise ValueError(f"Teams ({num_teams}) dürfen Spieleranzahl ({len(df)}) nicht überschreiten.")

    teams, warns = balanced_random_teams_with_caps(df, num_teams, level_caps)
    rows = []
    for idx, team in enumerate(teams, start=1):
        for p in team:
            rows.append({"Team": f"Team {idx}", "Name": p.get("name"), "Stärke": p.get("stärke")})
    out_df = pd.DataFrame(rows).sort_values(["Team", "Stärke"], ascending=[True, False]).reset_index(drop=True)
    if team_names and len(team_names) == num_teams:
        mapping = {f"Team {i+1}": team_names[i] for i in range(num_teams)}
        out_df["Team"] = out_df["Team"].map(mapping)
    return out_df, teams, warns

# --- Session ---
if "players_df" not in st.session_state:
    st.session_state.players_df = pd.DataFrame({"Name": [], "Stärke": []})
if "team_names" not in st.session_state:
    st.session_state.team_names = []
if "last_result" not in st.session_state:
    st.session_state.last_result = None

def ensure_team_names_count(n: int):
    names = st.session_state.team_names
    if len(names) < n: names += [f"Team {i}" for i in range(len(names)+1, n+1)]
    elif len(names) > n: names = names[:n]
    st.session_state.team_names = names

# --- UI ---
st.title("⚽ Zufallsgenerator")
st.caption("Name + Stärke (1,2,3) erfassen → Teams sind höchstens um 1 unterschiedlich groß.")

with st.form("add_player_form", clear_on_submit=True):
    c1, c2, c3 = st.columns([2,1,1])
    with c1: add_name = st.text_input("Name hinzufügen", placeholder="z. B. Alex")
    with c2: add_strength = st.selectbox("Stärke", options=[1,2,3], index=1)
    with c3: submitted = st.form_submit_button("➕ Hinzufügen")
    if submitted:
        if add_name.strip():
            new_row = pd.DataFrame([{"Name": add_name.strip(), "Stärke": add_strength}])
            st.session_state.players_df = pd.concat([st.session_state.players_df, new_row], ignore_index=True)
        else: st.warning("Bitte einen Namen eingeben.")

st.markdown("**Spielerliste** (bearbeitbar):")
try:
    edited_df = st.data_editor(
        st.session_state.players_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Name": st.column_config.TextColumn(required=True),
            "Stärke": st.column_config.SelectboxColumn(options=[1,2,3], required=True),
        },
        hide_index=True,
    )
except Exception:
    st.info("Hinweis: Dateneditor nicht verfügbar – Fallback-Ansicht.")
    edited_df = st.session_state.players_df
st.session_state.players_df = edited_df

c_a, c_b = st.columns(2)
with c_a:
    players_json = st.session_state.players_df.to_json(orient="records", force_ascii=False)
    st.download_button("💾 Spielerliste speichern (JSON)", players_json.encode("utf-8"),
                       "spielerliste.json", "application/json", use_container_width=True)
with c_b:
    up = st.file_uploader("Spielerliste laden (JSON)", type=["json"])
    if up:
        try:
            data = json.load(up)
            df_in = pd.DataFrame(data)
            df_in.columns = [str(c).strip().title() for c in df_in.columns]
            if not {"Name","Stärke"}.issubset(df_in.columns):
                st.error("JSON muss die Spalten 'Name' und 'Stärke' enthalten.")
            else:
                df_in["Stärke"] = pd.to_numeric(df_in["Stärke"], errors="coerce").astype("Int64")
                df_in = df_in.dropna(subset=["Name","Stärke"])
                df_in = df_in[df_in["Stärke"].isin([1,2,3])]
                st.session_state.players_df = df_in.reset_index(drop=True)
                st.success("Spielerliste geladen.")
        except Exception as e:
            st.error(f"Fehler beim Laden: {e}")

st.divider()

colL, colR = st.columns(2)
with colL:
    default_teams = 2 if len(st.session_state.players_df) >= 2 else 1
    num_teams = st.number_input("Anzahl Teams", min_value=1, step=1, value=default_teams)
with colR:
    seed_fix = st.checkbox("Zufall mit Seed fixieren?")
    seed_val = st.number_input("Seed (Ganzzahl)", step=1, value=42, disabled=not seed_fix)

ensure_team_names_count(int(num_teams))
st.markdown("**Team‑Namen** (optional):")
tn_cols = st.columns(min(3, int(num_teams))) if num_teams > 0 else []
for i in range(int(num_teams)):
    col = tn_cols[i % max(1, len(tn_cols))]
    with col:
        st.session_state.team_names[i] = st.text_input(
            f"Team {i+1} Name",
            value=st.session_state.team_names[i],
            key=f"team_name_{i}",
            placeholder=f"Team {i+1}"
        )

st.markdown("**Pro‑Stärke‑Limits je Team** (optional):")
lim_on = st.checkbox("Limits aktivieren")
lc1, lc2, lc3 = st.columns(3)
lvl_caps = None
if lim_on:
    with lc3: cap3 = st.number_input("Max. Stärke‑3/Team", min_value=0, step=1, value=0)
    with lc2: cap2 = st.number_input("Max. Stärke‑2/Team", min_value=0, step=1, value=0)
    with lc1: cap1 = st.number_input("Max. Stärke‑1/Team", min_value=0, step=1, value=0)
    lvl_caps = {1: None if cap1 == 0 else int(cap1),
                2: None if cap2 == 0 else int(cap2),
                3: None if cap3 == 0 else int(cap3)}

st.divider()

c1, c2 = st.columns(2)
with c1:
    generate = st.button("🧩 Teams generieren", type="primary", use_container_width=True)
with c2:
    remix = st.button("🎲 Neu mischen", use_container_width=True)

def render_results(out_df, teams, warns, team_names):
    for w in warns: st.warning(w)
    st.subheader("Zusammenfassung")
    for i, t in enumerate(teams, start=1):
        counts = {1: sum(1 for p in t if p["stärke"] == 1),
                  2: sum(1 for p in t if p["stärke"] == 2),
                  3: sum(1 for p in t if p["stärke"] == 3)}
        shown_name = team_names[i-1] if team_names and i-1 < len(team_names) else f"Team {i}"
        st.write(f"**{shown_name}**: {len(t)} Spieler (1:{counts[1]} | 2:{counts[2]} | 3:{counts[3]})")
    st.subheader("Teams")
    for i, t in enumerate(teams, start=1):
        shown_name = team_names[i-1] if team_names and i-1 < len(team_names) else f"Team {i}"
        with st.expander(f"{shown_name} ({len(t)} Spieler)"):
            team_df = pd.DataFrame(t)[["name", "stärke"]].rename(columns={"name": "Name", "stärke": "Stärke"})
            st.dataframe(team_df.sort_values("Stärke", ascending=False), use_container_width=True)
    st.subheader("Gesamte Zuteilung")
    st.dataframe(out_df, use_container_width=True)
    csv_buf = io.StringIO()
    out_df.to_csv(csv_buf, index=False)
    st.download_button("⬇️ CSV herunterladen", csv_buf.getvalue(), "Teams_Zuteilung.csv", "text/csv", use_container_width=True)

def do_build(use_seed: bool, shuffle_override: bool = False):
    seed_to_use = int(seed_val) if use_seed and not shuffle_override else None
    out_df, teams, warns = build_teams_df(
        st.session_state.players_df,
        int(num_teams),
        seed=seed_to_use,
        level_caps=lvl_caps,
        team_names=st.session_state.team_names
    )
    st.session_state.last_result = (out_df, teams, warns)
    st.success("Zuteilung erstellt!" if not shuffle_override else "Neu gemischt!")
    render_results(out_df, teams, warns, st.session_state.team_names)

try:
    if generate: do_build(use_seed=seed_fix, shuffle_override=False)
    elif remix: do_build(use_seed=False, shuffle_override=True)
    elif st.session_state.last_result:
        out_df, teams, warns = st.session_state.last_result
        render_results(out_df, teams, warns, st.session_state.team_names)
except Exception as e:
    st.error(f"Fehler: {e}")
