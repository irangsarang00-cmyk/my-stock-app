import streamlit as st
import pandas as pd
import zipfile
import io
import openpyxl
import re
import base64
from io import BytesIO
from barcode import Code128
from barcode.writer import ImageWriter

# 새로 추가된 라이브러리들
import gspread
from google.oauth2.service_account import Credentials
from st_keyup import st_keyup
import streamlit.components.v1 as components

# --- 1. 페이지 기본 설정 ---
st.set_page_config(page_title="WMS 바코드 출력 시스템", layout="wide")

# --- 2. 바코드 생성 함수 ---
def get_barcode_base64(data):
    if not data or data == "-": 
        return ""
    try:
        rv = BytesIO()
        # write_text=True로 설정하여 이미지 자체에 바코드 문자가 포함되도록 합니다.
        # module_height 값을 조금 더 키워서 이미지 자체를 크게 만듭니다.
        options = {'write_text': True, 'module_width': 0.25, 'module_height': 10.0, 'font_size': 12}
        Code128(str(data), writer=ImageWriter()).write(rv, options=options)
        return f"data:image/png;base64,{base64.b64encode(rv.getvalue()).decode()}"
    except Exception as e:
        return ""

# --- 3. 구글 시트 데이터 불러오기 (API 서비스 계정 연동) ---
# ttl=600을 넣으면 10분(600초)마다 최신 데이터를 다시 읽어와서 캐시를 갱신해 줘요.
@st.cache_data(ttl=600)
def load_google_sheet():
    try:
        # 1) 스트림릿 시크릿에서 제이슨 키 정보 가져오기
        # (주의: 시크릿 설정 시 [gcp_service_account] 라는 이름으로 저장했다고 가정한 코드입니다. 다르게 적으셨다면 맞춰서 바꿔주세요!)
        secret_info = st.secrets["gcp_service_account"]
        
        # 2) 구글 시트 접근 권한 설정 및 인증
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_info(secret_info, scopes=scopes)
        client = gspread.authorize(creds)
        
        # 3) B구글시트 열기 및 '시트1' 데이터 가져오기
        sheet_id = "1J5RwYs3IVCm9f0IsCjwtrSerOGdx_J3f3r0o72BgrTA"
        worksheet = client.open_by_key(sheet_id).worksheet("시트1")
        
        # 4) 데이터를 판다스 데이터프레임으로 변환
        data = worksheet.get_all_values()
        
        if data:
            # 첫 번째 줄을 열 이름(헤더)으로 사용
            df = pd.DataFrame(data[1:], columns=data[0])
            return df
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"구글 시트를 불러오지 못했어요. 시크릿 설정이나 시트 공유 권한을 확인해주세요. (오류: {e})")
        return pd.DataFrame()

df_sheet = load_google_sheet()

# --- 4. 최상단: 작업대 및 IBC 바코드 고정 영역 ---
st.markdown("### 🏷️ 작업대 & IBC 바코드")
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.markdown("**작업대 바코드**")
    # 이미지를 더 크게 만들기 위해 width 값을 250에서 350으로 키웠습니다.
    st.image(get_barcode_base64("RCS0000023061"), width=350)

with col3:
    st.markdown("**IBC 바코드 입력**")
    # 텍스트 입력 대신 st_keyup을 사용해 실시간으로 값을 받아옵니다.
    ibc_input = st_keyup("", placeholder="IBC 뒤에 붙을 숫자 입력", label_visibility="collapsed")

with col2:
    st.markdown("**IBC 바코드**")
    ibc_full = f"IBC{ibc_input}" if ibc_input else "IBC"
    # 이미지를 더 크게 만들기 위해 width 값을 250에서 350으로 키웠습니다.
    st.image(get_barcode_base64(ibc_full), width=350)

st.divider()

# --- 5. ZIP 파일 업로드 및 분석 영역 ---
st.markdown("### 📁 ZIP 파일 업로드 및 발주번호 확인")
uploaded_zip = st.file_uploader("ZIP 파일을 선택해주세요.", type=["zip"])

