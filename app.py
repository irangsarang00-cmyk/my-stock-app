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

        raw_data = worksheet.get_all_values()
        df_raw = pd.DataFrame(raw_data)

        if df_raw.empty:
            return pd.DataFrame()

        # ✨ [수정된 로직] 
        # 1. 띄어쓰기만 있는 칸도 완벽하게 빈칸(None)으로 인식하도록 변환
        df_filled = df_raw.replace(r'^\s*$', None, regex=True)

        # 2. 모든 칸이 비어있는 '스페이서(빈 행)'를 찾아냅니다.
        barrier_mask = df_filled.isna().all(axis=1)
        
        # 3. 빈 행에 'BARRIER'라는 장벽을 쳐서 ffill이 넘어가지 못하게 막습니다!
        df_filled.loc[barrier_mask, :] = 'BARRIER'

        # 4. 이제 안심하고 ffill(병합된 셀 채우기)을 실행합니다.
        # 장벽 밑에 있는 '미정' 데이터들은 남의 날짜를 훔쳐오지 못하고 'BARRIER'를 받게 됩니다.
        df_filled = df_filled.ffill()

        # 5. 역할을 다한 장벽 행은 깔끔하게 삭제합니다.
        df_filled = df_filled[~barrier_mask]

        # 6. 불필요한 헤더 행 제외 (기존 로직 유지)
        exclude_keywords = ['상품전환', '주차 입고', '기준:날짜']
        mask_exclude = df_filled.astype(str).apply(
            lambda x: x.str.contains('|'.join(exclude_keywords))
        ).any(axis=1)
        df_filtered = df_filled[~mask_exclude]

        # 3. '가평'이 포함된 행 필터링
        mask_gapyeong = df_filtered.astype(str).apply(lambda x: x.str.contains('가평')).any(axis=1)

        # 4. '날짜' 패턴이 포함된 행 필터링
        date_pattern = r'(\d{2,4}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2})|(\d{1,2}\s*[.\-/]\s*\d{1,2})'
        mask_date = df_filtered.astype(str).apply(lambda x: x.str.contains(date_pattern)).any(axis=1)

        # 5. 최종 조건 만족 행 추출
        schedule_df = df_filtered[mask_gapyeong & mask_date].copy()

        # 6. 날짜 형식 강제 통일 (월/일)
        def force_format_date(val):
            val_str = str(val).strip()
            # 1단계: 모든 구분자(., -, /)를 공백으로 치환하여 숫자만 추출하기 쉽게 만듦
            clean_val = re.sub(r'[.\-/]', ' ', val_str)
            parts = clean_val.split()
            
            if len(parts) >= 3: # 연.월.일 형태 (2026 03 15)
                # 연도가 앞에 오든 뒤에 오든, 1~12 사이의 숫자를 월로, 나머지를 일로 판단
                # 안전하게 연도를 제외한 두 번째, 세 번째 요소를 가져옴
                return f"{int(parts[1])}/{int(parts[2])}"
            elif len(parts) == 2: # 월.일 형태 (03 15)
                return f"{int(parts[0])}/{int(parts[1])}"
            return val_str

        if len(schedule_df.columns) > 7:
            schedule_df.iloc[:, 7] = schedule_df.iloc[:, 7].apply(force_format_date)

        # 7. 열 순서 재배치 (7, 3, 5, 6, 8, 9, 10, 1)
        new_columns_idx = [7, 3, 5, 6, 8, 9, 10, 1]
        valid_indices = [c for c in new_columns_idx if c < len(schedule_df.columns)]
        schedule_df = schedule_df.iloc[:, valid_indices]

        # 8. ✨ 열 제목 변경 (숫자 대신 한글로!)
        schedule_df.columns = [
            "날짜", "바코드", "제품명", "수량", "입고시간", "창고", "컨테이너", "거래처"
        ]

        return schedule_df

    except Exception as e:
        st.error(f"스케줄을 불러오는 중 오류 발생: {e}")
        return pd.DataFrame()

# ==========================================================
# 2. 메인 화면 시작 (로그인 성공 후)
# ==========================================================

# ✨ CSS 수정: 높이를 고정(height)하지 않고 최소 높이(min-height)만 설정합니다.
st.markdown("""
    <style>
    div[data-testid="stExpander"] {
        min-height: 45px; 
        height: auto !important; /* 내용에 따라 늘어나도록 강제 설정 */
    }
    button[data-testid="baseButton-secondary"] {
        height: 45px !important;
        width: 100% !important;
        margin-top: 0px !important;
    }
    /* 입고스케줄 표가 너무 커서 모바일을 가리지 않게 살짝 조정 */
    .stTable {
        overflow-x: auto;
    }
    </style>
""", unsafe_allow_html=True)

# 1:1:1 비율로 3개의 컬럼 생성
col1, col2, col3 = st.columns([1, 1, 1])

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
    with st.expander("🚛 입고스케줄"):
        with st.spinner('분석 중...'):
            sched_data = get_incoming_schedule()
            if not sched_data.empty:
                st.write("") 
                
                html_code = """
                <div style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch;">
                    <table style="width: 100%; border-collapse: collapse; user-select: text !important; -webkit-user-select: text !important; min-width: 800px;">
                """
                
                # 1. 제목(헤더) 행 (진한 하늘색 계열로 변경)
                html_code += '<tr style="background-color: #4A90E2; color: white; border-bottom: 2px solid #357ABD;">'
                for i, col in enumerate(sched_data.columns):
                    sticky_style = 'position: sticky; left: 0; background-color: #4A90E2; z-index: 2;' if i == 0 else ''
                    html_code += f'<th style="border: 1px solid #ddd; padding: 10px; font-size: 12px; white-space: nowrap; {sticky_style}">{col}</th>'
                html_code += '</tr>'
                
                # 2. 날짜별 색상 제어 변수
                current_bg = "#ffffff"  # 초기 배경색 (흰색)
                last_date = None        # 이전 행의 날짜 저장용
                
                # 3. 데이터 행 생성
                for _, row in sched_data.iterrows():
                    current_row_date = str(row['날짜']).strip()
                    
                    # 날짜가 이전 행과 다르면 색상 변경!
                    if last_date is not None and current_row_date != last_date:
                        # 흰색 <-> 연한 하늘색(#E3F2FD) 스위칭
                        current_bg = "#EDF7FE" if current_bg == "#ffffff" else "#ffffff"
                    
                    last_date = current_row_date # 현재 날짜를 기록
                    
                    html_code += f'<tr style="background-color: {current_bg};">'
                    for i, val in enumerate(row):
                        # 날짜 열(첫 번째 열) 고정 및 현재 배경색 유지
                        sticky_style = f'position: sticky; left: 0; background-color: {current_bg}; z-index: 1; border-right: 2px solid #ddd;' if i == 0 else ''
                        html_code += f'<td style="border: 1px solid #ddd; padding: 10px; font-size: 13px; white-space: nowrap; {sticky_style}">{val}</td>'
                    html_code += '</tr>'
                
                html_code += '</table></div>'
                
                st.markdown(html_code, unsafe_allow_html=True)
                st.markdown("---")
            else:
                st.warning("예정된 가평 스케줄이 없습니다.")

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

# 기존 검색창 윗부분
st.markdown("<div style='margin-top: 5vh;'></div>", unsafe_allow_html=True) # vh 숫자를 높이면 간격이 더 벌어집니다.
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
