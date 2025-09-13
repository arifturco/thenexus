import streamlit as st
import random
import pandas as pd
from PIL import Image
from io import BytesIO
import base64

# --- Görseller ---
background_path = "images/arkaplan.jpg"
background_img = Image.open(background_path)
logo_path = "images/logo.png"
logo_img = Image.open(logo_path)

def img_to_base64(img):
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

bg_base64 = img_to_base64(background_img)
logo_base64 = img_to_base64(logo_img)

# --- CSS ---
st.markdown(f"""
<style>
.stApp {{
    background-image: url("data:image/png;base64,{bg_base64}");
    background-size: cover;
    background-repeat: no-repeat;
    background-position: center;
    color: white;
}}
.team-card {{
    background: rgba(20, 20, 50, 0.65);
    backdrop-filter: blur(8px);
    border-radius: 18px;
    padding: 20px;
    margin: 15px 0;
    border: 1px solid rgba(255,255,255,0.2);
    box-shadow: 0 0 25px rgba(0, 150, 255, 0.5);
}}
.team-name {{
    font-size: 24px;
    font-weight: bold;
    color: #FFD700;
    text-shadow: 0 0 10px #000;
    margin-bottom: 10px;
}}
.opponent {{
    font-size: 16px;
    padding: 6px 0;
    border-bottom: 1px solid rgba(255,255,255,0.15);
    color: #00e5ff;
}}
</style>
""", unsafe_allow_html=True)

# --- Sekmeler ---
tabs = st.tabs(["Kura Çek", "Fikstür", "Skor Gir", "Puan Durumu"])

