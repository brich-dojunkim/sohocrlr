import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Selenium 관련
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# webdriver-manager로 크롬드라이버 버전 자동 관리 (필요 시)
from webdriver_manager.chrome import ChromeDriverManager

# -----------------------------------------------------------
# 1. 웹드라이버 / 브라우저 환경 세팅
# -----------------------------------------------------------

options = webdriver.ChromeOptions()
options.add_argument("window-size=1920x1080")  # 브라우저 크기
options.add_argument("disable-gpu")
options.add_argument("disable-infobars")
options.add_argument("--disable-extensions")
options.add_argument('--no-sandbox')

service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)
driver.implicitly_wait(3)

# -----------------------------------------------------------
# 2. 크롤링에 필요한 사전 작업 (사이트 열기 & 버튼 클릭)
# -----------------------------------------------------------

# (2-1) 원하는 상품 페이지 열기
target_url = 'https://brand.naver.com/onnon/products/8045986719'
driver.get(target_url)
time.sleep(3)

# (2-1-1) 상품 제목 가져오기
html_source = driver.page_source
soup = BeautifulSoup(html_source, 'html.parser')
title_tag = soup.find('h3', {'class': '_22kNQuEXmb _copyable'})
if title_tag:
    product_title = title_tag.get_text(strip=True)
else:
    product_title = ""  # 혹은 None
print("[INFO] 상품 제목:", product_title)

# (2-2) "리뷰" 탭 버튼 클릭
driver.find_element(By.CSS_SELECTOR,
    '#content > div > div.z7cS6-TO7X > div._27jmWaPaKy > ul > li:nth-child(2) > a'
).click()
time.sleep(3)
print("[INFO] 리뷰 탭 클릭 완료.")

# (2-3) "최신순" 버튼 클릭
try:
    driver.find_element(By.CSS_SELECTOR,
        '#REVIEW > div > div._2LvIMaBiIO > div._2LAwVxx1Sd > div._1txuie7UTH > ul > li:nth-child(2) > a'
    ).click()
    time.sleep(3)
    print("[INFO] 최신순 버튼 클릭 완료.")
except:
    print("[WARN] 최신순 버튼 클릭 실패.")

# -----------------------------------------------------------
# 3. 리뷰데이터 수집을 위한 리스트 초기화
# -----------------------------------------------------------
write_dt_lst = []
rating_lst = []   # 평점을 담을 리스트 추가
item_nm_lst = []
content_lst = []

# -----------------------------------------------------------
# 4. 여러 페이지 리뷰를 반복적으로 수집하기
#    (예: 최근 1년 기준 수집)
# -----------------------------------------------------------

page_num = 1
page_ctl = 3  # 2페이지 버튼은 nth-child(3)

# 최근 1년 날짜 기준(수집 종료)
# date_cut = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

while True:
    print(f"[INFO] {page_num} 페이지 수집 중 ... (page_ctl={page_ctl})")

    # 4-1. 현재 페이지 HTML 파싱
    html_source = driver.page_source
    soup = BeautifulSoup(html_source, 'html.parser')
    time.sleep(0.5)

    # 4-2. 현재 페이지에 표시된 모든 리뷰 블록 찾기 (find_all 사용)
    reviews = soup.find_all('li', {'class': 'BnwL_cs1av'})

    # 4-3. 리뷰마다 날짜, 평점, 상품명, 리뷰내용을 수집
    for r in reviews:
        # (a) 리뷰 작성 일자
        write_dt_raw = r.find_all('span', {'class': '_2L3vDiadT9'})[0].get_text()
        # 'yy.mm.dd.' → YYYYMMDD
        write_dt = datetime.strptime(write_dt_raw, '%y.%m.%d.').strftime('%Y%m%d')

        # (b) 평점
        rating_tag = r.find('em', {'class': '_15NU42F3kT'})
        if rating_tag:
            rating = rating_tag.get_text(strip=True)
        else:
            rating = ""

        # (c) 상품명(옵션명)
        item_div = r.find_all('div', {'class': '_2FXNMst_ak'})[0]
        item_nm_info_raw = item_div.get_text()

        # dl 태그(XbGQRlzveO) 부분이 없을 경우 방어 처리
        dl_tag = item_div.find('dl', {'class': 'XbGQRlzveO'})
        if dl_tag:
            item_nm_info_for_del = dl_tag.get_text()
        else:
            item_nm_info_for_del = ""

        item_nm_info = re.sub(item_nm_info_for_del, '', item_nm_info_raw)
        str_start_idx = item_nm_info.find('제품 선택: ')
        if str_start_idx != -1:
            item_nm = item_nm_info[str_start_idx + 6:].strip()
        else:
            item_nm = ""

        # (d) 리뷰 내용
        content_raw = r.find_all('div', {'class': '_1kMfD5ErZ6'})[0] \
                       .find('span', {'class': '_2L3vDiadT9'}) \
                       .get_text()
        review_content = re.sub(' +', ' ', re.sub('\n', ' ', content_raw))

        # (e) 리스트에 저장
        write_dt_lst.append(write_dt)
        rating_lst.append(rating)
        item_nm_lst.append(item_nm)
        content_lst.append(review_content)

    # 4-4. 최근 1년 기준으로 멈출지 확인
    # if write_dt_lst and write_dt_lst[-1] < date_cut:
    #     print("[INFO] 기준 날짜 도달. 크롤링을 종료합니다.")
    #     break

    # 4-5. 다음 페이지로 이동 (페이지 버튼 클릭)
    try:
        driver.find_element(By.CSS_SELECTOR,
            f'#REVIEW > div > div._2LvIMaBiIO > div._2g7PKvqCKe > div > div > a:nth-child({page_ctl})'
        ).click()
    except:
        print("[INFO] 더 이상 이동할 페이지가 없습니다. 종료합니다.")
        break

    time.sleep(3)
    page_num += 1
    page_ctl += 1

    # (추가) 10페이지 넘어갈 때 page_ctl 재설정
    if page_num % 10 == 1:
        page_ctl = 3

print("크롤링 완료!")

# -----------------------------------------------------------
# 5. 데이터프레임으로 정리 후 CSV 파일로 저장
# -----------------------------------------------------------
result_df = pd.DataFrame({
    'RD_WRITE_DT': write_dt_lst,
    'RD_RATING': rating_lst,
    'RD_ITEM_NM': item_nm_lst,
    'RD_CONTENT': content_lst
})

# (5-1) 상품 제목 열을 추가 (모든 리뷰 행에 동일 값)
result_df['PRODUCT_TITLE'] = product_title

# CSV 저장
result_df.to_csv('navershopping_review_data.csv', index=False, encoding='utf-8-sig')
print("CSV 저장 완료!")
print(f"총 {len(result_df)}건의 리뷰가 수집되었으며, 상품 제목은 '{product_title}' 입니다.")
