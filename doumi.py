import streamlit as st
import io
import os
import json
import re
import zipfile
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter, PdfReader
import pdfplumber
import pandas as pd

# =====================================================================
# 기본 설정 및 화면 분할
# =====================================================================
st.set_page_config(page_title="통합 창고 관리 시스템", layout="wide")

st.markdown("<h1 style='text-align: center;'>📦 통합 창고 관리 시스템</h1>", unsafe_allow_html=True)
st.divider()

# 좌우 화면 분할 (1:1 비율)
col_left, col_right = st.columns(2)

# =====================================================================
# [왼쪽 화면] 1. 발주서 추출 및 PDF 병합 (milk3 로직)
# =====================================================================
with col_left:
    st.markdown("### 📄 [1] 발주서 추출 및 PDF 병합 (가평3)")
    st.markdown("<div style='background-color: #f0f2f5; padding: 15px; border-radius: 10px;'>", unsafe_allow_html=True)
    
    # ── A타입 바코드 관리 ──
    CONFIG_D_PATH = "type_a_barcodes.json"
    
    def load_type_a():
        if os.path.exists(CONFIG_D_PATH):
            try:
                with open(CONFIG_D_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []

    def save_type_a(barcodes):
        with open(CONFIG_D_PATH, "w", encoding="utf-8") as f:
            json.dump(barcodes, f, ensure_ascii=False, indent=4)

    if 'type_a_barcodes' not in st.session_state:
        st.session_state.type_a_barcodes = load_type_a()

    with st.expander("⚙️ 'A' 구분 바코드 매칭 사전 관리", expanded=False):
        c1, c2 = st.columns([3, 1])
        with c1:
            new_bc = st.text_input("A타입 적용 바코드 입력", key="new_bc_input", label_visibility="collapsed", placeholder="바코드 입력...")
        with c2:
            if st.button("➕ 추가", use_container_width=True):
                if new_bc and new_bc not in st.session_state.type_a_barcodes:
                    st.session_state.type_a_barcodes.append(new_bc.strip())
                    save_type_a(st.session_state.type_a_barcodes)
                    st.rerun()
                    
        if st.session_state.type_a_barcodes:
            st.write("등록된 바코드 목록:")
            for bc in st.session_state.type_a_barcodes:
                bc_col1, bc_col2 = st.columns([4, 1])
                bc_col1.markdown(f"**{bc}**")
                if bc_col2.button("❌ 삭제", key=f"del_{bc}", help=f"{bc} 삭제"):
                    st.session_state.type_a_barcodes.remove(bc)
                    save_type_a(st.session_state.type_a_barcodes)
                    st.rerun()

    # ── 파일 업로드 및 실행 ──
    st.write("")
    uploaded_zips = st.file_uploader("📁 '글로브' / '빌리브' ZIP 파일들을 올려주세요", type="zip", accept_multiple_files=True)
    
    if st.button("🚀 추출 및 병합 실행", type="primary", use_container_width=True):
        if not uploaded_zips:
            st.warning("ZIP 파일을 먼저 선택해 주세요.")
        else:
            with st.spinner("ZIP 파일을 분석하고 PDF를 추출하는 중입니다... 잠시만 기다려주세요!"):
                try:
                    def zip_sort_key(file_obj):
                        filename = file_obj.name
                        if '글로브' in filename: return 0
                        if '빌리브' in filename: return 1
                        return 2

                    sorted_zips = sorted(uploaded_zips, key=zip_sort_key)
                    date_match = re.search(r'(\d{8}|\d{6}|\d{4})', sorted_zips[0].name)
                    date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y%m%d")
                    
                    all_pdfs_to_merge = []
                    extracted_table_data = []

                    # ZIP 파일 분석 로직
                    for z_file in sorted_zips:
                        vendor = ('글로브' if '글로브' in z_file.name else ('빌리브' if '빌리브' in z_file.name else '기타'))
                        
                        with zipfile.ZipFile(z_file, 'r') as z:
                            g3_files = [f for f in z.namelist() if '가평3' in f and not f.endswith('/')]
                            if not g3_files: continue

                            subfolders = {}
                            for f in g3_files:
                                parts = f.split('/')
                                try:
                                    g_idx = next(i for i, p in enumerate(parts) if '가평3' in p)
                                    if g_idx + 1 < len(parts) - 1:
                                        subfolder_name = parts[g_idx + 1]
                                        if 'VFR3' in subfolder_name: continue
                                        subfolder_path = '/'.join(parts[:g_idx+2])
                                        if subfolder_path not in subfolders:
                                            subfolders[subfolder_path] = []
                                        subfolders[subfolder_path].append(f)
                                except StopIteration:
                                    continue

                            for sub_path in sorted(subfolders.keys()):
                                files_in_sub = subfolders[sub_path]
                                pdfs = [f for f in files_in_sub if f.lower().endswith('.pdf')]

                                num_pdf = None
                                receipt_pdf = None
                                for pf in pdfs:
                                    filename = os.path.splitext(os.path.basename(pf))[0].strip()
                                    if re.fullmatch(r'[\d\s\-_]+', filename):
                                        num_pdf = pf
                                    elif '거래명세서' in filename:
                                        receipt_pdf = pf

                                center_val = ""
                                pallet_val = ""
                                items = []
                                is_all_skipped = True

                                if num_pdf or receipt_pdf:
                                    # 발주서 숫자파일 분석
                                    if num_pdf:
                                        try:
                                            with pdfplumber.open(io.BytesIO(z.read(num_pdf))) as pdf:
                                                for page in pdf.pages:
                                                    text = page.extract_text() or ""
                                                    text_layout = page.extract_text(layout=True) or ""
                                                    words = page.extract_words()
                                                    all_words_text = "".join(w.get('text', '') for w in words).replace(" ", "")

                                                    if not center_val:
                                                        c_match = (re.search(r'받는\s*사람\s*:\s*([A-Za-z0-9가-힣\-]+)', text) or 
                                                                   re.search(r'받는\s*사람\s*:\s*([A-Za-z0-9가-힣\-]+)', text_layout) or 
                                                                   re.search(r'받는사람:([A-Za-z0-9가-힣\-]+)', all_words_text))
                                                        if c_match: center_val = c_match.group(1).strip()
                                                    
                                                    if not pallet_val:
                                                        p_match = (re.search(r'팔레트\s*수량\s*:\s*(\d+)', text) or 
                                                                   re.search(r'팔레트\s*수량\s*:\s*(\d+)', text_layout) or 
                                                                   re.search(r'팔레트수량:(\d+)', all_words_text))
                                                        if p_match: pallet_val = p_match.group(1).strip()
                                                            
                                                    if center_val and pallet_val: break
                                        except Exception as e:
                                            st.error(f"PDF 읽기 에러 ({os.path.basename(num_pdf)}): {e}")
                                            
                                        all_pdfs_to_merge.append((z_file, num_pdf, 'num'))

                                    # 거래명세서 분석
                                    if receipt_pdf:
                                        all_pdfs_to_merge.append((z_file, receipt_pdf, 'receipt'))
                                        try:
                                            with pdfplumber.open(io.BytesIO(z.read(receipt_pdf))) as pdf:
                                                for page in pdf.pages:
                                                    words = page.extract_words()
                                                    page_text_nospace = "".join(w.get('text', '') for w in words).replace(" ", "")
                                                    if "업체보관용" in page_text_nospace: continue
                                                    
                                                    is_all_skipped = False
                                                    text_layout = page.extract_text(layout=True) or ""
                                                    lines = text_layout.split('\n')
                                                    
                                                    for idx, line in enumerate(lines):
                                                        b_match = re.search(r'(PL\d+|880\d+)', line)
                                                        if b_match:
                                                            barcode_val = b_match.group(1).strip()
                                                            b_idx = b_match.start()
                                                            prod_val_parts = []
                                                            
                                                            for offset in (2, 1):
                                                                if idx - offset >= 0:
                                                                    prev_line = lines[idx - offset]
                                                                    for m in re.finditer(r'\S(?:.*?\S)?(?=\s{2,}|$)', prev_line):
                                                                        s, e = m.start(), m.end()
                                                                        if s - 25 <= b_idx <= e + 25:
                                                                            part = m.group().strip()
                                                                            if re.search(r'[가-힣a-zA-Z]', part):
                                                                                prod_val_parts.append(part)
                                                                            break
                                                            prod_val = (" ".join(prod_val_parts).strip() if prod_val_parts else "상품명 없음")
                                                            items.append((prod_val, barcode_val))
                                        except Exception as e:
                                            st.error(f"명세서 읽기 에러 ({os.path.basename(receipt_pdf)}): {e}")
                                    else:
                                        is_all_skipped = False

                                    # 표 데이터 추가
                                    if items:
                                        for i, (prod, bc) in enumerate(items):
                                            gubun = "A" if bc in st.session_state.type_a_barcodes else "K"
                                            disp_pallet = pallet_val if i == 0 else ""
                                            extracted_table_data.append((vendor, center_val, bc, prod, disp_pallet, gubun))
                                    elif receipt_pdf and is_all_skipped:
                                        extracted_table_data.append((vendor, center_val, "업체보관용(표추출제외)", "-", pallet_val, "K"))
                                    elif num_pdf or receipt_pdf:
                                        extracted_table_data.append((vendor, center_val, "-", "-", pallet_val, "K"))

                    # 병합 로직
                    if not all_pdfs_to_merge:
                        st.info("안내: 조건에 맞는 파일이 없습니다.")
                    else:
                        merger = PdfWriter()
                        
                        for z_file, pf, pdf_type in all_pdfs_to_merge:
                            with zipfile.ZipFile(z_file, 'r') as z:
                                pdf_bytes = z.read(pf)
                                temp_reader = PdfReader(io.BytesIO(pdf_bytes))
                                tot_pages = len(temp_reader.pages)
                                
                                if pdf_type == 'num':
                                    if tot_pages % 2 == 0:
                                        merger.append(io.BytesIO(pdf_bytes), pages=(0, tot_pages // 2))
                                    else:
                                        half = (tot_pages + 1) // 2
                                        if tot_pages >= 1:
                                            merger.append(io.BytesIO(pdf_bytes), pages=(0, 1))
                                        if half > 2:
                                            merger.append(io.BytesIO(pdf_bytes), pages=(2, half))
                                elif pdf_type == 'receipt':
                                    merger.append(io.BytesIO(pdf_bytes))

                        merged_pdf_buf = io.BytesIO()
                        merger.write(merged_pdf_buf)
                        merged_pdf_buf.seek(0)

                        st.success(f"✅ 성공적으로 {len(all_pdfs_to_merge)}개의 PDF가 처리되었습니다!")
                        
                        # 결과 테이블 출력
                        if extracted_table_data:
                            df = pd.DataFrame(extracted_table_data, columns=["벤더", "센터", "바코드", "상품명", "팔레트", "구분"])
                            st.dataframe(df, use_container_width=True)
                        
                        st.download_button(
                            label="📥 병합된 발주서 PDF 다운로드",
                            data=merged_pdf_buf,
                            file_name=f"가평3_{date_str}.pdf",
                            mime="application/pdf",
                            type="primary",
                            use_container_width=True
                        )

                except Exception as e:
                    st.error(f"오류가 발생했습니다: {e}")
    st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# [오른쪽 화면] 2. 부착물 자동생성
# =====================================================================
with col_right:
    st.markdown("### 🏷️ [2] 부착물 자동생성")
    st.markdown("<div style='background-color: #f0f2f5; padding: 15px; border-radius: 10px;'>", unsafe_allow_html=True)
    
    # ── 상수 및 폰트 설정 (요청하신 좌표/크기 적용) ──
    CENTERS  = ["대구2", "동탄1", "인천14", "이천2", "양산1", "고양1"]
    SKU_CODES = ["7391", "7392", "7715", "8834", "1959", "1960"]
    SKU_INFO  = {   
        "7391": (16, 30), "7392": (12, 45), "7715": (12, 45),
        "8834": (8,  16), "1959": (8,  96), "1960": (8,  96),
    }
    NUM_BLOCKS = 3
    ROWS_PER_BLOCK = 6

    TOTE_CENTER_XY   = (1248, 742)
    TOTE_SKU_XY      = (1120, 1050)
    TOTE_BOX_XY      = (1318, 1056)
    TOTE_UNIT_XY     = (1525, 1056)
    TOTE_CODE_XY     = (1617, 1152)

    CONT_CENTER_XY   = (1248, 742)
    CONT_SKU_XY      = (1525, 1063)

    def get_custom_font(size):
        font_path = "NanumSquare_acEB.ttf"
        try:
            return ImageFont.truetype(font_path, size)
        except IOError:
            st.error(f"🚨 '{font_path}' 폰트를 찾을 수 없습니다!")
            return ImageFont.load_default()

    def dc(draw, text, cx, cy, font):
        draw.text((cx, cy), text, font=font, fill='black', anchor='mm')

    def dc_right(draw, text, rx, y, font):
        b = draw.textbbox((0, 0), text, font=font)
        draw.text((rx - (b[2]-b[0]), y), text, font=font, fill='black')

    # ── PDF 생성 함수 ──
    def generate_attachment_pdf(rows, progress_cb=None):
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

        # 글자 크기 (요청 수치 적용)
        f_center = get_custom_font(220)
        f_num    = get_custom_font(110)
        f_code   = get_custom_font(30)

        for center, truck_cnt in center_trucks.items():
            for _ in range(truck_cnt):
                img = Image.open("container.jpg")
                draw = ImageDraw.Draw(img)
                dc(draw, center, *CONT_CENTER_XY, f_center)
                container_imgs.append(img)
                done += 1
                if progress_cb: progress_cb(done, total, f"컨테이너 생성 중... ({done}/{total})")

        for center, sku_code, plt_cnt, truck_cnt in rows:
            for _ in range(plt_cnt):
                box, unit = SKU_INFO[sku_code]
                img = Image.open("tote.jpg")
                draw = ImageDraw.Draw(img)
                dc(draw, center,       *TOTE_CENTER_XY, f_center)
                dc(draw, str(box),     *TOTE_BOX_XY,   f_num)
                dc(draw, str(unit),    *TOTE_UNIT_XY,  f_num)
                dc_right(draw, sku_code, TOTE_CODE_XY[0], TOTE_CODE_XY[1], f_code)
                tote_imgs.append(img)
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

    # ── 부착물 UI ──
    def reset_inputs():
        for b in range(NUM_BLOCKS):
            st.session_state[f"center_{b}"] = CENTERS[0]
            st.session_state[f"truck_{b}"] = 0
            for r in range(ROWS_PER_BLOCK):
                st.session_state[f"plt_{b}_{r}"] = 0

    if "initialized_att" not in st.session_state:
        reset_inputs()
        st.session_state["initialized_att"] = True

    block_cols = st.columns(3)
    for b in range(NUM_BLOCKS):
        with block_cols[b]:
            st.markdown("""<div style='background-color: #FFFF00; padding: 5px; text-align: center; border: 1px solid black; font-weight: bold;'>센터 및 트럭</div>""", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.selectbox("센터", options=CENTERS, key=f"center_{b}", label_visibility="collapsed")
            with c2:
                st.number_input("트럭", min_value=0, step=1, key=f"truck_{b}", label_visibility="collapsed")
            
            st.write("")
            st.markdown("""<div style='background-color: #FFFF00; padding: 5px; text-align: center; border: 1px solid black; font-weight: bold;'>상품 &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; 팔렛트</div>""", unsafe_allow_html=True)
            
            for r in range(ROWS_PER_BLOCK):
                c_sku, c_plt = st.columns([1, 1])
                with c_sku:
                    st.markdown(f"<div style='text-align: center; padding-top: 10px; font-weight: bold;'>{SKU_CODES[r]}</div>", unsafe_allow_html=True)
                with c_plt:
                    st.number_input("plt", min_value=0, step=1, key=f"plt_{b}_{r}", label_visibility="collapsed")

    st.write("")
    btn1, btn2 = st.columns([1, 2])
    with btn1:
        if st.button("🔄 초기화", use_container_width=True):
            reset_inputs()
            st.rerun()
    with btn2:
        generate_clicked = st.button("📄 부착물 PDF 생성", type="primary", use_container_width=True)

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
                prog_bar = st.progress(0)
                stat_txt = st.empty()
                def update_prog(done, total, msg):
                    prog_bar.progress(done / total)
                    stat_txt.text(msg)
                
                pdf_bytes, cont_cnt, tote_cnt = generate_attachment_pdf(rows, progress_cb=update_prog)
                
                prog_bar.empty()
                stat_txt.empty()
                
                st.success(f"✅ 완료! (컨테이너 {cont_cnt}장, 토트 {tote_cnt}장)")
                st.download_button(
                    label="📥 부착물 PDF 다운로드",
                    data=pdf_bytes,
                    file_name="부착물.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
            except FileNotFoundError:
                st.error("🚨 `container.jpg` 또는 `tote.jpg` 파일을 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"오류 발생: {e}")
                
    st.markdown("</div>", unsafe_allow_html=True)
