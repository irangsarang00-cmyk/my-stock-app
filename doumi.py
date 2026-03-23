import streamlit as st
import io
import os
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter, PdfReader

# ── 상수 ──────────────────────────────────────────────
CENTERS  = ["대구2", "동탄1", "인천14", "이천2", "양산1", "고양1"]
SKU_CODES = ["7391", "7392", "7715", "8834", "1959", "1960"]
SKU_INFO  = {   # box, unit
    "7391": (16, 30), "7392": (12, 45), "7715": (12, 45),
    "8834": (8,  16), "1959": (8,  96), "1960": (8,  96),
}

# ── 텍스트 삽입 좌표 (1683x1190 기준) ─────────────────
# 토트
TOTE_CENTER_XY   = (1219, 742)   # 도착센터
TOTE_SKU_XY      = (1120, 1050)  # SKU값
TOTE_BOX_XY      = (1323, 1050)  # BOX값
TOTE_UNIT_XY     = (1525, 1050)  # BOX당UNIT값
TOTE_CODE_XY     = (1617, 1152)  # 상품코드 우하단 (우정렬)
# 컨테이너
CONT_CENTER_XY   = (1247, 742)   # 도착센터
CONT_SKU_XY      = (1525, 1063)  # SKU값

# ── 폰트 ──────────────────────────────────────────────
def get_font(size, kind='kr'):
    kr_candidates = [
        ('C:/Windows/Fonts/malgunbd.ttf', 0),
        ('C:/Windows/Fonts/malgun.ttf', 0),
        ('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc', 2),
        ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', 2),
    ]
    num_candidates = [
        ('C:/Windows/Fonts/arialbd.ttf', 0),
        ('C:/Windows/Fonts/arial.ttf', 0),
        ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 0),
        ('/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 0),
    ]
    candidates = kr_candidates if kind == 'kr' else num_candidates
    for path, idx in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size, index=idx)
    return ImageFont.load_default()

def dc(draw, text, cx, cy, font):
    """중앙 정렬로 텍스트 그리기"""
    draw.text((cx, cy), text, font=font, fill='black', anchor='mm')

def dc_right(draw, text, rx, y, font):
    """우측 정렬로 텍스트 그리기"""
    b = draw.textbbox((0, 0), text, font=font)
    draw.text((rx - (b[2]-b[0]), y), text, font=font, fill='black')

# ── 페이지 생성 ───────────────────────────────────
def make_tote_page(center, sku_code):
    box, unit = SKU_INFO[sku_code]
    img = Image.open("tote.jpg") # 내장 이미지 파일 직접 사용
    draw = ImageDraw.Draw(img)

    f_center = get_font(200, 'kr')
    f_num    = get_font(90,  'num')
    f_code   = get_font(36,  'num')

    dc(draw, center,       *TOTE_CENTER_XY, f_center)
    dc(draw, str(box),     *TOTE_BOX_XY,   f_num)
    dc(draw, str(unit),    *TOTE_UNIT_XY,  f_num)
    dc_right(draw, sku_code, TOTE_CODE_XY[0], TOTE_CODE_XY[1], f_code)

    return img

def make_container_page(center):
    img = Image.open("container.jpg") # 내장 이미지 파일 직접 사용
    draw = ImageDraw.Draw(img)

    f_center = get_font(200, 'kr')
    dc(draw, center, *CONT_CENTER_XY, f_center)

    return img

# ── 전체 PDF 생성 (스트림릿 맞춤형 반환) ────────────────
def generate_pdf_bytes(rows, progress_cb=None):
    from collections import OrderedDict
    center_trucks = OrderedDict()
    for center, sku_code, plt_cnt, truck_cnt in rows:
        if center not in center_trucks:
            center_trucks[center] = 0
        center_trucks[center] = max(center_trucks[center], truck_cnt)

    total_cont = sum(center_trucks.values())
    total_tote = sum(p for _, _, p, _ in rows)
    total = total_cont + total_tote
    container_imgs, tote_imgs = [], []
    done = 0

    for center, truck_cnt in center_trucks.items():
        for _ in range(truck_cnt):
            container_imgs.append(make_container_page(center))
            done += 1
            if progress_cb: progress_cb(done, total, f"컨테이너 생성 중... ({done}/{total})")

    for center, sku_code, plt_cnt, truck_cnt in rows:
        for _ in range(plt_cnt):
            tote_imgs.append(make_tote_page(center, sku_code))
            done += 1
            if progress_cb: progress_cb(done, total, f"토트 생성 중... ({done}/{total})")

    all_imgs = container_imgs + tote_imgs
    if not all_imgs:
        raise ValueError("생성할 페이지가 없습니다.")

    first = all_imgs[0].convert('RGB')
    rest  = [i.convert('RGB') for i in all_imgs[1:]]
    
    # PDF를 메모리에 저장
    pdf_buf = io.BytesIO()
    first.save(pdf_buf, format='PDF', save_all=True, append_images=rest)
    pdf_buf.seek(0)

    return pdf_buf, len(container_imgs), len(tote_imgs)


