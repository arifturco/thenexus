import streamlit as st
import random
import pandas as pd
from PIL import Image
from io import BytesIO
import base64
import re
from supabase import create_client

# -------------------------
# CONFIG: Supabase client
# -------------------------
# TODO: production ortamında KEY'i environment variable ile alın.
url = "https://zpfgzjlqtiruzitsonqs.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InpwZmd6amxxdGlydXppdHNvbnFzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc3NjMwODgsImV4cCI6MjA3MzMzOTA4OH0.HT6MpQOfh4YavubUt3oRJ6iSeYqaHh55qna_SwQ69Dw"
supabase = create_client(url, key)

# -------------------------
# Yardımcı fonksiyonlar
# -------------------------
def keyify(*parts):
    """Anahtar standardizasyonu: takım isimlerindeki özel karakterleri normalize eder."""
    return "score_" + "_".join(re.sub(r'[^0-9a-zA-Z]+', '_', str(p)) for p in parts)

def img_to_base64(img):
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def create_schedule_from_draw(players, draw_pairs, total_weeks=8):
    """
    36 oyuncu/ takım, toplam tek maçlı eşleşmeler (ör. A-B sadece bir kez),
    8 hafta, haftada len(players)//2 maç (36 için 18).
    draw_pairs: iterable of (a,b) unordered pairs (her eş yalnızca 1 kez olmalı).
    Algoritma: haftalık max matching bulmaya çalışır (greedy + shuffle denemeleri).
    """

    players = list(players)
    n = len(players)
    matches_per_week = n // 2  # örn. 36 -> 18
    matches = set()
    # Normalize draw_pairs: tuple(sorted(...)) ile tekilleştir
    for a, b in draw_pairs:
        if a == b:
            continue
        matches.add(tuple(sorted((a, b))))
    matches = list(matches)

    # Hızlı sanity check: toplam maç sayısı istenenle uyuşmalı
    expected_total_matches = (n * (len(matches) * 0 // len(matches) + 0))  # dummy avoid div0
    # (bu satır sadece gösterim amaçlıdır; fonksiyon çalışma mantığı bundan etkilenmez)

    # Çoklu deneme (global) - eğer belirli kura kombinasyonlarında yerleştirme takılırsa yeniden dene
    MAX_GLOBAL_RETRIES = 2000
    WEEK_RETRIES = 500

    for global_try in range(MAX_GLOBAL_RETRIES):
        remaining = set(matches)
        schedule = {w: [] for w in range(1, total_weeks + 1)}
        success = True

        for week in range(1, total_weeks + 1):
            assigned = False
            # Her hafta için WEEK_RETRIES defa farklı greedy deneme yap
            for wtry in range(WEEK_RETRIES):
                rem_list = list(remaining)
                random.shuffle(rem_list)
                week_assigned = []
                used = set()
                for (a, b) in rem_list:
                    if len(week_assigned) >= matches_per_week:
                        break
                    if a not in used and b not in used:
                        week_assigned.append((a, b))
                        used.update([a, b])
                if len(week_assigned) == matches_per_week:
                    # Başarılı hafta yerleştirmesi
                    schedule[week] = week_assigned
                    for m in week_assigned:
                        remaining.discard(tuple(sorted(m)))
                    assigned = True
                    break
            if not assigned:
                success = False
                break

        if success and not remaining:
            return schedule

    # Eğer buraya gelindiyse, belirlenen denemelerde yerleştirme sağlanamadı
    raise RuntimeError("Fikstür oluşturulamadı: uygun dağılım bulunamadı (denendi).")


# -------------------------
# Mevcut sezon (en güncel active sezon)
# -------------------------
seasons = supabase.table("seasons").select("*").eq("active", True).order("id", desc=True).limit(1).execute()
season = seasons.data[0] if seasons.data else None
season_id = season['id'] if season else None

# -------------------------
# State vars defaults
# -------------------------
if 'weeks' not in st.session_state:
    st.session_state['weeks'] = {}
if 'scores' not in st.session_state:
    st.session_state['scores'] = {}
if 'opponents' not in st.session_state:
    st.session_state['opponents'] = {}
if 'matches_loaded' not in st.session_state:
    st.session_state['matches_loaded'] = False

# -------------------------
# DB'den yükleme fonksiyonu
# -------------------------
def load_matches_into_state():
    """DB'deki mevcut season_id için tüm maçları çek ve session_state'i overwrite et."""
    if not season_id:
        return
    st.session_state['weeks'] = {}
    st.session_state['scores'] = {}

    res = supabase.table("matches").select("*").eq("season_id", season_id).order("week", desc=False).execute()
    matches = res.data if hasattr(res, "data") else (res.get("data") if isinstance(res, dict) else [])

    for m in matches:
        week = m['week']
        st.session_state['weeks'].setdefault(week, [])
        pair = (m['home_team'], m['away_team'])
        if pair not in st.session_state['weeks'][week]:
            st.session_state['weeks'][week].append(pair)

        key = (m['home_team'], m['away_team'], week)
        home_db = "-" if m.get('score_home') is None else str(m.get('score_home'))
        away_db = "-" if m.get('score_away') is None else str(m.get('score_away'))

        st.session_state['scores'][key] = (home_db, away_db)

        # selectbox keylerine kesin olarak yaz (overwrite)
        sel_home_key = keyify(m['home_team'], m['away_team'], week, "home")
        sel_away_key = keyify(m['home_team'], m['away_team'], week, "away")


# İlk yükleme (only once per session, veya matches_loaded False ise)
if season_id and not st.session_state.get('matches_loaded', False):
    load_matches_into_state()
    st.session_state['matches_loaded'] = True

# -------------------------
# Admin kontrolü
# -------------------------
if "admin_logged_in" not in st.session_state:
    st.session_state["admin_logged_in"] = False
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

with st.sidebar:
    st.subheader("Admin Girişi")
    password = st.text_input("Parola", type="password")
    if st.button("Giriş Yap"):
        if password == "1":
            st.session_state["admin_logged_in"] = True
            st.session_state["is_admin"] = True
            st.success("Admin olarak giriş yapıldı")
        else:
            st.session_state["admin_logged_in"] = False
            st.session_state["is_admin"] = False
            st.error("Hatalı parola")

# -------------------------
# Görseller
# -------------------------
background_path = "images/arkaplan.jpg"
background_img = Image.open(background_path)
logo_path = "images/logo.png"
logo_img = Image.open(logo_path)

bg_base64 = img_to_base64(background_img)
logo_base64 = img_to_base64(logo_img)

# -------------------------
# CSS
# -------------------------
# -------------------------
# CSS
# -------------------------
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
    box-shadow: 0 0 25px rgba(0, 150, 255,0.5);
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

st.markdown("""
<style>
/* Fikstür kartları */
.fixtur-week-card {
    background: rgba(10,10,40,0.7);
    backdrop-filter: blur(6px);
    border-radius: 15px;
    padding: 15px;
    margin: 10px 0;
    border: 1px solid rgba(255,255,255,0.2);
    box-shadow: 0 0 15px rgba(0, 100, 255, 0.5);
}
.fixtur-match {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 6px 0;
}
.fixtur-team {
    font-weight: bold;
    color: #ffffff;
    padding: 6px 12px;
    border-radius: 12px;
    background: rgba(0, 150, 255, 0.3);
    text-align: center;
    min-width: 120px;
}
.fixtur-vs {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}

/* Maç sonuçları kartları */
.match-week-card {
    background: rgba(20,20,50,0.65);
    backdrop-filter: blur(6px);
    border-radius: 15px;
    padding: 12px;
    margin: 8px 0;
    border: 1px solid rgba(255,255,255,0.2);
    box-shadow: 0 0 12px rgba(0, 120, 255, 0.5);
}
.match-card {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 6px 0;
}
.match-team {
    font-weight: bold;
    color: #ffffff;
    padding: 6px 10px;
    border-radius: 12px;
    background: rgba(0, 150, 255, 0.3);
    min-width: 110px;
    text-align: center;
}
.match-score {
    font-weight: bold;
    color: #ffffff;
    font-size: 16px;
}
</style>
""", unsafe_allow_html=True)
st.markdown(f"""
<style>
.stApp {{
    background-image: url("data:image/png;base64,{bg_base64}");
    background-size: cover;
    background-repeat: no-repeat;
    background-position: center;
    color: white;
}}
</style>
""", unsafe_allow_html=True)



# -------------------------
# Sekmeler
# -------------------------
tabs = st.tabs(["Kura Çek", "Fikstür", "Maç Sonuçları", "Puan Durumu"])

# -------------------------
# Kura Çek
# -------------------------
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


    if st.session_state["admin_logged_in"]:
        if st.button("🎲 Kura Çek") and teams:
            opponents, all_matches = draw_opponents(teams)
            st.session_state['opponents'] = opponents
            st.session_state['all_matches'] = all_matches

            # Yeni sezon ekle
            season_count = supabase.table("seasons").select("id", count="exact").execute().count
            season_name = f"Sezon {season_count + 1}"
            new_season = supabase.table("seasons").insert({
                "name": season_name,
                "active": True
            }).execute()
            season_id = new_season.data[0]['id']

            # Session state sıfırla
            st.session_state['weeks'] = {}
            st.session_state['scores'] = {}
            st.session_state['matches_loaded'] = False

            # 🎯 Yeni: kura sonucuna göre fikstür oluştur
            players = teams
            draw_pairs = list(all_matches)
            st.session_state['weeks'] = create_schedule_from_draw(players, draw_pairs, total_weeks=8)

            # DB'ye ekle
            for week, week_matches in st.session_state['weeks'].items():
                for m in week_matches:
                    exists = supabase.table("matches").select("*") \
                        .eq("home_team", m[0]).eq("away_team", m[1]) \
                        .eq("week", week).eq("season_id", season_id).execute()
                    if not exists.data:
                        supabase.table("matches").insert({
                            "home_team": m[0],
                            "away_team": m[1],
                            "week": week,
                            "season_id": season_id,
                            "score_home": None,
                            "score_away": None
                        }).execute()
                    sel_home_key = keyify(m[0], m[1], week, "home")
                    sel_away_key = keyify(m[0], m[1], week, "away")
                    st.session_state[sel_home_key] = "-"
                    st.session_state[sel_away_key] = "-"
                    st.session_state['scores'][(m[0], m[1], week)] = ("-", "-")

            st.session_state['matches_loaded'] = True
            st.success(f"Kura başarıyla çekildi ve '{season_name}' başlatıldı!")

    if 'opponents' in st.session_state:
        st.subheader("🎯 Takımlar ve Rakipleri")
        for team, opps in st.session_state['opponents'].items():
            st.markdown('<div class="team-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="team-name">{team}</div>', unsafe_allow_html=True)
            for opp in opps:
                st.markdown(f'<div class="opponent">⚽ {opp}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# Fikstür
# -------------------------
with tabs[1]:
    if season_id and 'weeks' in st.session_state and st.session_state['weeks']:
        for week, week_matches in st.session_state['weeks'].items():
            st.markdown(f"<div class='fixtur-week-card'><h3>Hafta {week}</h3>", unsafe_allow_html=True)
            for m in week_matches:
                col1, col2, col3 = st.columns([2,1,2])
                with col1:
                    st.markdown(f'<div class="fixtur-team">{m[0]}</div>', unsafe_allow_html=True)
                with col2:
                    st.markdown(f'<div class="fixtur-vs" style="text-align:center;">➖</div>', unsafe_allow_html=True)
                with col3:
                    st.markdown(f'<div class="fixtur-team">{m[1]}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    if 'opponents' in st.session_state:
        if 'weeks' not in st.session_state:
            # fallback - nadiren çalışır
            pass

        st.subheader("📅 Haftalık Fikstür")
        csv_rows = []
        for week, week_matches in st.session_state['weeks'].items():
            st.markdown(f"### Hafta {week}")
            for m in week_matches:
                st.write(f"{m[0]} ➖ {m[1]}")
                csv_rows.append({"Hafta": week, "Ev Sahibi": m[0], "Deplasman": m[1]})
        df_fixtur = pd.DataFrame(csv_rows)
        csv_bytes = df_fixtur.to_csv(index=False).encode()
        st.download_button("📥 Fikstürü CSV olarak indir", data=csv_bytes, file_name="fikstur.csv", mime="text/csv")
    else:
        st.info("Önce 'Kura Çek' sekmesinden kura çekin.")

# -------------------------
# Maç Sonuçları
# -------------------------
with tabs[2]:
    if 'weeks' in st.session_state and st.session_state['weeks']:
        for week in sorted(st.session_state['weeks'].keys()):
            week_matches = st.session_state['weeks'][week]

            # Admin değilse modern kart görünümü
            if not st.session_state.get("admin_logged_in"):
                st.markdown(f'<div class="match-week-card"><h4>Hafta {week}</h4>', unsafe_allow_html=True)
                for m in week_matches:
                    pair_key = (m[0], m[1], week)
                    g1, g2 = st.session_state['scores'].get(pair_key, ("-", "-"))

                    col1, col2, col3 = st.columns([2, 1, 2])

                    with col1:
                        st.markdown(f'<div class="match-team">{m[0]}</div>', unsafe_allow_html=True)
                    with col2:
                        st.markdown(f'<div class="match-score" style="text-align:center;">{g1} ➖ {g2}</div>',
                                    unsafe_allow_html=True)
                    with col3:
                        st.markdown(f'<div class="match-team">{m[1]}</div>', unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)
                continue  # Admin kısmını atla

            # Admin görünümü (mevcut kodun aynısı)
            for m in week_matches:
                pair_key = (m[0], m[1], week)
                sel_home_key = keyify(m[0], m[1], week, "home")
                sel_away_key = keyify(m[0], m[1], week, "away")

                col1, col2, col3 = st.columns([2,1,2])

                g1_db, g2_db = st.session_state['scores'].get(pair_key, ("-", "-"))
                options = ["-"] + [str(i) for i in range(51)]

                with col1:
                    g1 = st.selectbox(label=m[0], options=options,
                                      index=options.index(g1_db) if g1_db in options else 0,
                                      key=sel_home_key)
                with col2:
                    st.write("➖")
                with col3:
                    g2 = st.selectbox(label=m[1], options=options,
                                      index=options.index(g2_db) if g2_db in options else 0,
                                      key=sel_away_key)

                st.session_state['scores'][pair_key] = (g1, g2)

    # Admin için sabit "Skorları Kaydet" butonu
    if st.session_state.get("admin_logged_in"):
        st.markdown("""
            <style>
            .fixed-save-btn {
                position: fixed;
                bottom: 20px;
                right: 20px;
                z-index: 9999;
            }
            </style>
        """, unsafe_allow_html=True)

        save_col = st.container()
        with save_col:
            if st.button("💾 Skorları Kaydet", key="kaydet_fixed"):
                any_error = False
                for week, week_matches in st.session_state['weeks'].items():
                    for m in week_matches:
                        sel_home_key = keyify(m[0], m[1], week, "home")
                        sel_away_key = keyify(m[0], m[1], week, "away")

                        g1 = st.session_state.get(sel_home_key, "-")
                        g2 = st.session_state.get(sel_away_key, "-")

                        db_home = None if g1 == "-" else int(g1)
                        db_away = None if g2 == "-" else int(g2)

                        try:
                            supabase.table("matches").update({
                                "score_home": db_home,
                                "score_away": db_away
                            }).eq("home_team", m[0]).eq("away_team", m[1]).eq("week", week).eq("season_id", season_id).execute()
                        except Exception as e:
                            any_error = True
                            st.error(f"DB güncelleme hatası: {e}")

                        st.session_state['scores'][(m[0], m[1], week)] = (g1, g2)

                st.session_state['matches_loaded'] = False
                load_matches_into_state()
                st.session_state['matches_loaded'] = True

                if any_error:
                    st.error("Bazı güncellemelerde hata oluştu.")
                else:
                    st.success("Skorlar kaydedildi ve yenilendi ✅")



# -------------------------
# Puan Durumu
# -------------------------
with tabs[3]:
    if season_id:
        # DB'den skorları al
        matches_db = supabase.table("matches").select("*").eq("season_id", season_id).execute()
        for m in matches_db.data:
            key = (m['home_team'], m['away_team'], m['week'])
            home = str(m['score_home']) if m['score_home'] is not None else "-"
            away = str(m['score_away']) if m['score_away'] is not None else "-"
            st.session_state['scores'][key] = (home, away)

        # Logo ve başlık
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

        # Takımları DB'den al
        teams = set()
        for row in matches_db.data:
            teams.add(row['home_team'])
            teams.add(row['away_team'])
        teams = list(teams)

        # Puan, galibiyet, vs hesapla
        points = {t: 0 for t in teams}
        wins = {t: 0 for t in teams}
        draws = {t: 0 for t in teams}
        losses = {t: 0 for t in teams}
        goals_for = {t: 0 for t in teams}
        goals_against = {t: 0 for t in teams}

        for (t1, t2, _), (g1, g2) in st.session_state['scores'].items():
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

        # Tablo oluştur
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

        df_table = pd.DataFrame(table_data, columns=["Takım","O","G","B","M","A","Y","AV","P"])
        if not df_table.empty:
            df_table = df_table.sort_values(by=["P","AV","A"], ascending=[False, False, False]).reset_index(drop=True)
            df_table.insert(0, "Sıra", df_table.index + 1)

            # --- SENİN RENKLEME AYARLARIN ---
            # Satır arka plan renkleri (aynı kalıyor)
            def color_row(row):
                pos = row.name + 1
                if 1 <= pos <= 8:
                    return ["background-color: rgba(0,255,0,0.2);"] * len(row)
                elif 9 <= pos <= 24:
                    return ["background-color: rgba(255,215,0,0.2);"] * len(row)
                elif 25 <= pos <= 36:
                    return ["background-color: rgba(255,0,0,0.2);"] * len(row)
                return [""] * len(row)


            # Takım isimleri beyaz
            def color_team(val):
                return "color: #ffffff; font-weight:bold;"


            # Diğer tüm sayı sütunları beyaz
            def color_numbers_white(val):
                return "color: white; font-weight:bold;"


            styled = (df_table.style
                      .apply(color_row, axis=1)  # satır arka plan renkleri
                      .applymap(color_team, subset=["Takım"])  # takım isimleri
                      .applymap(color_numbers_white, subset=["O", "G", "B", "M", "A", "Y", "AV", "P"])  # sayılar beyaz
                      .set_table_styles([
                {"selector": "th", "props": [("text-align", "center"),
                                             ("background-color", "rgba(0,0,50,0.8)"),
                                             ("color", "#FFD700"),
                                             ("border", "1px solid #00e5ff")]},
                {"selector": "td", "props": [("text-align", "center"),
                                             ("border", "1px solid #00e5ff")]}
            ])
                      .hide(axis="index")
                      )

            html_table = styled.to_html(index=False)
            st.markdown(f"<div style='display:flex; justify-content:center;'>{html_table}</div>",
                        unsafe_allow_html=True)
        else:
            st.info("Henüz skor girilmedi veya fikstür oluşturulmadı.")