if uploaded_zip:
    po_numbers = []
    extracted_data = []

    with zipfile.ZipFile(uploaded_zip, 'r') as z:
        for fi in z.infolist():
            if fi.filename.endswith('.xlsx') and not fi.filename.startswith('~'):
                fn = fi.filename.split('/')[-1]
                po_num = re.sub(r'[^0-9]', '', fn)
                if po_num and po_num not in po_numbers:
                    po_numbers.append(po_num)
                
                with z.open(fi) as f:
                    wb = openpyxl.load_workbook(io.BytesIO(f.read()), data_only=True)
                    ws = wb.active
                    
                    for ri in range(1, ws.max_row + 1):
                        cv = str(ws.cell(ri, 3).value or "").strip() 
                        if cv.startswith("PL") or cv.startswith("880"):
                            qv = str(ws.cell(ri - 1, 8).value or "0").strip() 
                            extracted_data.append({"po": po_num, "barcode": cv, "qty": qv})

    st.markdown("**[ 추출된 발주번호 ]**")
    po_cols = st.columns(4)
    for idx, po in enumerate(po_numbers):
        po_cols[idx % 4].write(f"📝 {po}")
        
    st.divider()

    # --- 6. 본문 5열 표 렌더링 영역 ---
    st.markdown("### 📋 상품 출력 목록")
    
    # HTML 문자열로 표 조립 시작 (표 제목 행 고정 CSS 포함)
    html_table = """
    <style>
    .table-container { max-height: 800px; overflow-y: auto; border: 1px solid #ddd; }
    table { width: 100%; border-collapse: collapse; text-align: center; }
    th { position: sticky; top: 0; background-color: #f4f4f4; padding: 10px; border-bottom: 2px solid #ccc; z-index: 10; font-size: 16px;}
    td { padding: 15px; border-bottom: 1px solid #eee; vertical-align: middle; }
    /* 표 안의 바코드 이미지를 더 크게 만들기 위해 max-width 값을 180px에서 280px로 키웠습니다. */
    img { max-width: 280px; height: auto; }
    </style>
    <div class="table-container">
    <table>
        <tr>
            <th>상품바코드</th>
            <th>상품명</th>
            <th>확정수량</th>
            <th>토트 바코드</th>
            <th>로케이션 바코드</th>
        </tr>
    """

    for item in extracted_data:
        prod_barcode = item["barcode"]
        prod_qty = item["qty"]
        
        prod_name = "매칭 실패"
        loc_num = "0"
        
        # 시트 데이터(gspread)로 매칭
        if not df_sheet.empty:
            # 0번 열(A열)이 상품바코드(SKU)라고 가정
            match_row = df_sheet[df_sheet.iloc[:, 0].astype(str).str.strip() == prod_barcode]
            if not match_row.empty:
                # C열은 인덱스 2, L열은 인덱스 11
                if len(match_row.columns) > 2:
                    prod_name = str(match_row.iloc[0, 2])
                if len(match_row.columns) > 11:
                    loc_num = str(match_row.iloc[0, 11])

        # 각 바코드 이미지 생성
        img_prod = get_barcode_base64(prod_barcode)
        img_tote = get_barcode_base64("466-RCRT1-1-1")
        img_loc = get_barcode_base64(f"466-A1-1-{loc_num}")

        # HTML 행 추가 (요청하신 대로 이미지 밑의 텍스트 출력 부분을 제거했습니다.)
        html_table += f"""
        <tr>
            <td><img src="{img_prod}"></td>
            <td style="text-align: left;">{prod_name}</td>
            <td style="font-size: 24px; font-weight: bold;">{prod_qty}</td>
            <td><img src="{img_tote}"></td>
            <td><img src="{img_loc}"></td>
        </tr>
        """

    html_table += "</table></div>"
    
    # 완성된 HTML 표를 스트림릿 화면에 안전하게 출력 (높이 850px 고정 및 스크롤 허용)
    components.html(html_table, height=850, scrolling=True)
