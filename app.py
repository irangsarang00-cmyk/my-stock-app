import urllib.parse
import streamlit as st
import pandas as pd
import gspread
import json
import tempfile
import os
import re
import requests 
from datetime import datetime, timedelta 
from google.oauth2.service_account import Credentials
from streamlit_google_auth import Authenticate
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, ColumnsAutoSizeMode
from st_keyup import st_keyup

# --- 상단 메뉴 및 워터마크 숨기기 ---
hide_streamlit_style = """
<style>
/* ✨ 1. 구글 웹 폰트 불러오기 (고운돋움) */
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&display=swap');

/* ✨ 2. 너무 강했던 !important를 빼고 부드럽게 전체 텍스트에 폰트를 덮어씌웁니다. */
html, body, [class*="css"], .stApp, p, h1, h2, h3, h4, h5, h6, span, div, button, input, select, textarea, table, td, th, ul, li, strong, b {
    font-family: 'Gowun Dodum', sans-serif;
}

/* ✨ 3. 아이콘 역할을 하는 녀석들은 무조건 아이콘 폰트를 쓰도록 절대 방어막을 칩니다! */
.material-icons, 
.material-symbols-rounded, 
span[class*="material-icons"], 
span[class*="material-symbols"], 
i {
    font-family: 'Material Symbols Rounded', 'Material Icons', sans-serif !important;
    font-style: normal !important;
    font-variant: normal !important;
    text-transform: none !important;
}

/* ✨ 4. AgGrid 표 내부까지 완벽하게 고운돋움 폰트 강제 적용! */
.ag-root-wrapper, .ag-theme-alpine, .ag-cell, .ag-header-cell-text {
    font-family: 'Gowun Dodum', sans-serif !important;
    --ag-font-family: 'Gowun Dodum', sans-serif !important;
}

/* --- 여기서부터는 기존 숨김 및 버튼 색상 코드 --- */
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

button[kind="primary"] {
    background-color: #4A90E2 !important;
    border-color: #4A90E2 !important;
    color: white !important;
}
button[kind="primary"]:hover,
button[kind="primary"]:active,
button[kind="primary"]:focus {
    background-color: #357ABD !important; 
    border-color: #357ABD !important;
    color: white !important;
}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

# ==========================================================
# 1. 구글 로그인 및 권한 설정
# ==========================================================
WHITELIST_EMAILS = ["irangsarang00@gmail.com", "hiyokosan0314@gmail.com", "ddadung77@gmail.com", "a01066531205@gmail.com", "seohanseung2@gmail.com", "afopis75@gmail.com", "gmsik00@gmail.com", "hamsungbin87@gmail.com", "policelee2@gmail.com", "leetic1224@gmail.com"]

auth_secrets = st.secrets["google_oauth"]

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
# 스케줄 데이터 및 구글 시트 데이터 가져오기 함수
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

        df_filled = df_raw.replace(r'^\s*$', None, regex=True)
        barrier_mask = df_filled.isna().all(axis=1)
        df_filled.loc[barrier_mask, :] = 'BARRIER'
        df_filled = df_filled.ffill()
        df_filled = df_filled[~barrier_mask]

        exclude_keywords = ['상품전환', '주차 입고', '기준:날짜']
        mask_exclude = df_filled.astype(str).apply(
            lambda x: x.str.contains('|'.join(exclude_keywords))
        ).any(axis=1)
        df_filtered = df_filled[~mask_exclude]

        mask_gapyeong = df_filtered.astype(str).apply(lambda x: x.str.contains('가평')).any(axis=1)
        date_pattern = r'(\d{2,4}\s*[.\-/]\s*\d{1,2}\s*[.\-/]\s*\d{1,2})|(\d{1,2}\s*[.\-/]\s*\d{1,2})'
        mask_date = df_filtered.astype(str).apply(lambda x: x.str.contains(date_pattern)).any(axis=1)

        schedule_df = df_filtered[mask_gapyeong & mask_date].copy()

        def force_format_date(val):
            val_str = str(val).strip()
            clean_val = re.sub(r'[.\-/]', ' ', val_str)
            parts = clean_val.split()
            if len(parts) >= 3: 
                return f"{int(parts[1])}/{int(parts[2])}"
            elif len(parts) == 2:
                return f"{int(parts[0])}/{int(parts[1])}"
            return val_str

        if len(schedule_df.columns) > 7:
            schedule_df.iloc[:, 7] = schedule_df.iloc[:, 7].apply(force_format_date)

        new_columns_idx = [7, 3, 5, 6, 8, 9, 10, 1]
        valid_indices = [c for c in new_columns_idx if c < len(schedule_df.columns)]
        schedule_df = schedule_df.iloc[:, valid_indices]

        schedule_df.columns = [
            "날짜", "바코드", "제품명", "수량", "입고시간", "창고", "컨테이너", "거래처"
        ]

        return schedule_df

    except Exception as e:
        st.error(f"스케줄을 불러오는 중 오류 발생: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=900)
def load_real_data():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
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

# ==========================================================
# 이카운트 구매입력 API 전송 함수
# ==========================================================
def send_ecount_purchase(master_data, detail_data):
    zone = "CA"
    company_code = "614508"
    user_id = "VILIV0730"
    api_key = "07a00290661fe49c58fd7318a26e4f7100"
    
    login_url = f"https://sboapi{zone}.ecount.com/OAPI/V2/OAPILogin"
    login_payload = {
        "COM_CODE": company_code,
        "USER_ID": user_id,
        "API_CERT_KEY": api_key,
        "LAN_TYPE": "ko-KR",
        "ZONE": zone
    }
    
    try:
        login_res = requests.post(login_url, json=login_payload).json()
        session_id = login_res.get("Data", {}).get("V2_SESSION_ID")
        
        if not session_id:
            return False, f"이카운트 로그인 실패: {login_res.get('Error', {}).get('Message', '알 수 없는 오류')}"
            
        save_url = f"https://sboapi{zone}.ecount.com/OAPI/V2/Purchases/SavePurchases?SESSION_ID={session_id}"
        
        purchase_list = []
        for idx, row in detail_data.iterrows():
            if not row.get('품목코드'):
                continue
            
            exp_raw = row.get('유통기한')
            add_date_02 = ""
            if exp_raw:
                try:
                    add_date_02 = pd.to_datetime(exp_raw).strftime("%Y%m%d")
                except:
                    add_date_02 = str(exp_raw).replace("-", "").replace("/", "")
                
            purchase_item = {
                "BulkFlag": "M", 
                "LineReqNo": str(idx + 1),
                "IO_DATE": master_data['일자'],
                "CUST": master_data['거래처코드'],
                "EMP_CD": "00008", # 전산 입력자는 00008로 고정
                "WH_CD": master_data['창고코드'],
                "PROD_CD": str(row['품목코드']).strip(),
                "PROD_DES": str(row['품목명']).strip(),
                "QTY": str(row['수량']).strip(),
                "ADD_DATE_02": add_date_02,
                "U_MEMO1": f"실제 담당자: {master_data['담당자']}" # ✨ 여기에 비고란 추가!
            }
            purchase_list.append(purchase_item)
            
        save_payload = {"PurchaseList": purchase_list}
        save_res = requests.post(save_url, json=save_payload).json()
        
        if save_res.get("Status") == "200":
            return True, "이카운트 구매입력이 완료되었습니다!"
        else:
            return False, f"전송 실패: {save_res.get('Error', {}).get('Message', '오류')}"
            
    except Exception as e:
        return False, f"API 통신 오류: {e}"

# ==========================================================
# 2. 메인 화면 및 페이지 이동 제어
# ==========================================================

st.markdown("""
    <style>
    div[data-testid="stExpander"] {
        min-height: 45px; 
        height: auto !important;
    }
    button[data-testid="baseButton-secondary"] {
        height: 45px !important;
        width: 100% !important;
        margin-top: 0px !important;
    }
    .stTable {
        overflow-x: auto;
    }
    </style>
