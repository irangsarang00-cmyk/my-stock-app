import streamlit as st

# 데스크톱 화면 전체를 활용할 수 있도록 레이아웃을 넓게(wide) 설정합니다.
st.set_page_config(
    page_title="창고 관리 시스템",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 메인 화면 타이틀
st.title("📦 창고 관리 메인 화면")
st.divider() # 시각적 분리를 위한 선

# 크게 2개의 탭을 생성합니다.
tab1, tab2 = st.tabs(["🏭 1창고", "🏭 3창고"])

# 1창고 탭에 들어갈 내용
with tab1:
    st.subheader("1창고 현황")
    st.info("이곳에 1창고와 관련된 데이터, 재고 표, 혹은 기능 버튼들이 들어갈 예정입니다.")
    # TODO: 기존 py 파일의 1창고 관련 로직과 UI 컴포넌트 추가

# 3창고 탭에 들어갈 내용
with tab2:
    st.subheader("3창고 현황")
    st.info("이곳에 3창고와 관련된 데이터, 재고 표, 혹은 기능 버튼들이 들어갈 예정입니다.")
    # TODO: 기존 py 파일의 3창고 관련 로직과 UI 컴포넌트 추가
