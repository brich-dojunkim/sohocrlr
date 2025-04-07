import time
import csv

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

def scrape_multiple_pages(page_url: str, max_page: int, output_csv: str):
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # 필요시 헤드리스 모드
    driver = webdriver.Chrome(service=service, options=options)

    all_urls = set()

    try:
        driver.get(page_url)
        time.sleep(3)  # 페이지 로딩 대기

        for page in range(1, max_page + 1):
            # ---- (A) 현재 페이지의 상품 URL 수집 ----
            soup = BeautifulSoup(driver.page_source, "html.parser")
            cards = soup.select('li[class*="ZdiAiTrQWZ"] a._nlog_click._nlog_impression_element[data-shp-area="list.pd"]')
            for card in cards:
                href = card.get('href')
                if href:
                    all_urls.add(href)

            print(f"[페이지 {page}] 상품 {len(cards)}개 수집 (누적 {len(all_urls)}개)")

            if page == max_page:
                break  # 원하는 페이지 수만큼 돌았다면 종료

            # ---- (C) 페이지네이션에서 다음 페이지 클릭 ----
            # find_elements(By.CSS_SELECTOR, 'CSS 셀렉터') 형식으로 변경
            pagination_links = driver.find_elements(
                By.CSS_SELECTOR,
                'div[role="menubar"] a.UWN4IvaQza._nlog_click'
            )

            next_page_str = str(page + 1)
            found_next_page = False
            for link in pagination_links:
                if link.text.strip() == next_page_str:
                    link.click()
                    found_next_page = True
                    break

            if not found_next_page:
                print(f"{page}페이지 이후로 더 이상 페이지 링크를 찾지 못했습니다.")
                break

            time.sleep(3)  # 다음 페이지 로딩 대기

    finally:
        driver.quit()

    # --- 수집된 URL CSV 저장 ---
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["URL"])
        for url in all_urls:
            writer.writerow([url])

    print(f"\n총 {len(all_urls)}개의 상품 URL을 수집했고, {output_csv}에 저장했습니다.")


if __name__ == "__main__":
    start_url = "https://brand.naver.com/onnon/category/78a8c0589ce54c10a778e9b1140fadbf?cp=1"  # 예시 URL
    scrape_multiple_pages(
        page_url=start_url,
        max_page=10,
        output_csv="product_urls_pagination.csv"
    )
