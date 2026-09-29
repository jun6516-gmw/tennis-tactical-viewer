import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.font_manager as fm

# OS依存のない日本語フォント設定
JP_FONTS = [
    'Yu Gothic', 'Meiryo', 'MS Gothic',           # Windows
    'Hiragino Sans', 'Hiragino Kaku Gothic ProN', # Mac
    'Noto Sans CJK JP', 'TakaoGothic', 'IPAGothic'# Linux / Ubuntu
]
available_fonts = {f.name for f in fm.fontManager.ttflist}
for font in JP_FONTS:
    if font in available_fonts:
        plt.rcParams['font.family'] = font
        break

# ページ設定
st.set_page_config(page_title="Tennis Match Tactical Visualizer", layout="wide")

st.title("🎾 テニス戦術分析ダッシュボード")
st.caption("SwingVisionのデータから、1ポイントごとのボール軌跡・得失点文脈を可視化します")

# 英語/日本語の表示変換辞書
STROKE_MAP = {
    'サーブ': 'Serve',
    'フォアハンド': 'Forehand',
    'バックハンド': 'Backhand',
    'フォアハンド ボレー': 'FH Volley',
    'バックハンド ボレー': 'BH Volley',
    'スマッシュ': 'Smash',
    'ドロップ': 'Drop Shot',
    'フィード': 'Feed'
}

RESULT_MAP = {
    'イン': 'IN',
    'アウト': 'OUT',
    'ネット': 'NET'
}

def translate_stroke(stroke):
    return STROKE_MAP.get(str(stroke), str(stroke))

def translate_result(result):
    return RESULT_MAP.get(str(result), str(result))

# サイドバー: ファイル読み込み
st.sidebar.header("📁 データ読み込み")
uploaded_file = st.sidebar.file_uploader("SwingVisionファイルを選択 (.xlsx / .csv)", type=["xlsx", "csv"])

if uploaded_file is None:
    st.info("👈 左側のサイドバーから SwingVision のデータファイル（Excel または CSV）をアップロードしてください。")
    st.stop()

@st.cache_data
def load_data(file):
    if file.name.endswith(".xlsx"):
        xls = pd.ExcelFile(file)
        if "Shots" in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name="Shots")
        else:
            df = pd.read_excel(xls, sheet_name=0)
    else:
        df = pd.read_csv(file)
    return df

try:
    shots_df = load_data(uploaded_file)
except Exception as e:
    st.error(f"ファイルの読み込みに失敗しました: {e}")
    st.stop()

required_cols = ['Point', 'Shot', 'Player', 'Stroke', 'Speed (KM/H)', 'Bounce (x)', 'Bounce (y)', 'Hit (x)', 'Hit (y)', 'Result']
missing_cols = [c for c in required_cols if c not in shots_df.columns]
if missing_cols:
    st.error(f"必要なカラムが見つかりません: {missing_cols}")
    st.stop()

players = [p for p in shots_df['Player'].dropna().unique().tolist() if str(p).strip()]
if not players:
    st.error("Playerデータが存在しません。")
    st.stop()

st.sidebar.header("👤 プレイヤー視点設定")
target_player = st.sidebar.selectbox("手前側に固定するプレイヤーを選択", players, index=0)

# ポイントサマリー作成
@st.cache_data
def analyze_points(df, focus_player):
    points_data = []
    grouped = df.groupby('Point')
    
    for point_id, group in grouped:
        group_sorted = group.sort_values('Shot')
        last_shot = group_sorted.iloc[-1]
        
        last_player = str(last_shot['Player'])
        last_stroke = translate_stroke(last_shot['Stroke'])
        last_res = translate_result(last_shot['Result'])
        total_shots = len(group_sorted)
        
        if last_player == focus_player:
            outcome = "得点 (Winner)" if last_res == "IN" else "失点 (自滅エラー)"
        else:
            outcome = "得点 (相手ミス)" if last_res in ["OUT", "NET"] else "失点 (相手Winner)"
            
        detail = f"{last_player}: {last_stroke} -> {last_res}"
        
        points_data.append({
            'Point': int(point_id),
            'Total_Shots': total_shots,
            'Outcome': outcome,
            'Last_Player': last_player,
            'Last_Stroke': last_stroke,
            'Last_Result': last_res,
            'Detail': detail
        })
    return pd.DataFrame(points_data)

points_summary_df = analyze_points(shots_df, target_player)

# 絞り込みフィルター
st.sidebar.header("🔍 ポイント絞り込み")
all_outcomes = [
    "得点 (Winner)",
    "得点 (相手ミス)",
    "失点 (自滅エラー)",
    "失点 (相手Winner)"
]
outcome_filter = st.sidebar.multiselect(
    "勝敗結果で絞り込み",
    options=all_outcomes,
    default=all_outcomes
)

min_shots = int(points_summary_df['Total_Shots'].min())
max_shots = int(points_summary_df['Total_Shots'].max())
shot_range = st.sidebar.slider("ラリー打数で絞り込み", min_shots, max_shots, (min_shots, max_shots))

