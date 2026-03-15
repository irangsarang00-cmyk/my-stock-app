import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_google_auth import Authenticate

# ==========================================================
# 1. 구글 로그인 및 보안 설정
# ==========================================================
# 허용된 사용자 이메일 목록 (여기에 본인과 동료 이메일을 넣으세요)
WHITELIST_EMAILS = ["user1@gmail.com", "user2@gmail.com"]

# 구글 인증 설정
authenticator = Authenticate(
    secret_token="나만의_비밀_토큰_아무거나_입력", # 세션 암호화용 임의 문자열
    cookie_name="inventory_app_cookie",
    key="inventory_app_key",
    cookie_expiry_days=1,
    client_id=st.secrets["google_oauth"]["client_id"],
    client_secret=st.secrets["google_oauth"]["client_secret"], 
    redirect_uri="https://my-stock-app-ccigj2eobvvlittcqknnu2.streamlit.app/",
)

# 로그인 상태 확인
authenticator.check_authentication()

# 로그인 버튼 및 로그아웃 처리
if not st.session_state.get('connected'):
    st.markdown("<h2 style='text-align: center;'>🔒 재고 시스템 접속</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>보안을 위해 구글 로그인이 필요합니다.</p>", unsafe_allow_html=True)
    authenticator.login()
    st.stop() # 로그인 전까지 아래 코드 실행 안 함

# 화이트리스트 체크
user_email = st.session_state.get('user_info', {}).get('email')
if user_email not in WHITELIST_EMAILS:
    st.error(f"접근 권한이 없습니다. ({user_email})")
    if st.button("로그아웃"):
        authenticator.logout()
    st.stop()

# ==========================================================
# 2. 실제 구글 시트 데이터 불러오기 함수
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

        # 🌸 여기에 실제 구글 시트 주소창의 전체 링크를 붙여넣어주세요!
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
# 3. 메인 화면 출력
# ==========================================================
# 검색 안내 문구를 HTML을 이용해 가운데 정렬로 큼직하게 넣었어요.
st.markdown("<h3 style='text-align: center;'>상품명 또는 PL번호로 검색</h3>", unsafe_allow_html=True)

# 검색창 (기본 라벨은 숨겨서 깔끔하게 만들었어요)
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
            # 품목코드의 끝 4자리만 잘라서 가져옵니다.
            item_code_short = str(row.get('품목코드', ''))[-4:]

            # 끝 4자리 코드와 품목명만 보이도록 수정했어요.
            with st.expander(f" [{item_code_short}] {row.get('품목명', '이름없음')}"):

                # --- 창고별 재고 (HTML 테이블로 가로 정렬 강제) ---
                st.markdown(
                    f"""
                    <table style="width:100%; border-collapse: collapse; text-align: center; border: 1px solid #ddd;">
                        <tr style="background-color: #f2f2f2;">
                            <th style="border: 1px solid #ddd; padding: 8px;">1창고</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">2창고</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">3창고</th>
                            <th style="border: 1px solid #ddd; padding: 8px;">4창고</th>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('1창고 (007)', 0)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('2창고 (012)', 0)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('3창고 (017)', 0)}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; font-size: 1.2em; font-weight: bold;">{row.get('4창고 (018)', 0)}</td>
                        </tr>
                    </table>
                    """,
                    unsafe_allow_html=True
                )

                st.markdown("---") # 구역을 나누는 얇은 선이에요

                # --- SKU 정보 (HTML 테이블로 가로 정렬 강제 및 단위 수정) ---
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
    
