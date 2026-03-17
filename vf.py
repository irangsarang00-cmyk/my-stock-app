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

import gspread
from google.oauth2.service_account import Credentials
from st_keyup import st_keyup
import streamlit.components.v1 as components

st.set_page_config(page_title="벤더플렉스 입고 도우미", layout="wide")

def get_barcode_base64(data):
    if not data or data == "-": 
        return ""
    try:
        rv = BytesIO()
        options = {'write_text': True, 'module_width': 0.25, 'module_height': 10.0, 'font_size': 12}
        Code128(str(data), writer=ImageWriter()).write(rv, options=options)
        return f"data:image/png;base64,{base64.b64encode(rv.getvalue()).decode()}"
    except Exception as e:
        return ""

@st.cache_data(ttl=600)
def load_google_sheet():
    try:
        secret_info = st.secrets["gcp_service_account"]
        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_info(secret_info, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_id = "1J5RwYs3IVCm9f0IsCjwtrSerOGdx_J3f3r0o72BgrTA"
        worksheet = client.open_by_key(sheet_id).worksheet("시트1")
        data = worksheet.get_all_values()
        if data:
            df = pd.DataFrame(data[1:], columns=data[0])
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"구글 시트를 불러오지 못했어요. (오류: {e})")
        return pd.DataFrame()

df_sheet = load_google_sheet()

st.markdown("""
<style>
.block-container {
    padding-top: 0rem !important;
}
header[data-testid="stHeader"] {
    display: none !important;
}
.fixed-top-bar {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    background-color: white;
    z-index: 9999;
    padding: 12px 30px 14px 30px;
    border-bottom: 2px solid #ddd;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    box-sizing: border-box;
}
.main-content {
    margin-top: 180px;
}
.top-barcode-title {
    font-size: 18px;
    font-weight: bold;
    text-align: center;
    margin-bottom: 8px;
}
.fixed-top-bar img {
    max-width: 380px;
    max-height: 160px;
    width: 100%;
    object-fit: contain;
    display: block;
    margin: 0 auto;
}
iframe { margin-bottom: 0 !important; }
</style>
""", unsafe_allow_html=True)

workbench_img = get_barcode_base64("466-RCRT1-1-1")
ibc_placeholder_img = get_barcode_base64("IBC")

