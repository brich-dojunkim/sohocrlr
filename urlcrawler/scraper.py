# urlcrawler/scraper.py
import time
from bs4 import BeautifulSoup
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def scrape_product_urls(driver, limit=10):
    """
    페이지에서 최대 limit 개의 제품 URL을 추출합니다.
    스크롤을 반복하여 원하는 개수만큼 로드하도록 구현합니다.
    """
    product_urls = []
    scroll_count = 0
    max_scrolls = 10  # 최대 스크롤 횟수
    
    while len(product_urls) < limit and scroll_count < max_scrolls:
        time.sleep(2)  # 스크롤 후 로딩 대기
        soup = BeautifulSoup(driver.page_source, "html.parser")
        product_cards = soup.select("a[href^='https://shopping.naver.com/window-products/style/']")
        print(">> [DEBUG] 추출된 product_card 개수:", len(product_cards))
        
        for card in product_cards:
            href = card.get("href")
            if href and href.strip() not in product_urls:
                product_urls.append(href.strip())
                if len(product_urls) >= limit:
                    break
        
        if len(product_urls) >= limit:
            break
        
        # 페이지의 가장 밑으로 스크롤하여 추가 로딩을 유도합니다.
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        scroll_count += 1
        print(f">> [DEBUG] 스크롤 {scroll_count}회 진행 중. 현재 수집된 URL 개수: {len(product_urls)}")
    
    return product_urls

def apply_sort_filter(driver, safe_click, wait_func=None):
    """
    '리뷰 많은순' 버튼 클릭 후 '전체' 옵션을 선택합니다.
    """
    try:
        sort_filter = WebDriverWait(driver, 20).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "div.sortFilterWrapper_sort_filter_wrapper__Ny94X"))
        )
        print(">> [DEBUG] sort filter 컨테이너 로드됨")
    except Exception as e:
        print(">> [DEBUG] sort filter 컨테이너 로딩 실패:", e)
        return

    try:
        review_sort_btn = sort_filter.find_element(By.XPATH, ".//button[contains(., '리뷰 많은순')]")
        btn_text = review_sort_btn.text.strip()
        print(">> [DEBUG] 리뷰 많은순 버튼 찾음:", btn_text)
        if "sort_active" not in review_sort_btn.get_attribute("class"):
            safe_click(driver, review_sort_btn, "리뷰 많은순 버튼")
        else:
            print(">> [DEBUG] 리뷰 많은순 버튼 이미 활성화됨")
    except Exception as e:
        print(">> [DEBUG] 리뷰 많은순 버튼 찾기 실패:", e)
        return

    try:
        sort_detail_list = WebDriverWait(driver, 5).until(
            EC.visibility_of_element_located((By.CSS_SELECTOR, "ul.sort_option_detail_list__4oSrw"))
        )
        print(">> [DEBUG] sort detail 리스트 로드됨")
        sort_buttons = sort_detail_list.find_elements(By.CSS_SELECTOR, "button.sort_detail_button__CoQKb")
        target_sort = None
        for btn in sort_buttons:
            if btn.text.strip() == "전체":
                target_sort = btn
                break
        if target_sort:
            safe_click(driver, target_sort, "Sort Detail '전체'")
            print(">> [DEBUG] '전체' sort detail 옵션 클릭 성공")
        else:
            print(">> [DEBUG] '전체' sort detail 옵션을 찾지 못함")
    except Exception as e:
        print(">> [DEBUG] sort detail 리스트 처리 중 예외 발생:", e)
    
    time.sleep(2)