filtered_points = points_summary_df[
    (points_summary_df['Outcome'].isin(outcome_filter)) &
    (points_summary_df['Total_Shots'] >= shot_range[0]) &
    (points_summary_df['Total_Shots'] <= shot_range[1])
]

if filtered_points.empty:
    st.warning("条件に一致するポイントがありません。フィルター条件を緩和してください。")
    st.stop()

point_list = filtered_points['Point'].tolist()

# ----------------------------------------------------
# ポイント選択 & マウスホイール連動コントローラー
# ----------------------------------------------------
st.sidebar.header("🎯 ポイント選択")

# session_state の初期化
if "current_point_idx" not in st.session_state:
    st.session_state.current_point_idx = 0

# フィルター変更時にインデックスが範囲外にならないよう補正
if st.session_state.current_point_idx >= len(point_list):
    st.session_state.current_point_idx = 0

# 1. ドロップダウン（既存のSelect Point #）
def on_selectbox_change():
    chosen_pt = st.session_state.sb_point
    st.session_state.current_point_idx = point_list.index(chosen_pt)

selected_point_sb = st.sidebar.selectbox(
    "Select Point # (リストから選択)",
    options=point_list,
    index=st.session_state.current_point_idx,
    key="sb_point",
    on_change=on_selectbox_change
)

# 2. マウスホイール操作用コントローラー (マウスを乗せてローラーを回す)
def on_wheel_change():
    st.session_state.current_point_idx = int(st.session_state.wheel_idx)

st.sidebar.markdown(
    """<small style='color: #94a3b8;'>
    💡 <b>マウスローラー操作:</b> 下の枠の上にカーソルを乗せてホイールを回すと前後に移動できます。
    </small>""", 
    unsafe_allow_html=True
)

wheel_input = st.sidebar.number_input(
    f"Point Index (0 〜 {len(point_list)-1})",
    min_value=0,
    max_value=len(point_list)-1,
    value=st.session_state.current_point_idx,
    step=1,
    key="wheel_idx",
    on_change=on_wheel_change,
    help="枠内にマウスを乗せてホイールを回転させるとポイントが素早く切り替わります。"
)

# 現在選択されたポイント番号
selected_point = point_list[st.session_state.current_point_idx]

st.sidebar.header("🎨 表示モード")
view_mode = st.sidebar.radio(
    "描画モード",
    ["全ラリー表示", "決着ラスト2打のみ表示"],
    index=0
)

# 選択ポイントのショットデータ
p_shots = shots_df[shots_df['Point'] == selected_point].sort_values('Shot').copy()
p_info = points_summary_df[points_summary_df['Point'] == selected_point].iloc[0]

# 画面レイアウト
col1, col2 = st.columns([1, 2])

with col1:
    st.subheader(f"📌 Point {selected_point} 概要")
    st.metric(label="結果", value=p_info['Outcome'])
    st.write(f"**ラリー打数:** {p_info['Total_Shots']} 打")
    st.write(f"**決着展開:** {p_info['Detail']}")
    
    st.write("---")
    st.write("##### ショット詳細")
    
    display_df = p_shots.copy()
    display_df['Stroke'] = display_df['Stroke'].apply(translate_stroke)
    display_df['Result'] = display_df['Result'].apply(translate_result)
    
    cols_to_show = ['Shot', 'Player', 'Stroke', 'Speed (KM/H)', 'Direction', 'Result']
    st.dataframe(display_df[[c for c in cols_to_show if c in display_df.columns]], use_container_width=True, hide_index=True)