st.markdown(f"""
<div class="fixed-top-bar">
    <div style="display: flex; justify-content: space-around; align-items: center; gap: 20px;">
        <div style="text-align: center; flex: 1; min-width: 0;">
            <div class="top-barcode-title">🏷️ 작업대 바코드</div>
            <img src="{workbench_img}">
        </div>
        <div style="text-align: center; flex: 1; min-width: 0;">
            <div class="top-barcode-title">🏷️ IBC 바코드</div>
            <img src="{ibc_placeholder_img}" id="ibc-barcode-img">
        </div>
        <div style="text-align: center; flex: 1; min-width: 0;">
            <div class="top-barcode-title">✏️ IBC 바코드 입력</div>
            <input 
                id="ibc-input"
                type="text"
                placeholder="IBC 뒤에 붙는 숫자 입력"
                style="font-size: 20px; padding: 10px; width: 85%; border: 2px solid #ccc; border-radius: 6px; text-align: center; box-sizing: border-box;"
                oninput="updateIBC(this.value)"
            >
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

components.html("""
<script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
<canvas id="ibc-canvas" style="display:none;"></canvas>
<script>
function updateIBC(val) {
    const fullCode = val ? 'IBC' + val : 'IBC';
    try {
        const canvas = document.getElementById('ibc-canvas');
        JsBarcode(canvas, fullCode, {
            format: "CODE128",
            width: 2,
            height: 80,
            displayValue: true,
            fontSize: 16
        });
        const dataUrl = canvas.toDataURL('image/png');
        window.parent.document.getElementById('ibc-barcode-img').src = dataUrl;
    } catch(e) {}
}
window.parent.document.getElementById('ibc-input').addEventListener('input', function() {
    updateIBC(this.value);
});
</script>
""", height=0)

st.markdown('<div class="main-content">', unsafe_allow_html=True)

st.divider()

# --- ZIP 파일 업로드 ---
st.markdown("### 📁 ZIP 파일 업로드 및 발주번호 확인")
uploaded_files = st.file_uploader(
    "ZIP 파일 또는 XLSX 파일을 선택해주세요. (복수 선택 가능)",
    type=["zip", "xlsx"],
    accept_multiple_files=True
)

if uploaded_files:
    po_numbers = []        # (po_num, is_confirmed) 튜플 리스트
    extracted_data = []

    def process_xlsx(ws, po_num, is_confirmed):
        """워크시트에서 데이터 추출"""
        for ri in range(1, ws.max_row + 1):
            cv = str(ws.cell(ri, 3).value or "").strip()
            if cv.startswith("PL") or cv.startswith("880"):
                qv = str(ws.cell(ri - 1, 8).value or "0").strip()
                extracted_data.append({
                    "po": po_num,
                    "barcode": cv,
                    "qty": qv,
                    "confirmed": is_confirmed
                })

    def check_confirmed(ws):
        """Q20~S20 병합셀에 '입고금액' 텍스트 여부 확인"""
        # 병합셀 확인
        for merged in ws.merged_cells.ranges:
            if (merged.min_row == 20 and merged.max_row == 20 and
                merged.min_col == 17 and merged.max_col == 19):  # Q=17, R=18, S=19
                cell_val = str(ws.cell(20, 17).value or "").strip()
                return cell_val == "입고금액"
        # 병합 없이 단일 셀에 있는 경우도 체크
        cell_val = str(ws.cell(20, 17).value or "").strip()
        return cell_val == "입고금액"

    for uploaded_file in uploaded_files:
        filename = uploaded_file.name

        if filename.endswith(".zip"):
            with zipfile.ZipFile(uploaded_file, 'r') as z:
                for fi in z.infolist():
                    if fi.filename.endswith('.xlsx') and not fi.filename.startswith('~'):
                        fn = fi.filename.split('/')[-1]
                        po_num = re.sub(r'[^0-9]', '', fn)
                        with z.open(fi) as f:
                            wb = openpyxl.load_workbook(io.BytesIO(f.read()), data_only=True)
                            ws = wb.active
                            is_confirmed = check_confirmed(ws)
                            if po_num and (po_num, is_confirmed) not in po_numbers:
                                po_numbers.append((po_num, is_confirmed))
                            process_xlsx(ws, po_num, is_confirmed)

        elif filename.endswith(".xlsx"):
            po_num = re.sub(r'[^0-9]', '', filename)
            wb = openpyxl.load_workbook(io.BytesIO(uploaded_file.read()), data_only=True)
            ws = wb.active
            is_confirmed = check_confirmed(ws)
            if po_num and (po_num, is_confirmed) not in po_numbers:
                po_numbers.append((po_num, is_confirmed))
            process_xlsx(ws, po_num, is_confirmed)

    # 발주번호 바코드 출력
    st.markdown("**[ 발주번호 ]**")
    po_cols = st.columns(4)
    for idx, (po, is_confirmed) in enumerate(po_numbers):
        with po_cols[idx % 4]:
            # 미확정이면 빨간색 텍스트
            text_color = "#222222" if is_confirmed else "#e00000"
            label = f"📝 {po}" if is_confirmed else f"📝 {po} ⚠️ 미확정"
            st.markdown(
                f"<div style='text-align:center; font-size:18px; font-weight:bold; "
                f"margin-bottom:4px; color:{text_color};'>{label}</div>",
                unsafe_allow_html=True
            )
            img_b64 = get_barcode_base64(po)
            # 미확정이면 바코드에 빨간 테두리 + 필터로 붉게 표시
            if is_confirmed:
                st.markdown(
                    f"<div style='text-align:center;'>"
                    f"<img src='{img_b64}' style='max-width:300px;'></div>",
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f"<div style='text-align:center; border: 2px solid #e00000; "
                    f"border-radius:6px; display:inline-block; padding:4px;'>"
                    f"<img src='{img_b64}' style='max-width:300px; "
                    f"filter: sepia(1) saturate(5) hue-rotate(-10deg);'></div>",
                    unsafe_allow_html=True
                )

    st.divider()

    # 상품 출력 목록
    # 미확정 발주서가 하나라도 있으면 제목 옆에 표시
    has_unconfirmed = any(not c for _, c in po_numbers)
    unconfirmed_label = (
        " <span style='color:#e00000; font-size:16px;'>* 미확정 발주서</span>"
        if has_unconfirmed else ""
    )
    st.markdown(
        f"### 📋 상품 출력 목록{unconfirmed_label}",
        unsafe_allow_html=True
    )

    html_table = """
    <style>
    .table-container { max-height: 800px; overflow-y: auto; border: 1px solid #ddd; }
    table { width: 100%; border-collapse: collapse; text-align: center; }
    th { position: sticky; top: 0; background-color: #f4f4f4; padding: 10px;
         border-bottom: 2px solid #ccc; z-index: 10; font-size: 16px;}
    td { padding: 15px; border-bottom: 1px solid #eee; vertical-align: middle; }
    img { max-width: 280px; height: auto; }
    .product-name { font-size: 20px; text-align: left; padding-left: 10px; }
    .unconfirmed-name { font-size: 20px; text-align: left; padding-left: 10px; color: #e00000; }
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

    inventory_rows = []
    seen = set()

    for item in extracted_data:
        prod_barcode = item["barcode"]
        prod_qty = item["qty"]
        is_confirmed = item["confirmed"]
        prod_name = "매칭 실패"
        loc_num = "0"
        w1 = w2 = w3 = w4 = "-"

        if not df_sheet.empty:
            match_row = df_sheet[df_sheet.iloc[:, 0].astype(str).str.strip() == prod_barcode]
            if not match_row.empty:
                if len(match_row.columns) > 2:
                    prod_name = str(match_row.iloc[0, 2])
                if len(match_row.columns) > 3:
                    w1 = str(match_row.iloc[0, 3])
                if len(match_row.columns) > 4:
                    w2 = str(match_row.iloc[0, 4])
                if len(match_row.columns) > 5:
                    w3 = str(match_row.iloc[0, 5])
                if len(match_row.columns) > 6:
                    w4 = str(match_row.iloc[0, 6])
                if len(match_row.columns) > 11:
                    loc_num = str(match_row.iloc[0, 11])

        if is_confirmed:
            # 확정: 정상 출력
            img_prod_tag = f'<img src="{get_barcode_base64(prod_barcode)}">'
            name_class = "product-name"
            qty_style = "font-size: 24px; font-weight: bold;"
        else:
            # 미확정: 바코드 없음 + 빨간색
            img_prod_tag = (
                f'<div style="color:#e00000; font-size:13px; font-weight:bold;">'
                f'⚠️ 미확정<br>{prod_barcode}</div>'
            )
            name_class = "unconfirmed-name"
            qty_style = "font-size: 24px; font-weight: bold; color: #e00000;"
            
        img_loc  = get_barcode_base64(f"466-RCRT1-1-1")
        img_loc  = get_barcode_base64(f"466-A1-1-{loc_num}")

        # 미확정이면 토트/로케이션도 빨간 필터
        tote_tag = f'<img src="{img_tote}">' if is_confirmed else (
            f'<img src="{img_tote}" style="filter: sepia(1) saturate(5) hue-rotate(-10deg);">'
        )
        loc_tag = f'<img src="{img_loc}">' if is_confirmed else (
            f'<img src="{img_loc}" style="filter: sepia(1) saturate(5) hue-rotate(-10deg);">'
        )

        html_table += f"""
        <tr>
            <td>{img_prod_tag}</td>
            <td class="{name_class}">{prod_name}</td>
            <td style="{qty_style}">{prod_qty}</td>
            <td>{tote_tag}</td>
            <td>{loc_tag}</td>
        </tr>
        """

        if prod_barcode not in seen:
            seen.add(prod_barcode)
            inventory_rows.append({
                "상품명": prod_name,
                "1창고": w1,
                "2창고": w2,
                "3창고": w3,
                "4창고": w4,
                "confirmed": is_confirmed
            })

    html_table += "</table></div>"

    # 이카운트 재고 현황
    inv_section = """
    <div style="margin-top: 24px;">
        <div style="font-size: 22px; font-weight: bold; margin-bottom: 8px;">📦 이카운트 재고 현황</div>
        <style>
        .inv-container { border: 1px solid #ddd; border-radius: 6px; overflow: hidden; }
        .inv-table { width: 100%; border-collapse: collapse; text-align: center; }
        .inv-table th {
            background-color: #4A90D9; color: white;
            padding: 12px 8px; font-size: 20px;
        }
        .inv-table td {
            padding: 12px 8px; border-bottom: 1px solid #eee;
            font-size: 19px; vertical-align: middle;
        }
        .inv-table tr:nth-child(even) { background-color: #f9f9f9; }
        .inv-table tr:hover { background-color: #EBF5FB; }
        .inv-name { text-align: center; font-weight: 500; }
        .inv-name-red { text-align: center; font-weight: 500; color: #e00000; }
        .inv-num  { font-weight: bold; color: #1a5276; }
        </style>
        <div class="inv-container">
        <table class="inv-table">
            <tr>
                <th>상품명</th><th>1창고</th><th>2창고</th><th>3창고</th><th>4창고</th>
            </tr>
    """

    for row in inventory_rows:
        name_cls = "inv-name" if row["confirmed"] else "inv-name-red"
        inv_section += f"""
            <tr>
                <td class="{name_cls}">{row['상품명']}</td>
                <td class="inv-num">{row['1창고']}</td>
                <td class="inv-num">{row['2창고']}</td>
                <td class="inv-num">{row['3창고']}</td>
                <td class="inv-num">{row['4창고']}</td>
            </tr>
        """

    inv_section += "</table></div></div>"

    combined_html = html_table + inv_section

    product_height = 100 + len(extracted_data) * 180
    inv_height = 60 + len(inventory_rows) * 52
    total_height = product_height + inv_height + 100

    components.html(combined_html, height=total_height, scrolling=True)

st.markdown('</div>', unsafe_allow_html=True)