# ---------------------------------------------------------
# 스트림릿 메인 화면 설정 및 디자인
# ---------------------------------------------------------
st.set_page_config(page_title="창고 관리 시스템", layout="wide")

st.markdown("""
    <style>
        header {visibility: hidden;}
        .stTabs [data-baseweb="tab-list"] { justify-content: center; gap: 20px; }
        .stTabs [data-baseweb="tab"] {
            font-size: 35px !important; font-weight: 900 !important;
            padding: 20px 80px !important; height: auto !important;
            background-color: #f0f2f5; border-radius: 15px 15px 0 0;
        }
        .stTabs [aria-selected="true"] { background-color: #FFB3E3; color: #000000 !important; }
        div.stButton > button { width: 100%; height: 120px; font-size: 28px; font-weight: bold; border-radius: 15px; }
        .center-text { text-align: center; }
    </style>
""", unsafe_allow_html=True)

if 'current_page' not in st.session_state:
    st.session_state.current_page = 'main'

if st.session_state.current_page == 'main':
    tab1, tab2 = st.tabs(["🏭 1창고", "🏭 3창고"])
    
    with tab1:
        st.markdown("<h2 class='center-text'><br>1창고 기능은 준비 중입니다.</h2>", unsafe_allow_html=True)
        
    with tab2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("📄 가평3 (D) 출고건 병합"):
                st.session_state.current_page = 'page_d_merge'
                st.rerun()
            st.write("")
            if st.button("🏷️ 부착물 자동생성"):
                st.session_state.current_page = 'page_attachment'
                st.rerun()

elif st.session_state.current_page == 'page_d_merge':
    st.markdown("<h1 class='center-text'>📄 가평3 (D) 출고건 병합</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("◀ 메인으로 돌아가기"):
            st.session_state.current_page = 'main'
            st.rerun()
            
    st.divider()
    
    uploaded_files = st.file_uploader("병합할 PDF 파일들을 올려주세요", type="pdf", accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("병합 실행하기", type="primary"):
            merger = PdfWriter()
            try:
                for file in uploaded_files:
                    reader = PdfReader(file)
                    for page in reader.pages:
                        merger.add_page(page)
                
                merged_pdf = io.BytesIO()
                merger.write(merged_pdf)
                merged_pdf.seek(0)
                
                st.success("✅ 병합이 완료되었습니다! 아래 버튼을 눌러 저장하세요.")
                st.download_button("📥 병합된 PDF 다운로드", data=merged_pdf, file_name="병합완료_출고건.pdf", mime="application/pdf")
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")

elif st.session_state.current_page == 'page_attachment':
    st.markdown("<h1 class='center-text'>🏷️ 부착물 자동생성</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("◀ 메인으로 돌아가기"):
            st.session_state.current_page = 'main'
            st.rerun()
            
    st.divider()
    st.info("💡 파이썬 파일과 동일한 위치에 `tote.jpg`, `container.jpg` 파일이 있어야 정상 작동합니다.")
    
    if 'input_data' not in st.session_state:
        # 빈 데이터 초기 세팅
        st.session_state.input_data = [{"센터": CENTERS[0], "SKU": SKU_CODES[0], "팔렛트수": 0, "트럭수": 0}]
    
    st.write("아래 표에 데이터를 입력하거나 행을 추가하세요.")
    edited_data = st.data_editor(st.session_state.input_data, num_rows="dynamic", use_container_width=True)
    
    if st.button("📄 PDF 생성하기", type="primary"):
        # 입력 데이터 변환 (빈 값 무시)
        rows = []
        for row in edited_data:
            if row.get("팔렛트수", 0) > 0 or row.get("트럭수", 0) > 0:
                rows.append((row["센터"], row["SKU"], int(row.get("팔렛트수", 0)), int(row.get("트럭수", 0))))
                
        if not rows:
            st.warning("최소 한 개의 팔렛트나 트럭 수량을 입력해 주세요.")
        else:
            try:
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(done, total, msg):
                    progress_bar.progress(done / total)
                    status_text.text(msg)
                
                pdf_bytes, cont_cnt, tote_cnt = generate_pdf_bytes(rows, progress_cb=update_progress)
                
                progress_bar.empty()
                status_text.empty()
                
                st.success(f"✅ 완료! (컨테이너 {cont_cnt}장, 토트 {tote_cnt}장)")
                st.download_button(
                    label="📥 부착물 PDF 다운로드",
                    data=pdf_bytes,
                    file_name="부착물.pdf",
                    mime="application/pdf"
                )
            except FileNotFoundError:
                st.error("🚨 `container.jpg` 또는 `tote.jpg` 파일을 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"오류가 발생했습니다: {e}")
