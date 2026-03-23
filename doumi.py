import streamlit as st
import io
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter

# ── 상수 및 기본 설정 ──────────────────────────────────
CENTERS  = ["대구2", "동탄1", "인천14", "이천2", "양산1", "고양1"]
SKU_CODES = ["7391", "7392", "7715", "8834", "1959", "1960"]
SKU_INFO  = {   
    "7391": (16, 30), "7392": (12, 45), "7715": (12, 45),
    "8834": (8,  16), "1959": (8,  96), "1960": (8,  96),
}
NUM_BLOCKS = 3
ROWS_PER_BLOCK = 6

# ── 텍스트 삽입 좌표 ───────────────────────────────────
TOTE_CENTER_XY   = (1219, 742)
TOTE_SKU_XY      = (1120, 1050)
TOTE_BOX_XY      = (1323, 1050)
TOTE_UNIT_XY     = (1525, 1050)
TOTE_CODE_XY     = (1617, 1152)

CONT_CENTER_XY   = (1247, 742)
CONT_SKU_XY      = (1525, 1063)

# ── 폰트 및 그리기 함수 ────────────────────────────────
def get_font(size):
    # 같은 폴더에 있는 나눔스퀘어 폰트를 바로 불러옵니다.
    font_path = "NanumSquare_acEB.ttf"
    try:
        return ImageFont.truetype(font_path, size)
    except IOError:
        st.error(f"🚨 폰트 파일을 찾을 수 없어요! 폴더 안에 '{font_path}' 파일이 있는지 확인해 주세요.")
        return ImageFont.load_default()

def dc(draw, text, cx, cy, font):
    # 글자를 지정된 좌표의 정중앙에 배치합니다.
    draw.text((cx, cy), text, font=font, fill='black', anchor='mm')

def dc_right(draw, text, rx, y, font):
    # 우측 하단 정렬용
    b = draw.textbbox((0, 0), text, font=font)
    draw.text((rx - (b[2]-b[0]), y), text, font=font, fill='black')

# ── 페이지 생성 로직 ───────────────────────────────────
def make_tote_page(center, sku_code):
    box, unit = SKU_INFO[sku_code]
    img = Image.open("tote.jpg")
    draw = ImageDraw.Draw(img)
    
    # 글자 크기를 아주 큼직하게 키웠습니다!
    f_center = get_font(200)  # 센터명 크기
    f_num    = get_font(100)  # 팔렛트/박스 숫자 크기
    f_code   = get_font(70)  # SKU 번호 크기

    dc(draw, center,       *TOTE_CENTER_XY, f_center)
    dc(draw, str(box),     *TOTE_BOX_XY,   f_num)
    dc(draw, str(unit),    *TOTE_UNIT_XY,  f_num)
    dc_right(draw, sku_code, TOTE_CODE_XY[0], TOTE_CODE_XY[1], f_code)
    return img

def make_container_page(center):
    img = Image.open("container.jpg")
    draw = ImageDraw.Draw(img)
    
    # 컨테이너 센터 글자 크기
    f_center = get_font(500)
    dc(draw, center, *CONT_CENTER_XY, f_center)
    return img

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
    
    pdf_buf = io.BytesIO()
    first.save(pdf_buf, format='PDF', save_all=True, append_images=rest)
    pdf_buf.seek(0)
    return pdf_buf, len(container_imgs), len(tote_imgs)

# ── 스트림릿 화면 구성 ───────────────────────────────────
st.set_page_config(page_title="부착물 자동생성", layout="wide")

st.markdown("<h1 style='text-align: center;'>📦 부착물 자동생성</h1>", unsafe_allow_html=True)
st.divider()

# 입력값 초기화 함수
def reset_inputs():
    for b in range(NUM_BLOCKS):
        st.session_state[f"center_{b}"] = CENTERS[0]
        st.session_state[f"truck_{b}"] = 0
        for r in range(ROWS_PER_BLOCK):
            st.session_state[f"plt_{b}_{r}"] = 0

if "initialized" not in st.session_state:
    reset_inputs()
    st.session_state["initialized"] = True

# 3등분 화면 생성
cols = st.columns(3)

for b in range(NUM_BLOCKS):
    with cols[b]:
        st.markdown(f"### 블록 {b+1}")
        st.markdown("""<div style='background-color: #FFFF00; padding: 5px; text-align: center; border: 1px solid black; font-weight: bold;'>센터 및 트럭</div>""", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        with c1:
            st.selectbox("센터", options=CENTERS, key=f"center_{b}", label_visibility="collapsed")
        with c2:
            st.number_input("트럭", min_value=0, step=1, key=f"truck_{b}", label_visibility="collapsed")
        
        st.write("")
        st.markdown("""<div style='background-color: #FFFF00; padding: 5px; text-align: center; border: 1px solid black; font-weight: bold;'>상품 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 팔렛트 수</div>""", unsafe_allow_html=True)
        
        for r in range(ROWS_PER_BLOCK):
            c_sku, c_plt = st.columns([1, 1])
            with c_sku:
                st.markdown(f"<div style='text-align: center; padding-top: 10px; font-weight: bold;'>{SKU_CODES[r]}</div>", unsafe_allow_html=True)
            with c_plt:
                st.number_input("plt", min_value=0, step=1, key=f"plt_{b}_{r}", label_visibility="collapsed")

st.divider()

# 하단 버튼
btn1, btn2 = st.columns([1, 1])

with btn1:
    if st.button("🔄 초기화", use_container_width=True):
        reset_inputs()
        st.rerun()

with btn2:
    generate_clicked = st.button("📄 PDF 생성", type="primary", use_container_width=True)

# 생성 버튼 눌렀을 때의 동작
if generate_clicked:
    rows = []
    for b in range(NUM_BLOCKS):
        center = st.session_state[f"center_{b}"]
        truck = st.session_state[f"truck_{b}"]
        for r in range(ROWS_PER_BLOCK):
            plt_cnt = st.session_state[f"plt_{b}_{r}"]
            if plt_cnt > 0:
                rows.append((center, SKU_CODES[r], plt_cnt, truck))
                
    if not rows:
        st.warning("최소 한 개의 팔렛트 수량을 입력해 주세요.")
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
            st.error("🚨 `container.jpg` 또는 `tote.jpg` 이미지를 찾을 수 없어요. 코드가 있는 폴더에 이미지를 꼭 넣어주세요!")
        except Exception as e:
            st.error(f"오류가 발생했습니다: {e}")
