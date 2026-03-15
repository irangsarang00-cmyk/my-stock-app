import urllib.parse
import streamlit as st
import pandas as pd
import gspread
import json
import tempfile
import os
import re
from google.oauth2.service_account import Credentials
from streamlit_google_auth import Authenticate

# --- 햄버거 메뉴 & 워터마크 영혼까지 끌어모아 암살하기 ---
hide_streamlit_style = """
<style>
[data-testid="stToolbar"] {display: none !important;}
[data-testid="collapsedControl"] {display: none !important;}
header[data-testid="stHeader"] {display: none !important;}
header {visibility: hidden !important;}
#MainMenu {display: none !important;}
footer {display: none !important;}
.block-container {padding-top: 1rem !important;}
[class^="viewerBadge"] {display: none !important;}
.viewerBadge_container__1tSll {display: none !important;}
.viewerBadge_link__qRIus {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
# ---------------------------------------------------------

# ==========================================================
# 1. 구글 로그인 및 보안 설정
# ==========================================================
WHITELIST_EMAILS = ["irangsarang00@gmail.com", "hiyokosan0314@gmail.com", "ddadung77@gmail.com", "a01066531205@gmail.com", "seohanseung2@gmail.com", "afopis75@gmail.com"]

auth_secrets = st.secrets["google_oauth"]

# secrets에서 임시 JSON 파일 생성 (Streamlit Cloud용)
credentials_dict = {
    "web": {
        "client_id": auth_secrets["client_id"],
        "client_secret": auth_secrets["client_secret"],
        "redirect_uris": ["https://my-stock-app-2dctlxmsqxehndw9vh79pp.streamlit.app"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
}

tmp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
json.dump(credentials_dict, tmp_file)
tmp_file.close()

# 로그인 유지 기간을 아주 길게(약 10년) 설정
authenticator = Authenticate(
    secret_credentials_path=tmp_file.name,
    cookie_name="stock_app_cookie",
    cookie_key="stock_app_secret_key_1234",
    redirect_uri="https://my-stock-app-2dctlxmsqxehndw9vh79pp.streamlit.app",
    cookie_expiry_days=3650
)

authenticator.check_authentification()

if not st.session_state.get("connected"):
    st.markdown("<div style='margin-top: 15vh;'></div>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center;'>가평창고 재고조회</h2>", unsafe_allow_html=True)
    
    # ✨ 로그인 화면에 접속 방법 안내 상자 추가
    st.info("""
    **💡 접속 및 설치 방법**
    1. 정이랑 주임에게 구글 이메일 아이디 전달해 주세요.
    2. 승인 완료되면 구글 아이디로 로그인하세요.
    3. 로그인 한 뒤, 크롬(갤럭시) or 사파리(아이폰)에서 '홈 화면에 추가'를 통해 바탕화면에 설치할 수 있습니다.
    """)

    client_id = auth_secrets["client_id"]
    redirect_uri = "https://my-stock-app-2dctlxmsqxehndw9vh79pp.streamlit.app"
    scope = "openid email profile"
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope={urllib.parse.quote(scope)}"

    st.markdown(f'''
        <div style="text-align: center; margin-top: 30px; margin-bottom: 30px;">
            <a href="{auth_url}" target="_blank" style="
                display: inline-block;
                padding: 12px 24px;
                background-color: #4285F4;
                color: white;
                text-decoration: none;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.2);
            ">🚀 구글 계정으로 로그인</a>
        </div>
    ''', unsafe_allow_html=True)

    os.unlink(tmp_file.name)
    st.stop()

os.unlink(tmp_file.name)

user_email = st.session_state.get("user_info", {}).get("email")
if user_email not in WHITELIST_EMAILS:
    st.error(f"접근 권한이 없습니다. ({user_email})")
    if st.button("로그아웃"):
        authenticator.logout()
    st.stop()

# ==========================================================
# [중요] 데이터 처리 함수 (병합 해결 & 유연한 필터링)
# ==========================================================
def get_incoming_schedule():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)

        sheet_url = "https://docs.google.com/spreadsheets/d/1J5RwYs3IVCm9f0IsCjwtrSerOGdx_J3f3r0o72BgrTA/edit"
        doc = gc.open_by_url(sheet_url)
        worksheet = doc.worksheet("시트2")

        raw_data = worksheet.get_all_values()
        df_raw = pd.DataFrame(raw_data)

        if df_raw.empty:
            return pd.DataFrame()

        # 1. 병합된 셀 해결 (위에서 아래로 빈칸 채우기)
        df_filled = df_raw.replace('', None).ffill()

        # 2. '상품전환'이라는 단어가 포함된 행은 미리 제거 (요청사항)
        # 행 전체를 검사해서 '상품전환'이 들어있으면 False 반환
        mask_product_change = df_filled.astype(str).apply(lambda x: x.str.contains('상품전환')).any(axis=1)
        df_filtered = df_filled[~mask_product_change] # ~은 제외(Not)를 의미

        # 3. '가평'이 포함된 행 필터링
        mask_gapyeong = df_filtered.astype(str).apply(lambda x: x.str.contains('가평')).any(axis=1)

        # 4. '날짜' 패턴이 포함된 행 필터링
        date_pattern = r'(\d{2,4}[.\-/]\d{1,2}[.\-/]\d{1,2})'
        mask_date = df_filtered.astype(str).apply(lambda x: x.str.contains(date_pattern)).any(axis=1)

        # 5. 최종 조건 만족 행 추출
        schedule_df = df_filtered[mask_gapyeong & mask_date].copy()

        # 6. 특정 열 숨김 처리 (0, 2, 4, 11, 12, 13 열 삭제)
        # 현재 열 번호를 기준으로 지울 열 리스트 (안전하게 실제 존재하는 열 번호만 타겟팅)
        cols_to_drop = [c for c in [0, 2, 4, 11, 12, 13] if c < len(schedule_df.columns)]
        schedule_df = schedule_df.drop(schedule_df.columns[cols_to_drop], axis=1)

        return schedule_df

    except Exception as e:
        st.error(f"스케줄을 불러오는 중 오류 발생: {e}")
        return pd.DataFrame()

# ==========================================================
# 2. 메인 화면 시작 (로그인 성공 후)
# ==========================================================

# ✨ 상단에 2개의 버튼(설치 안내 / 뷰어 목록)을 나란히 배치
col1, col2, col3 = st.columns([3, 3, 3])

with col1:
    # 로그인 후에도 설치 방법을 다시 확인할 수 있는 버튼
    with st.expander("📱 앱 설치 방법 안내"):
        st.markdown("""
        **💡 접속 및 설치 방법**
        1. 정이랑 주임에게 구글 이메일 아이디 전달해 주세요.
        2. 승인 완료되면 구글 아이디로 로그인하세요.
        3. 로그인 한 뒤, 크롬(갤럭시) or 사파리(아이폰)에서 '홈 화면에 추가'를 통해 바탕화면에 설치할 수 있습니다.
        """)

with col2:
    # 기존에 있던 뷰어 목록 버튼
    with st.expander("👥 접근 허용 명단"):
        for email in WHITELIST_EMAILS:
            st.caption(f"✔️ {email}")

with col3:
    # ✨ 입고스케줄 버튼 추가!
    show_schedule = st.button("🚛 입고스케줄")

# --- 입고스케줄 클릭 시 보여주는 로직 ---
if show_schedule:
    st.markdown("---")
    st.subheader("🗓️ 가평창고 입고 예정 리스트")
    with st.spinner('스케줄을 분석 중입니다...'):
        sched_data = get_incoming_schedule()
        
        if not sched_data.empty:
            # 깔끔하게 표로 출력 (성공 문구 제거됨)
            st.table(sched_data)
        else:
            st.warning("현재 예정된 가평 입고 스케줄이 없습니다.")
    st.markdown("---")

# ==========================================================
# 3. 실제 구글 시트 데이터 불러오기 함수
# ==========================================================
@st.cache_data(ttl=900)
def load_real_data():
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        creds_dict = st.secrets["gcp_service_account"]
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(credentials)

        sheet_url = "https://docs.google.com/spreadsheets/d/1J5RwYs3IVCm9f0IsCjwtrSerOGdx_J3f3r0o72BgrTA/edit?gid=0#gid=0"

        doc = gc.open_by_url(sheet_url)
        worksheet = doc.worksheet("시트1")

        data = worksheet.get_all_records()
        df = pd.DataFrame(data)

        if '품목코드' in df.columns:
            df['품목코드'] = df['품목코드'].astype(str).str.strip()
        if '품목명' in df.columns:
            df['품목명'] = df['품목명'].astype(str).str.strip()

        return df

    except Exception as e:
        st.error(f"시트를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

df = load_real_data()

# ==========================================================
# 4. 모바일 최적화 검색 화면
# ==========================================================

# ✨ 검색창을 모바일 중간으로 시원하게 내리기 (30vh로 증가)
st.markdown("<div style='margin-top: 30vh;'></div>", unsafe_allow_html=True)
st.markdown("<h3 style='text-align: center;'>상품명 또는 PL번호로 검색</h3>", unsafe_allow_html=True)

search_query = st.text_input("", label_visibility="collapsed")

if search_query and not df.empty:
    clean_query = search_query.strip()

    mask = (
        df['품목명'].str.contains(clean_query, case=False, na=False) |
        (df['품목코드'].str[-4:] == clean_query)
    )
    search_result = df[mask]

    if search_result.empty:
        st.warning("검색 결과가 없습니다. 다른 키워드로 검색해 보세요.")
    else:
        st.success(f"총 {len(search_result)}개의 품목이 검색되었습니다.")

        for index, row in search_result.iterrows():
            item_code_short = str(row.get('품목코드', ''))[-4:]

            with st.expander(f" [{item_code_short}] {row.get('품목명', '이름없음')}"):

                # ✨ 4창고 옆에 '불용' 열이 자연스럽게 들어가도록 HTML 테이블 수정
                st.markdown(
                    f"""
                    <table style="width:100%; border-collapse: collapse; text-align: center; border: 1px solid #ddd;">
                        <tr style="background-color: #f2f2f2;">
                            <th style="border: 1px solid #ddd; padding: 8px;">1창고</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">2창고</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">3창고</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">4창고</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">불용</th>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('1창고 (007)', 0)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('2창고 (012)', 0)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('3창고 (017)', 0)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('4창고 (018)', 0)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold; color: #e74c3c;">{row.get('불용 (009)', 0)}</td>
                        </tr>
                    </table>
                    """,
                    unsafe_allow_html=True
                )

                st.markdown("---")

                st.markdown("#### 🏷️ SKU 정보")
                st.markdown(
                    f"""
                    <table style="width:100%; border-collapse: collapse; text-align: center; border: 1px solid #ddd;">
                        <tr style="background-color: #f2f2f2;">
                            <th style="border: 1px solid #ddd; padding: 8px;">BOX 입수량</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">PLT BOX수</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">PLT 입수량</th>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('BOX 입수량', 0)} EA</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('PLT BOX수', 0)} BOX</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('PLT 입수량', 0)} EA</td>
                        </tr>
                    </table>
                    """,
                    unsafe_allow_html=True
                )

elif search_query and df.empty:
    st.error("데이터가 비어있습니다. API 설정이나 시트 주소를 다시 확인해 주세요.")