""", unsafe_allow_html=True)

if "current_page" not in st.session_state:
    st.session_state.current_page = "main"

if "selected_items" not in st.session_state:
    st.session_state.selected_items = pd.DataFrame(columns=["품목코드", "품목명", "수량", "유통기한"])

def go_to_ecount():
    st.session_state.current_page = "ecount"

def go_to_main():
    st.session_state.current_page = "main"
    
    # ✨ 1. 체크해서 불러왔던 품목 표 비우기
    st.session_state.selected_items = pd.DataFrame(columns=["품목코드", "품목명", "수량", "유통기한"])
    
    # ✨ 2. 입력했던 기본 정보(날짜, 거래처, 담당자, 창고) 기억 지우기
    keys_to_clear = ["ecount_date", "ecount_vendor", "ecount_actual_user", "ecount_wh"]
    for k in keys_to_clear:
        if k in st.session_state:
            del st.session_state[k]

vendor_list = {
    "Peter(라온글로벌)": "171-86-02191",
    "빌리브": "165-88-02069",
    "글로브": "527-87-02182",
    "주식회사 여운": "244-81-02500",
    "아센트": "551-28-01909",
    "주식회사 우하모[야코브]": "860-86-02952",
    "세신실업주식회사": "621-81-48421",
    "(주)성창베네피나": "142-85-19590",
    "(주) 더꾼": "605-88-00652",
    "더마켓": "106-86-81853",
    "(주) 이라이프": "388-88-00816",
    "머티리얼즈파크 주식회사": "481-85-00017",
    "(주) 이씨티": "302-87-01094"
}
warehouse_list = {
    "1창고": "007",
    "2창고": "012",
    "3창고": "017",
    "4창고": "018"
}

# ==========================================================
# [페이지 1] 메인 화면
# ==========================================================
if st.session_state.current_page == "main":
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        with st.expander("📱 앱 설치 방법 안내"):
            st.markdown("""
            **💡 접속 및 설치 방법**
            1. 정이랑 주임에게 구글 이메일 아이디 전달해 주세요.
            2. 승인 완료되면 구글 아이디로 로그인하세요.
            3. 로그인 한 뒤, 크롬(갤럭시) or 사파리(아이폰)에서 '홈 화면에 추가'를 통해 바탕화면에 설치할 수 있습니다.
            """)

    with col2:
        with st.expander("👥 접근 허용 명단"):
            for email in WHITELIST_EMAILS:
                st.caption(f"✔️ {email}")

    with col3:
        sched_data = pd.DataFrame() 
        
        with st.expander("🚛 입고스케줄"):
            with st.spinner('분석 중...'):
                sched_data = get_incoming_schedule()
                if not sched_data.empty:
                    st.write("") 
                    
                    html_code = """
                    <div style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch;">
                        <table style="width: 100%; border-collapse: collapse; user-select: text !important; -webkit-user-select: text !important; min-width: 800px;">
                    """
                    html_code += '<tr style="background-color: #4A90E2; color: white; border-bottom: 2px solid #357ABD;">'
                    
                    for i, col in enumerate(sched_data.columns):
                        sticky_style = 'position: sticky; left: 0; background-color: #4A90E2; z-index: 2;' if i == 0 else ''
                        html_code += f'<th style="border: 1px solid #ddd; padding: 10px; font-size: 12px; white-space: nowrap; {sticky_style}">{col}</th>'
                    html_code += '</tr>'
                    
                    current_bg = "#ffffff" 
                    last_date = None        
                    
                    for _, row in sched_data.iterrows():
                        current_row_date = str(row['날짜']).strip()
                        if last_date is not None and current_row_date != last_date:
                            current_bg = "#EDF7FE" if current_bg == "#ffffff" else "#ffffff"
                        
                        last_date = current_row_date 
                        
                        html_code += f'<tr style="background-color: {current_bg};">'
                        for i, val in enumerate(row):
                            sticky_style = f'position: sticky; left: 0; background-color: {current_bg}; z-index: 1; border-right: 2px solid #ddd;' if i == 0 else ''
                            html_code += f'<td style="border: 1px solid #ddd; padding: 10px; font-size: 13px; white-space: nowrap; {sticky_style}">{val}</td>'
                        html_code += '</tr>'
                    
                    html_code += '</table></div>'
                    st.markdown(html_code, unsafe_allow_html=True)
                    st.markdown("---")
                else:
                    st.warning("예정된 가평 스케줄이 없습니다.")

        st.button("📝 (공사중) 이카운트 구매입력 하러가기", on_click=go_to_ecount, use_container_width=True, type="primary")

    # 기존 검색 화면
    df = load_real_data()

    st.markdown("<div style='margin-top: 5vh;'></div>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; font-size: 1.3em;'>상품명 또는 PL번호로 검색</h4>", unsafe_allow_html=True)

    search_query = st.text_input("", label_visibility="collapsed", placeholder="검색어를 입력하세요...")

    search_button = st.button("🔍 검색", type="primary", use_container_width=True)

    if search_query and not df.empty:
        clean_query = search_query.strip()

        mask = (
            df['품목명'].str.contains(clean_query, case=False, na=False) |
            (df['품목코드'].str[-4:] == clean_query)
        )
        search_result = df[mask]

        if search_result.empty:
            st.warning("검색 결과가 없습니다.")
        else:
            st.success(f"총 {len(search_result)}개의 품목이 검색되었습니다.")

            for index, row in search_result.iterrows():
                item_code_short = str(row.get('품목코드', ''))[-4:]

                with st.expander(f" [{item_code_short}] {row.get('품목명', '이름없음')}"):
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

# ==========================================================
# [페이지 2] 이카운트 구매입력 전용 화면
# ==========================================================
elif st.session_state.current_page == "ecount":
    
    st.button("⬅️ 메인으로", on_click=go_to_main)

    # ✨ [새로 추가된 부분] 빨간색으로 크고 아름다운 공사중 문구!
    st.markdown("""
        <div style="
            color: #e74c3c; 
            font-size: 2.5em; 
            font-weight: bold; 
            text-align: center; 
            margin-top: 15px; 
            margin-bottom: 15px;
            border: 3px solid #e74c3c;
            border-radius: 10px;
            padding: 10px;
            background-color: #fdf2f2;
        ">
            &lt;공사중입니다&gt;
        </div>
        """, unsafe_allow_html=True)
    
    st.write("### 📦 입고내역 불러오기")
    
    sched_data = get_incoming_schedule()
    
    if not sched_data.empty:
        sched_for_selection = sched_data[['날짜', '바코드', '제품명', '수량', '거래처']].copy()
        
        today = datetime.now()
        monday = today - timedelta(days=today.weekday()) 
        monday_start = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        def parse_and_filter(date_str):
            try:
                dt = datetime.strptime(f"{today.year}/{date_str.strip()}", "%Y/%m/%d")
                if (dt - today).days > 180: 
                    dt = dt.replace(year=today.year - 1)
                return dt
            except:
                return datetime.min 
                
        valid_dates = sched_for_selection['날짜'].apply(parse_and_filter)
        sched_for_selection = sched_for_selection[valid_dates >= monday_start]
        
        sched_for_selection = sched_for_selection[~sched_for_selection['거래처'].str.contains('이우', na=False)]
        
        if not sched_for_selection.empty:
            
            with st.form("ag_grid_form"):
                gb = GridOptionsBuilder.from_dataframe(sched_for_selection)
                gb.configure_selection('multiple', use_checkbox=True, header_checkbox=True)
                
                gb.configure_default_column(
                    sortable=False,        
                    suppressMovable=True,  
                    resizable=False,       
                    suppressSizeToFit=True 
                )
                gb.configure_grid_options(suppressMovableColumns=True)
                
                gb.configure_column('날짜', pinned='left', width=95) 
                gb.configure_column('바코드', width=145)
                gb.configure_column('제품명', width=500, wrapText=True, autoHeight=True) 
                gb.configure_column('수량', width=80)
                gb.configure_column('거래처', width=160)
                
                gridOptions = gb.build()
                
                # ✨ 잡다한 옵션은 싹 지우고 가장 깔끔한 기본 형태로 둡니다! (폰트는 1번 CSS가 알아서 바꿔줍니다)
                grid_response = AgGrid(
                    sched_for_selection,
                    gridOptions=gridOptions,
                    use_container_width=True, 
                    columns_auto_size_mode=ColumnsAutoSizeMode.NO_AUTOSIZE, 
                    fit_columns_on_grid_load=False, 
                    theme="alpine",
                    reload_data=True, 
                    key="ag_grid_schedule_page_final" 
                )
                
                load_clicked = st.form_submit_button("불러오기", use_container_width=True)
            
            if load_clicked:
                selected_rows = grid_response['selected_rows']
                
                if selected_rows is not None and len(selected_rows) > 0:
                    selected_df = pd.DataFrame(selected_rows)
                    new_items = pd.DataFrame({
                        "품목코드": selected_df["바코드"],
                        "품목명": selected_df["제품명"],
                        "수량": selected_df["수량"],
                        "유통기한": None 
                    })
                    st.session_state.selected_items = new_items
                    st.success("입고내역을 불러왔어요.")
                else:
                    st.warning("선택된 항목이 없습니다.")
        else:
            st.info("이번 주 월요일 이후로 등록된 입고 스케줄이 없습니다.")
    else:
        st.info("현재 예정된 입고 스케줄이 없습니다.")
        
    st.divider()
    
    # ✨ 폼(st.form)을 해제하여 검색창 배치를 자유롭게 만들었습니다.
    c1, c2 = st.columns(2)
    input_date = c1.date_input("일자", key="ecount_date").strftime("%Y%m%d")
    
    with c2:
        # ✨ 칸을 3개로 나누되, 가운데 빈 공간을 넓게(6) 줘서 팁 버튼을 오른쪽 끝으로 밀어냅니다!
        c_lbl, c_space, c_btn = st.columns([2, 6, 2])
        
        with c_lbl:
            st.markdown("<div style='font-size: 14px; margin-bottom: 5px; padding-top: 5px;'>거래처</div>", unsafe_allow_html=True)
            
        with c_btn:
            # ✨ 뚱뚱해지는 옵션을 빼고 원래의 앙증맞은 크기로 돌려놓습니다.
            with st.popover("💡 팁"):
                st.markdown("✔️ **#만 있는 것** = 라온글로벌<br>✔️ **[YC]** = 우하모(야코브)", unsafe_allow_html=True)
                
        vendor_name = st.selectbox(
            "거래처", 
            list(vendor_list.keys()), 
            key="ecount_vendor", 
            label_visibility="collapsed"
        )
        vendor_code = vendor_list[vendor_name]
    
    c3, c4 = st.columns(2)
    
    with c3:
        # ✨ 기본 텍스트 입력칸으로 복귀! 폰트도 완벽하게 적용되고 사라지는 버그도 없습니다.
        actual_user = st.text_input(
            "작성자", 
            placeholder="작성자 이름", 
            key="ecount_actual_user_keyup"
        )

    wh_name = c4.selectbox("입고창고", list(warehouse_list.keys()), key="ecount_wh")
    wh_code = warehouse_list[wh_name]
    
    # 1. 품목표가 먼저 나옵니다.
    final_items = st.data_editor(
        st.session_state.selected_items,
        use_container_width=True,
        hide_index=True, 
        column_config={
            "유통기한": st.column_config.DateColumn(
                "유통기한",
                help="클릭해서 날짜를 고르거나 YYYY/MM/DD로 적어주세요",
                format="YYYY/MM/DD"
            )
        }
    )
    
    # 2. 품목표 바로 밑에 요청하신 아주 깔끔한 검색창이 나옵니다.
    real_df = load_real_data()
    search_kw = st.text_input(
        "", 
        key="manual_search_kw", 
        placeholder="상품명 또는 PL번호로 검색", 
        label_visibility="collapsed" # 거슬리던 제목 글자를 완벽히 숨깁니다.
    )
    
    # ✨ 요청하신 파란색 검색 버튼을 검색창 바로 밑에 큼직하게 추가했습니다!
    search_clicked = st.button("🔍 검색", type="primary", use_container_width=True, key="manual_search_btn")
    
    # 검색 로직 처리 (엔터를 치거나 파란 버튼을 누르면 아래 로직이 실행됩니다)
    if search_kw and not real_df.empty:
        clean_kw = search_kw.strip()
        mask = (
            real_df['품목명'].str.contains(clean_kw, case=False, na=False) |
            (real_df['품목코드'].str[-4:] == clean_kw)
        )
        search_result = real_df[mask]
        
        if search_result.empty:
            st.warning("검색 결과가 없습니다.")
            
        elif len(search_result) == 1:
            row = search_result.iloc[0]
            # ✨ 바코드 전체 대신 뒤 4자리만 잘라서 보여줍니다.
            item_code_short = str(row['품목코드'])[-4:]
            st.success(f"✅ **[{item_code_short}] {row['품목명']}**")
            
            if st.button("✅ 추가", type="secondary"):
                new_row = pd.DataFrame([{
                    "품목코드": row["품목코드"], # 👈 표와 서버로 보낼 때는 원래대로 전체 바코드를 보냅니다.
                    "품목명": row["품목명"],
                    "수량": "1",
                    "유통기한": None
                }])
                st.session_state.selected_items = final_items
                st.session_state.selected_items = pd.concat([st.session_state.selected_items, new_row], ignore_index=True)
                st.rerun()
                
        else:
            st.info(f"총 {len(search_result)}개의 품목이 검색되었습니다.")
            
            # ✨ 드롭박스 옵션에서도 바코드 뒤 4자리만 잘라서 보여줍니다. (하지만 나중에 전체 바코드를 찾기 위해 전체 바코드도 옵션 값에 몰래 숨겨둡니다.)
            options = [f"[{str(r['품목코드'])[-4:]}] {r['품목명']} (코드:{r['품목코드']})" for _, r in search_result.iterrows()]
            
            # 사용자에게는 앞부분([4자리] 품목명)만 보여주고 선택하게 합니다.
            selected_option_full = st.selectbox("품목 선택", options, key="manual_select_item", format_func=lambda x: x.split(" (코드:")[0])
            
            if st.button("✅ 추가", type="secondary"):
                # 숨겨뒀던 진짜 전체 바코드를 꺼내서 검색합니다.
                selected_full_code = selected_option_full.split("(코드:")[1].replace(")", "").strip()
                selected_row = search_result[search_result['품목코드'] == selected_full_code].iloc[0]
                
                new_row = pd.DataFrame([{
                    "품목코드": selected_row["품목코드"], # 👈 표에는 전체 바코드가 들어갑니다.
                    "품목명": selected_row["품목명"],
                    "수량": "1",
                    "유통기한": None
                }])
                st.session_state.selected_items = final_items
                st.session_state.selected_items = pd.concat([st.session_state.selected_items, new_row], ignore_index=True)
                st.rerun()

    st.divider()

    # ✨ 폼이 없어졌으므로 st.form_submit_button 대신 일반 st.button을 사용합니다.
    submit_clicked = st.button("🚀 이카운트 입력하기", type="primary", use_container_width=True)
    
    if submit_clicked:
        if final_items.empty or str(final_items['품목코드'].iloc[0]).strip() == "" or str(final_items['품목코드'].iloc[0]) == "nan":
            st.error("입력된 품목이 없습니다.")
        elif not actual_user:
            st.warning("작성자 이름을 기록해 주세요.")
        else:
            master_info = {
                "일자": input_date,
                "거래처코드": vendor_code,
                "창고코드": wh_code,
                "담당자": actual_user
            }
            
            with st.spinner('이카운트로 데이터를 전송하고 있습니다...'):
                is_success, msg = send_ecount_purchase(master_info, final_items)
                if is_success:
                    st.success(msg)
                else:
                    st.error(msg)
                    