with col2:
    NET_Y = 11.885
    
    # 手前固定プレイヤーの判定
    focal_shots = p_shots[p_shots['Player'] == target_player]
    is_far = False
    if not focal_shots.empty:
        if focal_shots['Hit (y)'].mean() > NET_Y:
            is_far = True
            
    records = []
    for idx, row in p_shots.iterrows():
        s_num = int(row['Shot'])
        hx, hy = row['Hit (x)'], row['Hit (y)']
        bx, by = row['Bounce (x)'], row['Bounce (y)']
        if is_far:
            hx, hy = -hx, 23.77 - hy
            bx, by = -bx, 23.77 - by
        records.append({
            'shot': s_num,
            'player': str(row['Player']),
            'stroke': translate_stroke(row['Stroke']),
            'speed': row['Speed (KM/H)'],
            'result': translate_result(row['Result']),
            'hx': hx, 'hy': hy, 'bx': bx, 'by': by
        })
        
    if view_mode == "決着ラスト2打のみ表示":
        records = records[-min(2, len(records)):]
        
    fig, ax = plt.subplots(figsize=(7, 12), facecolor='#0f172a')
    ax.set_facecolor('#0f172a')
    
    # コート枠
    rect_court = patches.Rectangle((-5.485, 0), 10.97, 23.77, linewidth=2, edgecolor='#64748b', facecolor='#1e3a8a', alpha=0.9)
    ax.add_patch(rect_court)
    rect_singles = patches.Rectangle((-4.115, 0), 8.23, 23.77, linewidth=1.5, edgecolor='#cbd5e1', facecolor='none')
    ax.add_patch(rect_singles)
    
    # ネット線
    ax.plot([-5.8, 5.8], [NET_Y, NET_Y], color='#ffffff', linewidth=3.0, zorder=10)
    ax.text(6.0, NET_Y, 'NET', color='#ffffff', verticalalignment='center', fontsize=9, fontweight='bold')
    
    # ライン
    ax.plot([-4.115, 4.115], [5.485, 5.485], color='#94a3b8', linewidth=1.5)
    ax.plot([-4.115, 4.115], [18.285, 18.285], color='#94a3b8', linewidth=1.5)
    ax.plot([0, 0], [5.485, 18.285], color='#94a3b8', linewidth=1.5)
    ax.plot([0, 0], [0, 0.4], color='#cbd5e1', linewidth=1.5)
    ax.plot([0, 0], [23.37, 23.77], color='#cbd5e1', linewidth=1.5)
    
    color_focal = '#38bdf8'     # 手前プレイヤー: 青
    color_opp = '#fb923c'       # 相手プレイヤー: 橙
    color_net_miss = '#ef4444'  # ネットミス: 赤
    
    for i, cur in enumerate(records):
        c = color_focal if cur['player'] == target_player else color_opp
        is_net = (cur['result'] == 'NET')
        target_x, target_y = cur['bx'], cur['by']
        annotation_c = c
        
        # ネットミス延長処理
        if is_net:
            hx, hy = cur['hx'], cur['hy']
            bx, by = cur['bx'], cur['by']
            target_y = NET_Y
            if hy != by:
                target_x = hx + (bx - hx) * (NET_Y - hy) / (by - hy)
            annotation_c = color_net_miss
            
        ls_arrow = '-' if (cur['result'] == 'IN' or is_net) else '--'
        ax.annotate(
            '', xy=(target_x, target_y), xytext=(cur['hx'], cur['hy']),
            arrowprops=dict(arrowstyle="->,head_width=0.35,head_length=0.5",
                            color=annotation_c, lw=2.2, alpha=0.95, linestyle=ls_arrow)
        )
        
        # ヒット位置
        if cur['shot'] == 1:
            ax.plot(cur['hx'], cur['hy'], marker='o', markersize=13, color='#eab308', markeredgecolor='#ffffff', markeredgewidth=2, zorder=5)
            ax.plot(cur['hx'], cur['hy'], marker='o', markersize=7, color=c, zorder=6)
            ax.text(cur['hx'], cur['hy'] - 0.7 if cur['hy'] < NET_Y else cur['hy'] + 0.7,
                    '★SERVE', color='#fde047', fontsize=8, fontweight='bold', ha='center', va='center',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#000000', edgecolor='#fde047', alpha=0.85))
        else:
            ax.plot(cur['hx'], cur['hy'], marker='o', markersize=7, color=c, markeredgecolor='#ffffff', markeredgewidth=1, zorder=4)
            
        # バウンド位置 / ネット位置
        if is_net:
            ax.plot(target_x, target_y, marker='X', markersize=16, color=color_net_miss, markeredgecolor='#ffffff', markeredgewidth=2, zorder=11)
        else:
            b_marker = '*' if cur['result'] == 'IN' else 'x'
            ax.plot(target_x, target_y, marker=b_marker, markersize=11, color=annotation_c, markeredgecolor='#ffffff', markeredgewidth=1.5, zorder=4)
            
        # バウンドから次の打点への点線
        if i + 1 < len(records) and not is_net:
            nxt = records[i+1]
            ax.annotate(
                '', xy=(nxt['hx'], nxt['hy']), xytext=(cur['bx'], cur['by']),
                arrowprops=dict(arrowstyle="->,head_width=0.25,head_length=0.4",
                                color=c, lw=1.5, alpha=0.6, linestyle=':')
            )
            
        # ショットラベル
        offset_y = 0.55 if cur['hy'] < target_y else -0.55
        label_c = annotation_c if is_net else '#ffffff'
        bbox_c = color_net_miss if is_net else '#1e293b'
        
        player_tag = "Me" if cur['player'] == target_player else "Opponent"
        label_text = f"#{cur['shot']} {player_tag}\n{cur['stroke']} ({cur['speed']:.0f}km/h)"
        if is_net:
            label_text += "\n[NET]"
        elif cur['result'] == 'OUT':
            label_text += "\n[OUT]"
            
        ax.text(target_x, target_y + offset_y, label_text, color=label_c, fontsize=7.5,
                ha='center', va='center', zorder=7,
                bbox=dict(boxstyle='round,pad=0.25', facecolor='#0f172a', edgecolor=bbox_c, alpha=0.9))

    # 手前・奥のラベル
    ax.text(0, -2.0, f"手前 (NEAR): {target_player}", color='#38bdf8', fontsize=12, fontweight='bold', ha='center')
    ax.text(0, 25.2, "奥 (FAR): 対戦相手", color='#fb923c', fontsize=12, fontweight='bold', ha='center')

    ax.set_xlim(-6.5, 6.5)
    ax.set_ylim(-3.5, 27)
    ax.set_aspect('equal')
    ax.axis('off')
    
    st.pyplot(fig)