# --- Takımlar ---
with tabs[0]:
    st.subheader("Takımları alt alta yazın")
    teams_text = st.text_area("Her satıra bir takım gelecek şekilde yazın", height=300)
    teams = [t.strip() for t in teams_text.splitlines() if t.strip()]

    def draw_opponents(teams, max_attempts=5000):
        for attempt in range(max_attempts):
            opponents = {t: set() for t in teams}
            all_matches = set()
            try:
                for team in teams:
                    while len(opponents[team]) < 8:
                        possible = [t for t in teams if t != team and t not in opponents[team] and len(opponents[t]) < 8]
                        if not possible:
                            raise ValueError("Yetersiz seçenek")
                        choice = random.choice(possible)
                        opponents[team].add(choice)
                        opponents[choice].add(team)
                        match = tuple(sorted([team, choice]))
                        all_matches.add(match)
                if all(len(ops) == 8 for ops in opponents.values()):
                    return opponents, all_matches
            except ValueError:
                continue
        raise RuntimeError(f"{max_attempts} denemede uygun kura bulunamadı!")

    if st.button("🎲 Kura Çek") and teams:
        opponents, all_matches = draw_opponents(teams)
        st.session_state['opponents'] = opponents
        st.session_state['all_matches'] = all_matches
        st.session_state.pop('weeks', None)   # önceki fikstür sil
        st.session_state.pop('scores', None)  # önceki skorlar sil
        st.success("Kura başarıyla çekildi!")

    if 'opponents' in st.session_state:
        st.subheader("🎯 Takımlar ve Rakipleri")
        for team, opps in st.session_state['opponents'].items():
            st.markdown('<div class="team-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="team-name">{team}</div>', unsafe_allow_html=True)
            for opp in opps:
                st.markdown(f'<div class="opponent">⚽ {opp}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# --- Fikstür ---
with tabs[1]:
    if 'opponents' in st.session_state:   # kura çekildiyse
        if 'weeks' not in st.session_state:   # sadece 1 kere oluştur
            teams = list(teams)
            n = len(teams)

            # Takım sayısı tek olursa "BAY" ekle
            if n % 2 != 0:
                teams.append("BAY")
                n += 1

            weeks = {i: [] for i in range(1, 9)}

            # Berger (round robin) algoritması
            team_list = teams[:]
            for week in range(1, 9):
                week_matches = []
                for i in range(n // 2):
                    t1 = team_list[i]
                    t2 = team_list[n - 1 - i]
                    if t1 != "BAY" and t2 != "BAY":
                        week_matches.append((t1, t2))
                weeks[week] = week_matches

                # Rotasyon (ilk sabit, diğerleri kayar)
                team_list = [team_list[0]] + [team_list[-1]] + team_list[1:-1]

            st.session_state['weeks'] = weeks

        # Haftalık fikstürü göster
        st.subheader("📅 Haftalık Fikstür")
        csv_rows = []
        for week, week_matches in st.session_state['weeks'].items():
            st.markdown(f"### Hafta {week}")
            for m in week_matches:
                st.write(f"{m[0]} ⚔️ {m[1]}")
                csv_rows.append({"Hafta": week, "Ev Sahibi": m[0], "Deplasman": m[1]})
        df_fixtur = pd.DataFrame(csv_rows)
        csv_bytes = df_fixtur.to_csv(index=False).encode()
        st.download_button("📥 Fikstürü CSV olarak indir", data=csv_bytes, file_name="fikstur.csv", mime="text/csv")
    else:
        st.info("Önce 'Kura Çek' sekmesinden kura çekin.")

# --- Skor Gir ---
with tabs[2]:
    if 'weeks' in st.session_state:
        if 'scores' not in st.session_state:
            st.session_state['scores'] = {}

        for week, week_matches in st.session_state['weeks'].items():
            st.markdown(f"### Hafta {week}")
            for m in week_matches:
                key1 = f"{m[0]}_{m[1]}_week{week}_1"
                key2 = f"{m[0]}_{m[1]}_week{week}_2"

                col1, col2, col3 = st.columns([2,1,2])
                with col1:
                    g1 = st.selectbox(m[0], options=["-"] + list(range(0, 51)), key=key1)  # 0–50 arası
                with col2:
                    st.write("⚔️")
                with col3:
                    g2 = st.selectbox(m[1], options=["-"] + list(range(0, 51)), key=key2)

                st.session_state['scores'][(m[0], m[1], week)] = (g1, g2)


# --- Puan Durumu ---
with tabs[3]:
    logo_img = Image.open("images/logo.png")
    logo_base64 = img_to_base64(logo_img)
    st.markdown(f"""
    <div style="display:flex; flex-direction:column; align-items:center; margin-bottom:20px;">
        <img src="data:image/png;base64,{logo_base64}" style="width:120px; margin-bottom:10px;">
        <h2 style="color:#FFD700; text-shadow:0 0 10px #000; background:rgba(0,0,50,0.5); 
                   padding:8px 20px; border-radius:12px; border:1px solid #FFD700;">
            📊 PUAN DURUMU
        </h2>
    </div>
    """, unsafe_allow_html=True)

    if 'scores' in st.session_state and st.session_state['scores']:
        points = {t:0 for t in teams}
        wins = {t:0 for t in teams}
        draws = {t:0 for t in teams}
        losses = {t:0 for t in teams}
        goals_for = {t:0 for t in teams}
        goals_against = {t:0 for t in teams}

        for (t1,t2,week),(g1,g2) in st.session_state['scores'].items():
            if g1 == "-" or g2 == "-":
                continue
            g1, g2 = int(g1), int(g2)

            goals_for[t1] += g1
            goals_against[t1] += g2
            goals_for[t2] += g2
            goals_against[t2] += g1
            if g1 > g2:
                points[t1] += 3
                wins[t1] += 1
                losses[t2] += 1
            elif g1 < g2:
                points[t2] += 3
                wins[t2] += 1
                losses[t1] += 1
            else:
                points[t1] += 1
                points[t2] += 1
                draws[t1] += 1
                draws[t2] += 1

        table_data=[]
        for t in teams:
            played = wins[t] + draws[t] + losses[t]
            avg = goals_for[t] - goals_against[t]
            table_data.append({
                "Takım": t,
                "O": played,
                "G": wins[t],
                "B": draws[t],
                "M": losses[t],
                "A": goals_for[t],
                "Y": goals_against[t],
                "AV": avg,
                "P": points[t]
            })

        df_table = pd.DataFrame(table_data)
        # Önce puana, averaja, atılan gole göre sırala
        df_table = df_table.sort_values(by=["P", "AV", "A"], ascending=[False, False, False]).reset_index(drop=True)

        # Eğer eski index sütunu tabloya eklenmişse sil
        if "index" in df_table.columns:
            df_table = df_table.drop(columns=["index"])

        # 🔹 Sıra sütunu ekle (1–36)
        df_table.insert(0, "Sıra", df_table.index + 1)


        # 🔹 Renk fonksiyonu (sıralama indexine göre)
        def color_row(row):
            pos = row.name + 1  # sıra numarası
            if 1 <= pos <= 8:
                return ["background-color: rgba(0,255,0,0.2); color: lime; font-weight:bold;"] * len(row)
            elif 9 <= pos <= 24:
                return ["background-color: rgba(255,215,0,0.2); color: gold; font-weight:bold;"] * len(row)
            elif 25 <= pos <= 36:
                return ["background-color: rgba(255,0,0,0.2); color: red; font-weight:bold;"] * len(row)
            return [""] * len(row)

        # 🔹 Takım isimlerini ayrıca belirgin yapalım (parlak mavi)
        def color_team(val):
            return "color: #00e5ff; font-weight:bold;"


        styled = (df_table.style
                  .apply(color_row, axis=1)  # satır bazlı renk
                  .applymap(color_team, subset=["Takım"])  # takım isimleri mavi
                  .set_table_styles([
            {"selector": "th", "props": [("text-align", "center"),
                                         ("background-color", "rgba(0,0,50,0.8)"),
                                         ("color", "#FFD700"),
                                         ("border", "1px solid #00e5ff")]},
            {"selector": "td", "props": [("text-align", "center"),
                                         ("border", "1px solid #00e5ff")]}
        ])
                  .hide(axis="index")  # 🔹 burada index’i tamamen gizliyoruz
                  )

        # Tabloyu tam ortala
        html_table = styled.to_html(index=False)
        st.markdown(f"<div style='display:flex; justify-content:center;'>{html_table}</div>", unsafe_allow_html=True)

    else:
        st.info("Henüz skor girilmedi veya fikstür oluşturulmadı.")




