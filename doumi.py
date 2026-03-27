import streamlit as st
import io
import os
import re
import zipfile
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter, PdfReader
import pdfplumber
import pandas as pd
import openpyxl
import logging

logging.getLogger("pdfminer").setLevel(logging.ERROR)

st.set_page_config(page_title="가평 업무 도우미", layout="wide")

tab_3창고, tab_1창고 = st.tabs(["🏭 3창고", "🏢 1창고"])


# =====================================================================
# 3창고 탭
# =====================================================================
with tab_3창고:
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("### 📄 [1] 3창고 서류 취합")
        st.markdown("<div style='background-color: #f0f2f5; padding: 15px; border-radius: 10px;'>", unsafe_allow_html=True)

        uploaded_zips = st.file_uploader("📁 ZIP 파일 업로드", type="zip", accept_multiple_files=True, key="zip_uploader")

        if st.button("🚀 실행", type="primary", use_container_width=True, key="run_btn"):
            if not uploaded_zips:
                st.warning("ZIP 파일 선택 필요")
            else:
                with st.spinner("처리중"):
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

                                    if num_pdf or receipt_pdf:
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
                                                st.error(f"읽기 에러: {e}")

                                            all_pdfs_to_merge.append((z_file, num_pdf, 'num'))

                                        if receipt_pdf:
                                            all_pdfs_to_merge.append((z_file, receipt_pdf, 'receipt'))

                                        extracted_table_data.append((vendor, center_val, pallet_val))

                        if not all_pdfs_to_merge:
                            st.info("조건에 맞는 파일 없음")
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

                            st.success("병합 완료")

                            if extracted_table_data:
                                df = pd.DataFrame(extracted_table_data, columns=["벤더", "센터", "팔레트"])
                                st.dataframe(df, use_container_width=True)

                            st.download_button(
                                label="📥 다운로드",
                                data=merged_pdf_buf,
                                file_name=f"가평3_{date_str}.pdf",
                                mime="application/pdf",
                                type="primary",
                                use_container_width=True
                            )

                    except Exception as e:
                        st.error(f"오류: {e}")
        st.markdown("</div>", unsafe_allow_html=True)

    # ─────────────────────────────────────────────────────────────────
    # VFR3 부착물 생성
    # ─────────────────────────────────────────────────────────────────
    with col_right:
        st.markdown("### 🏷️ [2] VFR3 부착물 생성")
        st.markdown("<div style='background-color: #f0f2f5; padding: 15px; border-radius: 10px;'>", unsafe_allow_html=True)

        CENTERS   = ["대구2", "동탄1", "인천14", "이천2", "양산1", "고양1"]
        SKU_CODES = ["7391", "7392", "7715", "8834", "1959", "1960"]
        SKU_INFO  = {
            "7391": (16, 30), "7392": (12, 45), "7715": (12, 45),
            "8834": (8,  16), "1959": (8,  96), "1960": (8,  96),
        }
        NUM_BLOCKS     = 3
        ROWS_PER_BLOCK = 6

        TOTE_CENTER_XY = (1248, 742)
        TOTE_BOX_XY    = (1318, 1056)
        TOTE_UNIT_XY   = (1525, 1056)
        TOTE_CODE_XY   = (1617, 1152)
        CONT_CENTER_XY = (1248, 742)

        def get_custom_font(size):
            font_path = "NanumSquare_acEB.ttf"
            try:
                return ImageFont.truetype(font_path, size)
            except IOError:
                return ImageFont.load_default()

        def dc(draw, text, cx, cy, font):
            draw.text((cx, cy), text, font=font, fill='black', anchor='mm')

        def dc_right(draw, text, rx, y, font):
            b = draw.textbbox((0, 0), text, font=font)
            draw.text((rx - (b[2]-b[0]), y), text, font=font, fill='black')

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
                    if progress_cb: progress_cb(done, total, f"컨테이너 생성중 ({done}/{total})")

            for center, sku_code, plt_cnt, truck_cnt in rows:
                for _ in range(plt_cnt):
                    box, unit = SKU_INFO[sku_code]
                    img = Image.open("tote.jpg")
                    draw = ImageDraw.Draw(img)
                    dc(draw, center,    *TOTE_CENTER_XY, f_center)
                    dc(draw, str(box),  *TOTE_BOX_XY,   f_num)
                    dc(draw, str(unit), *TOTE_UNIT_XY,  f_num)
                    dc_right(draw, sku_code, TOTE_CODE_XY[0], TOTE_CODE_XY[1], f_code)
                    tote_imgs.append(img)
                    done += 1
                    if progress_cb: progress_cb(done, total, f"토트 생성중 ({done}/{total})")

            all_imgs = container_imgs + tote_imgs
            if not all_imgs:
                raise ValueError("생성할 페이지 없음")

            first = all_imgs[0].convert('RGB')
            rest  = [i.convert('RGB') for i in all_imgs[1:]]

            pdf_buf = io.BytesIO()
            first.save(pdf_buf, format='PDF', save_all=True, append_images=rest)
            pdf_buf.seek(0)
            return pdf_buf, len(container_imgs), len(tote_imgs)

        def reset_inputs():
            for b in range(NUM_BLOCKS):
                st.session_state[f"center_{b}"] = CENTERS[0]
                st.session_state[f"truck_{b}"]  = 0
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
            st.button("🔄 초기화", use_container_width=True, on_click=reset_inputs)
        with btn2:
            generate_clicked = st.button("📄 생성", type="primary", use_container_width=True)

        if generate_clicked:
            rows = []
            for b in range(NUM_BLOCKS):
                center = st.session_state[f"center_{b}"]
                truck  = st.session_state[f"truck_{b}"]
                for r in range(ROWS_PER_BLOCK):
                    plt_cnt = st.session_state[f"plt_{b}_{r}"]
                    if plt_cnt > 0:
                        rows.append((center, SKU_CODES[r], plt_cnt, truck))

            if not rows:
                st.warning("수량 입력 필요")
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

                    st.success(f"생성 완료 (컨테이너 {cont_cnt}, 토트 {tote_cnt})")
                    st.download_button(
                        label="📥 PDF 다운로드",
                        data=pdf_bytes,
                        file_name="부착물.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                except FileNotFoundError:
                    st.error("이미지 파일 없음")
                except Exception as e:
                    st.error(f"오류: {e}")

        st.markdown("</div>", unsafe_allow_html=True)


# =====================================================================
# 1창고 탭
# =====================================================================
with tab_1창고:

    sub_a, sub_f, sub_g = st.tabs([
        "📦 [A] 쿠팡 택배송장 추출",
        "🖨️ [F] 가평1 발주서 추출",
        "✂️ [G] 라벨 4등분 & 명세서 병합",
    ])

    # ==================================================================
    # [A] 쿠팡 택배송장 추출 (매칭사전 제외)
    # ==================================================================
    with sub_a:
        st.markdown("### 📦 쿠팡 택배송장 양식 추출")
        st.info(
            "ZIP 또는 엑셀 파일을 업로드하면 택배송장 양식으로 변환합니다.\n"
            "ZIP 파일은 내부에서 파일명에 **'택배'** 가 포함된 엑셀만 자동 인식합니다."
        )

        uploaded_a = st.file_uploader(
            "📁 엑셀 또는 ZIP 파일 업로드 (복수 선택 가능)",
            type=["xlsx", "xls", "zip"],
            accept_multiple_files=True,
            key="uploader_a"
        )

        if st.button("🚀 추출 실행", type="primary", use_container_width=True, key="run_a"):
            if not uploaded_a:
                st.warning("파일을 먼저 업로드해주세요.")
            else:
                with st.spinner("처리중..."):
                    try:
                        def get_formatted_df_a(file_obj):
                            wb = openpyxl.load_workbook(file_obj, data_only=True)
                            ws = wb.active
                            active_sheet = ws.title
                            hidden_rows = [i for i, row in ws.row_dimensions.items() if row.hidden]
                            if hasattr(file_obj, 'seek'):
                                file_obj.seek(0)
                            df = pd.read_excel(file_obj, sheet_name=active_sheet, dtype=str)
                            to_drop = [r - 2 for r in hidden_rows if r >= 2 and (r - 2) < len(df)]
                            df = df.drop(df.index[to_drop]).reset_index(drop=True)
                            try:
                                extracted = pd.DataFrame()
                                extracted['A'] = df.iloc[:, 0].fillna('').astype(str).str.strip()
                                extracted['B'] = df.iloc[:, 1].fillna('').astype(str).str.strip()
                                extracted['C'] = df.iloc[:, 2].fillna('').astype(str).str.strip()
                                extracted['D'] = ""
                                extracted['E'] = df.iloc[:, 5].fillna('').astype(str).str.strip()
                                extracted['F'] = df.iloc[:, 11].fillna('').astype(str).str.strip()
                                extracted['G'] = "1"
                                extracted['H'] = ""
                                extracted['I'] = ""
                                return extracted
                            except IndexError:
                                return pd.DataFrame()

                        all_dfs_a = []
                        for uploaded_file in uploaded_a:
                            if uploaded_file.name.lower().endswith('.zip'):
                                with zipfile.ZipFile(uploaded_file, 'r') as z:
                                    excel_files = [
                                        f for f in z.namelist()
                                        if '택배' in f and f.endswith(('.xlsx', '.xls'))
                                        and '__MACOSX' not in f
                                        and not f.split('/')[-1].startswith('._')
                                    ]
                                    for file_name in excel_files:
                                        with z.open(file_name) as f:
                                            f_df = get_formatted_df_a(io.BytesIO(f.read()))
                                            if not f_df.empty:
                                                all_dfs_a.append(f_df)
                            elif uploaded_file.name.lower().endswith(('.xlsx', '.xls')):
                                f_df = get_formatted_df_a(uploaded_file)
                                if not f_df.empty:
                                    all_dfs_a.append(f_df)

                        if not all_dfs_a:
                            st.warning("유효한 엑셀 데이터를 찾지 못했습니다.")
                        else:
                            result_df = pd.concat(all_dfs_a, ignore_index=True)
                            result_df['B'] = result_df['B'].replace(['nan', '0.0'], '')
                            result_df = result_df[
                                result_df['A'].str.strip().ne('') &
                                result_df['A'].ne('nan')
                            ]

                            display_df = result_df.copy()
                            display_df.columns = ["A:성명", "B:전화번호", "C:주소", "D:(빈칸)", "E:품목명", "F:바코드", "G:수량", "H:박스타입", "I:메모"]

                            st.success(f"✅ 추출 완료 — {len(result_df)}건")
                            st.dataframe(display_df, use_container_width=True, height=350)

                            out_buf = io.BytesIO()
                            result_df.to_excel(out_buf, index=False, header=False)
                            out_buf.seek(0)
                            today = datetime.now().strftime("%Y%m%d")
                            st.download_button(
                                label="📥 엑셀 다운로드",
                                data=out_buf,
                                file_name=f"택배송장양식_쿠팡_{today}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                type="primary",
                                use_container_width=True
                            )

                    except Exception as e:
                        st.error(f"오류: {e}")

    # ==================================================================
    # [F] 가평1 발주서 추출 및 PDF 병합
    # ==================================================================
    with sub_f:
        st.markdown("### 🖨️ 가평1 발주서 추출 및 PDF 병합")
        st.info(
            "ZIP 파일을 업로드하면 **'가평1'** 폴더 내 발주서를 자동으로 추출·병합합니다.\n"
            "글로브 → 빌리브 순으로 정렬되며, 숫자 파일명 PDF의 절반 + 거래명세서를 합칩니다."
        )

        uploaded_f = st.file_uploader(
            "📁 ZIP 파일 업로드 (글로브/빌리브, 복수 선택 가능)",
            type="zip",
            accept_multiple_files=True,
            key="uploader_f"
        )

        if st.button("🚀 추출 및 병합 실행", type="primary", use_container_width=True, key="run_f"):
            if not uploaded_f:
                st.warning("ZIP 파일을 먼저 업로드해주세요.")
            else:
                with st.spinner("처리중..."):
                    try:
                        def zip_sort_key_f(file_obj):
                            n = file_obj.name
                            if '글로브' in n: return 0
                            if '빌리브' in n: return 1
                            return 2

                        sorted_zips_f = sorted(uploaded_f, key=zip_sort_key_f)
                        date_match = re.search(r'(\d{8}|\d{6}|\d{4})', sorted_zips_f[0].name)
                        date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y%m%d")

                        all_pdfs_f   = []
                        table_data_f = []

                        for z_file in sorted_zips_f:
                            vendor = '글로브' if '글로브' in z_file.name else ('빌리브' if '빌리브' in z_file.name else '기타')

                            with zipfile.ZipFile(z_file, 'r') as z:
                                g1_files = [f for f in z.namelist() if '가평1' in f and not f.endswith('/')]
                                if not g1_files:
                                    continue

                                subfolders = {}
                                for f in g1_files:
                                    parts = f.split('/')
                                    try:
                                        g_idx = next(i for i, p in enumerate(parts) if '가평1' in p)
                                        if g_idx + 1 < len(parts) - 1:
                                            if 'VFR3' in parts[g_idx + 1]:
                                                continue
                                            sf_path = '/'.join(parts[:g_idx+2])
                                            subfolders.setdefault(sf_path, []).append(f)
                                    except StopIteration:
                                        continue

                                for sub_path in sorted(subfolders.keys()):
                                    pdfs = [f for f in subfolders[sub_path] if f.lower().endswith('.pdf')]
                                    num_pdf     = None
                                    receipt_pdf = None
                                    for pf in pdfs:
                                        fname = os.path.splitext(os.path.basename(pf))[0].strip()
                                        if re.fullmatch(r'[\d\s\-_]+', fname):
                                            num_pdf = pf
                                        elif '거래명세서' in fname:
                                            receipt_pdf = pf

                                    center_val = ""
                                    pallet_val = ""

                                    if num_pdf or receipt_pdf:
                                        if num_pdf:
                                            try:
                                                with pdfplumber.open(io.BytesIO(z.read(num_pdf))) as pdf:
                                                    for page in pdf.pages:
                                                        text        = page.extract_text() or ""
                                                        text_layout = page.extract_text(layout=True) or ""
                                                        words       = page.extract_words()
                                                        all_w       = "".join(w.get('text', '') for w in words).replace(" ", "")
                                                        if not center_val:
                                                            m = (re.search(r'받는\s*사람\s*:\s*([A-Za-z0-9가-힣\-]+)', text) or
                                                                 re.search(r'받는\s*사람\s*:\s*([A-Za-z0-9가-힣\-]+)', text_layout) or
                                                                 re.search(r'받는사람:([A-Za-z0-9가-힣\-]+)', all_w))
                                                            if m: center_val = m.group(1).strip()
                                                        if not pallet_val:
                                                            m = (re.search(r'팔레트\s*수량\s*:\s*(\d+)', text) or
                                                                 re.search(r'팔레트\s*수량\s*:\s*(\d+)', text_layout) or
                                                                 re.search(r'팔레트수량:(\d+)', all_w))
                                                            if m: pallet_val = m.group(1).strip()
                                                        if center_val and pallet_val:
                                                            break
                                            except Exception:
                                                pass
                                            all_pdfs_f.append((z_file, num_pdf, 'num'))

                                        if receipt_pdf:
                                            all_pdfs_f.append((z_file, receipt_pdf, 'receipt'))

                                        table_data_f.append((vendor, center_val, pallet_val))

                        if not all_pdfs_f:
                            st.warning("조건에 맞는 가평1 파일을 찾지 못했습니다.")
                        else:
                            merger = PdfWriter()
                            for z_file, pf, pdf_type in all_pdfs_f:
                                with zipfile.ZipFile(z_file, 'r') as z:
                                    pdf_bytes   = z.read(pf)
                                    temp_reader = PdfReader(io.BytesIO(pdf_bytes))
                                    tot         = len(temp_reader.pages)
                                    if pdf_type == 'num':
                                        if tot % 2 == 0:
                                            merger.append(io.BytesIO(pdf_bytes), pages=(0, tot // 2))
                                        else:
                                            half = (tot + 1) // 2
                                            if tot >= 1:
                                                merger.append(io.BytesIO(pdf_bytes), pages=(0, 1))
                                            if half > 2:
                                                merger.append(io.BytesIO(pdf_bytes), pages=(2, half))
                                    else:
                                        merger.append(io.BytesIO(pdf_bytes))

                            out_buf = io.BytesIO()
                            merger.write(out_buf)
                            out_buf.seek(0)

                            st.success(f"✅ 병합 완료 — PDF {len(all_pdfs_f)}개 처리")

                            if table_data_f:
                                df_f = pd.DataFrame(table_data_f, columns=["벤더", "센터", "팔레트"])
                                st.dataframe(df_f, use_container_width=True, height=300)

                            st.download_button(
                                label="📥 병합 PDF 다운로드",
                                data=out_buf,
                                file_name=f"가평1_{date_str}.pdf",
                                mime="application/pdf",
                                type="primary",
                                use_container_width=True
                            )

                    except Exception as e:
                        st.error(f"오류: {e}")

    # ==================================================================
    # [G] 라벨 4등분 & 명세서 연속 병합
    # ==================================================================
    with sub_g:
        st.markdown("### ✂️ 라벨 4등분 & 명세서 연속 병합")
        st.info(
            "ZIP 파일을 업로드하면 내부 PDF를 자동으로 분류·처리합니다.\n"
            "- **Label** 파일 → 4장씩 한 페이지에 모아찍기 (4등분)\n"
            "- **ManiFest** 파일 → 원본 그대로 이어 붙이기"
        )

        uploaded_g = st.file_uploader(
            "📁 ZIP 파일 업로드 (글로브/빌리브, 복수 선택 가능)",
            type="zip",
            accept_multiple_files=True,
            key="uploader_g"
        )

        if st.button("🚀 4등분 & 병합 실행", type="primary", use_container_width=True, key="run_g"):
            if not uploaded_g:
                st.warning("ZIP 파일을 먼저 업로드해주세요.")
            else:
                with st.spinner("처리중..."):
                    try:
                        from pypdf import PageObject, Transformation

                        def zip_sort_key_g(file_obj):
                            n = file_obj.name
                            if '글로브' in n: return 0
                            if '빌리브' in n: return 1
                            return 2

                        sorted_zips_g = sorted(uploaded_g, key=zip_sort_key_g)

                        label_pages   = []
                        manifest_data = []

                        for z_file in sorted_zips_g:
                            with zipfile.ZipFile(z_file, 'r') as z:
                                for f in z.namelist():
                                    if f.endswith('/') or not f.lower().endswith('.pdf'):
                                        continue
                                    base_n    = os.path.basename(f).lower()
                                    pdf_bytes = z.read(f)
                                    if 'label' in base_n:
                                        for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
                                            label_pages.append(page)
                                    elif 'manifest' in base_n:
                                        manifest_data.append(pdf_bytes)

                        if not label_pages and not manifest_data:
                            st.warning("'Label' 또는 'ManiFest' 파일을 찾지 못했습니다.")
                        else:
                            final_writer = PdfWriter()

                            # Label → 4등분
                            if label_pages:
                                w = float(label_pages[0].mediabox.width)
                                h = float(label_pages[0].mediabox.height)
                                positions = [(0, h/2), (w/2, h/2), (0, 0), (w/2, 0)]

                                for i in range(0, len(label_pages), 4):
                                    chunk = label_pages[i:i+4]
                                    blank = PageObject.create_blank_page(width=w, height=h)
                                    for j, page in enumerate(chunk):
                                        tx, ty = positions[j]
                                        try:
                                            op = Transformation().scale(sx=0.5, sy=0.5).translate(tx=tx, ty=ty)
                                            page.add_transformation(op)
                                            blank.merge_page(page)
                                        except Exception:
                                            try:
                                                blank.mergeScaledTranslatedPage(page, 0.5, tx, ty)
                                            except Exception:
                                                pass
                                    final_writer.add_page(blank)

                            # ManiFest → 이어 붙이기
                            for pdf_bytes in manifest_data:
                                for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
                                    final_writer.add_page(page)

                            out_buf = io.BytesIO()
                            final_writer.write(out_buf)
                            out_buf.seek(0)

                            label_page_count = (len(label_pages) + 3) // 4
                            date_str         = datetime.now().strftime("%Y%m%d_%H%M%S")

                            st.success(
                                f"✅ 완료 — "
                                f"Label {len(label_pages)}장 → {label_page_count}페이지, "
                                f"ManiFest {len(manifest_data)}개 병합"
                            )
                            st.download_button(
                                label="📥 병합 PDF 다운로드",
                                data=out_buf,
                                file_name=f"라벨_명세서_통합_{date_str}.pdf",
                                mime="application/pdf",
                                type="primary",
                                use_container_width=True
                            )

                    except Exception as e:
                        st.error(f"오류: {e}")
