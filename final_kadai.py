import streamlit as st
import pandas as pd
import google.generativeai as genai
import re
import json
import os

# --- ページ設定 ---
st.set_page_config(page_title="視聴管理アプリ with Gemini", page_icon="📺")
st.title("📺 視聴管理アプリ")
st.markdown("視聴した作品の内容と感想を登録しましょう!")

# --- 定数定義 ---
# 保存するデータファイルの名前
DATA_FILE = "works_data.json"

# --- APIキー設定 ---
try:
    # Streamlitのシークレット管理からAPIキーを取得
    api_key = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)
except (KeyError, AttributeError):
    st.error("⚠️ Gemini APIキーが設定されていません。st.secretsに 'GEMINI_API_KEY' を設定してください。")
    st.stop()

# --- データ保存・読み込み関数 ---
def save_data(data):
    """
    視聴履歴データをJSONファイルに保存する関数
    """
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_data():
    """
    JSONファイルから視聴履歴データを読み込む関数
    """
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            # ファイルが空または破損している場合は空のリストを返す
            return []
    return []

# --- Gemini AIによる作品情報取得関数 ---
def get_work_info_with_gemini(title: str) -> tuple[str, int, str]:
    """
    Gemini AIを使用して、与えられた映像作品の基本情報を取得します。
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = f"""あなたは映像作品情報のエキスパートです。以下の映像作品のタイトルについて、指定された形式で情報を教えてください。
    
    作品タイトル: {title}

    以下の3つの情報を、必ず区切り文字「|||」で区切って出力してください。
    1. 視聴時間の概要（例: 全12話、各話約24分 / 映画 124分）
    2. シリーズ全体の総視聴時間（分単位の整数のみ。例: 288）
    3. 一般的な評価や評判の概要（200文字程度）

    出力形式の例:
    全28話、1話約24分|||672|||非常に高い評価を受けており、多くのレビューサイトで満点に近いスコアを記録しています。特に、感動的なストーリーとキャラクターの深い心理描写が称賛されています。
    """

    try:
        response = model.generate_content(prompt)
        parts = response.text.split('|||')
        if len(parts) == 3:
            viewing_time_summary = parts[0].strip()
            total_minutes_str = re.search(r'\d+', parts[1])
            total_minutes = int(total_minutes_str.group()) if total_minutes_str else 0
            reputation = parts[2].strip()
            return viewing_time_summary, total_minutes, reputation
        else:
            return "情報取得失敗", 0, "AIからの応答形式が正しくありませんでした。"
    except Exception as e:
        st.error(f"AIによる情報取得中にエラーが発生しました: {e}")
        return "情報取得失敗", 0, "APIエラーが発生しました。"

# --- Gemini AIによる分析・提案関数 ---
def analyze_with_gemini(prompt: str) -> str:
    """
    与えられたプロンプトに基づいてGemini AIで分析や提案を生成します。
    """
    model = genai.GenerativeModel('gemini-1.5-flash')
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"AIとの通信中にエラーが発生しました: {e}")
        return "分析・提案の生成に失敗しました。"

# --- セッションステートの初期化 ---
# アプリの初回起動時のみファイルからデータを読み込む
if "works" not in st.session_state:
    st.session_state.works = load_data()


# --- 入力フォーム ---
st.subheader("✍️ 新しい視聴記録を登録")
with st.form("work_form", clear_on_submit=True):
    title = st.text_input("作品タイトル", placeholder="例：葬送のフリーレン")
    category = st.selectbox("分類", ["アニメ", "映画", "ドラマ", "特撮", "その他"], help="作品の分類を選択してください")
    impression = st.text_area("感想", height=100, placeholder="例：映像が綺麗で、キャラクターの感情が丁寧に描かれていて感動した。")
    user_rating = st.slider("あなたの評価", 1, 5, 3, help="5段階で評価してください（1:悪い - 5:最高）")
    submit_button = st.form_submit_button("登録する", help="視聴記録を登録します。Gemini AIが情報を取得します。")


# --- 登録処理 ---
if submit_button and title:
    with st.spinner(f"Gemini AIが「{title}」の情報を調べています..."):
        viewing_time_summary, total_minutes, reputation = get_work_info_with_gemini(title)
    
    if total_minutes > 0:
        st.session_state.works.append({
            "タイトル": title,
            "分類": category,
            "感想": impression,
            "あなたの評価": "★" * user_rating,
            "評価(数値)": user_rating,
            "視聴時間(概要)": viewing_time_summary,
            "総視聴時間(分)": total_minutes,
            "一般的な評価": reputation
        })
        # データを追加した直後にファイルに保存
        save_data(st.session_state.works)
        st.success(f"「{title}」の記録を登録しました！")
        st.balloons()
    else:
        st.error(f"「{title}」の情報を取得できませんでした。作品名が正しいか確認してください。")

# --- 登録済み一覧表示 ---
if st.session_state.works:
    st.subheader("🎞️ 視聴履歴")
    
    df = pd.DataFrame(st.session_state.works)
    
    # 各作品の詳細をエキスパンダーで表示
    # インデックスを逆順にして新しいものが上にくるようにする
    for index in reversed(df.index):
        row = df.loc[index]
        with st.expander(f"**{row['タイトル']}** ({row['分類']} - {row['あなたの評価']})"):
            st.markdown("##### 🤖 AIによる作品情報")
            st.info(f"**一般的な評価:** {row['一般的な評価']}")
            st.markdown(f"**視聴時間の目安:** {row['視聴時間(概要)']} (合計 約{row['総視聴時間(分)']}分)")
            st.markdown("---")
            st.markdown("##### 💬 あなたの感想")
            if row['感想']:
                st.write(row['感想'])
            else:
                st.caption("感想は登録されていません。")
            
            # --- ここから削除機能 ---
            st.markdown("---")
            if st.button("この記録を削除する", key=f"delete_{index}", help="この視聴記録を削除します。"):
                # st.session_state.worksから該当の記録を削除
                st.session_state.works.pop(index)
                # 変更をファイルに保存
                save_data(st.session_state.works)
                st.success(f"「{row['タイトル']}」の記録を削除しました。")
                # 画面を再読み込みして表示を更新
                st.rerun()

    st.markdown("---")

    # --- 視聴時間の可視化 ---
    st.subheader("📊 視聴時間のグラフ")
    
    if not df.empty and "総視聴時間(分)" in df.columns:
        chart_df = df[["タイトル", "総視聴時間(分)"]].set_index("タイトル")
        st.bar_chart(chart_df)
        total_hours = df["総視聴時間(分)"].sum() / 60
        st.markdown(f"**合計視聴時間:** 約 **{total_hours:.1f}** 時間")
    else:
        st.warning("グラフを表示するためのデータがありません。")

    st.markdown("---")

    # --- ユーザーの好み分析とおすすめ機能 ---
    st.subheader("🤖 AIによる分析＆提案")
    st.markdown("登録した視聴履歴をもとに、あなたの好みを分析し、次に見るべき作品をおすすめします。")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("📈 あなたの好みを分析する"):
            with st.spinner("AIがあなたの好みを分析中です..."):
                work_list_str = ""
                for index, row in df.iterrows():
                    work_list_str += f"- 作品名: {row['タイトル']}, 分類: {row['分類']}, あなたの評価: {row['評価(数値)']}/5, 感想: {row['感想']}\n"

                prompt = f"""あなたはプロの映像作品アナリストです。
                以下の視聴履歴を持つユーザーの好みの傾向を分析し、簡潔にまとめてください。
                特に、評価が高い作品（評価4以上）に注目してください。
                どのようなジャンル、テーマ、作風、キャラクター像を好むかを具体的に分析してください。

                【ユーザーの視聴履歴】
                {work_list_str}

                【分析結果】
                """
                
                analysis_result = analyze_with_gemini(prompt)
                st.subheader("🔍 あなたの好み分析結果")
                st.success(analysis_result)

    with col2:
        if st.button("🎯 おすすめ作品を提案してもらう"):
            with st.spinner("AIがあなたにぴったりの作品を選んでいます..."):
                sorted_df = df.sort_values("評価(数値)", ascending=False)
                work_list_str = ""
                for index, row in sorted_df.iterrows():
                        work_list_str += f"- 作品名: {row['タイトル']}, 分類: {row['分類']}, あなたの評価: {row['評価(数値)']}/5\n"
                
                watched_titles = ", ".join(df['タイトル'].tolist())

                prompt = f"""あなたは優れた映像作品コンシェルジュです。
                以下の視聴履歴を持つユーザーの好みを踏まえて、次に見るべきおすすめの映像作品を3つ厳選して提案してください。
                提案する作品は、ユーザーがまだ見ていないものにしてください。
                それぞれの作品について、なぜおすすめなのか理由も50字程度で簡潔に付け加えてください。

                【ユーザーの視聴履歴】
                {work_list_str}

                【ユーザーが視聴済みの作品リスト（これらは提案しないでください）】
                {watched_titles}

                【出力形式の例】
                - **【作品名1】**: ユーザーの「〇〇」という好みに合っており、特に△△な点が楽しめるはずです。
                - **【作品名2】**: □□と似た雰囲気で、より深く××というテーマを掘り下げています。
                - **【作品名3】**: 高評価をつけた△△の監督の別作品で、きっと気に入ると思います。
                """
                
                recommendations = analyze_with_gemini(prompt)
                st.subheader("✨ あなたへのおすすめ作品")
                st.markdown(recommendations)
    
    st.markdown("---")
    
    # --- 全履歴削除機能 ---
    st.subheader("🗑️ 履歴の削除")
    if st.button("全ての履歴を削除する", type="primary", help="全ての視聴記録を削除します。この操作は元に戻せません。"):
        st.session_state.confirm_delete_all = True

    if st.session_state.get("confirm_delete_all"):
        st.warning("**本当に全ての視聴履歴を削除しますか？** この操作は元に戻せません。")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("はい、全て削除します", on_click=lambda: st.session_state.update({"confirm_delete_all": False})):
                st.session_state.works = []
                save_data([])
                st.success("全ての履歴を削除しました。")
                st.rerun()
        with c2:
            if st.button("キャンセル", on_click=lambda: st.session_state.update({"confirm_delete_all": False})):
                st.rerun()


else:
    st.info("まだ視聴記録がありません。上のフォームから最初の作品を登録してみましょう！")