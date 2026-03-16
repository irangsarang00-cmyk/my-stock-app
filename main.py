import os
import time
import glob
import json
import pandas as pd
from playwright.sync_api import sync_playwright
import gspread
from oauth2client.service_account import ServiceAccountCredentials

def get_credentials_and_sheet():
    print("구글 시트에서 아이디와 비밀번호를 가져오는 중...")
    
    # 1. 깃허브 금고에 있는 구글 열쇠 꺼내기 (이건 꼭 있어야 시트를 읽을 수 있어요!)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    google_secret_json = os.environ.get("GOOGLE_JSON")
    creds_dict = json.loads(google_secret_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)

    # 2. 알려주신 주소의 구글 시트 바로 열기
    sheet_url = "https://docs.google.com/spreadsheets/d/1J5RwYs3IVCm9f0IsCjwtrSerOGdx_J3f3r0o72BgrTA/edit"
    spreadsheet = client.open_by_url(sheet_url)
    
    # 3. '시트3' 탭 선택하기
    worksheet3 = spreadsheet.worksheet("시트3")

    # 4. Z1~Z4 셀에 있는 아이디와 비밀번호 읽어오기
    # (빈칸일 수도 있으니 값이 없으면 빈 문자로 처리해요)
    account1_id = worksheet3.acell('Z1').value or ""
    account1_pw = worksheet3.acell('Z2').value or ""
    account2_id = worksheet3.acell('Z3').value or ""
    account2_pw = worksheet3.acell('Z4').value or ""

    accounts = [
        {"id": account1_id, "pw": account1_pw},
        {"id": account2_id, "pw": account2_pw}
    ]
    
    # 다 쓴 구글 연결 객체는 나중에 업로드할 때 또 써야 하니까 같이 넘겨줍니다.
    return accounts, spreadsheet

def run_crawler(accounts):
    download_dir = os.path.join(os.getcwd(), "downloads")
    os.makedirs(download_dir, exist_ok=True)

    with sync_playwright() as p:
        # 깃허브에서 돌아가니까 화면은 안 보이게 (headless=True) 설정해요.
        browser = p.chromium.launch(headless=True) 

        for account in accounts:
            if not account['id']: # 시트에 아이디가 안 적혀 있으면 건너뜁니다.
                continue
                
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            print(f"[{account['id']}] 쿠팡 접속 중...")

            # 로그인
            page.goto("https://supplier.coupang.com/dashboard/KR")
            page.goto("https://supplier.coupang.com/dashboard/KR")
            page.wait_for_load_state('networkidle')
            page.screenshot(path=f"error_screen_{account['id']}.png")
            print("화면 스크린샷을 찍었습니다!")
            page.locator('input[name="username"]').fill(account['id'])
            page.locator('input[name="password"]').fill(account['pw'])
            page.locator('button[type="submit"].btn-primary').click()
            page.wait_for_load_state('networkidle')

            # 발주서 페이지 이동 및 다운로드
            page.goto("https://supplier.coupang.com/po-web/cplb/po/sku/list")
            page.wait_for_load_state('networkidle')
            page.locator('button.btn-outline-secondary:has-text("Today")').click()
            page.locator('button.btn-primary:has-text("Search")').click()
            time.sleep(3)

            with page.expect_download() as download_info:
                page.locator('button.download-button').click()

            download = download_info.value
            file_path = os.path.join(download_dir, f"PO_{account['id']}_{download.suggested_filename}")
            download.save_as(file_path)
            
            context.close()
        browser.close()

def upload_to_google_sheet(spreadsheet):
    download_dir = os.path.join(os.getcwd(), "downloads")
    all_files = glob.glob(os.path.join(download_dir, "*.csv"))
    
    if not all_files:
        print("새로 다운받은 발주서가 없네요.")
        return

    df_list = []
    for f in all_files:
        temp_df = pd.read_csv(f)
        df_list.append(temp_df)
    
    final_df = pd.concat(df_list, ignore_index=True)

    # 필요한 열만 골라내기
    columns_to_keep = ['Order number', 'Order Status', 'SKU name', 'SKU Barcode', 'ETA', 'Order Quantity', 'Firm quantity']
    available_columns = [col for col in columns_to_keep if col in final_df.columns]
    final_df = final_df[available_columns]

    # 상태 값 한글로 예쁘게 바꾸기
    status_mapping = {
        'Request Partner Confirmation': '확정 전',
        'Confirm Purchase Order': '확정 완료'
    }
    if 'Order Status' in final_df.columns:
        final_df['Order Status'] = final_df['Order Status'].map(status_mapping).fillna(final_df['Order Status'])

    # 발주 데이터를 올릴 '시트1' 탭 선택 (이름이 다르면 꼭 수정해 주세요!)
    worksheet1 = spreadsheet.worksheet("시트1")

    # 기존 데이터 싹 지우고 새 데이터 엎어치기
    worksheet1.clear()
    worksheet1.update([final_df.columns.values.tolist()] + final_df.fillna("").values.tolist())
    print("구글 시트에 발주서 정리 완료!")

if __name__ == "__main__":
    # 1. 시트에서 아이디/비밀번호 가져오기
    accounts_info, target_spreadsheet = get_credentials_and_sheet()
    
    # 2. 가져온 정보로 크롤링 시작하기
    run_crawler(accounts_info)
    
    # 3. 받아온 엑셀을 다시 구글 시트에 올리기
    upload_to_google_sheet(target_spreadsheet)
    
