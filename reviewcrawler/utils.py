# reviewcrawler/utils.py
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import ElementNotInteractableException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import hashlib

def setup_driver():
    """Chrome 웹드라이버 설정"""
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # 헤드리스 모드 활성화
    options.add_argument("window-size=1920x1080")  # 브라우저 크기
    options.add_argument("disable-gpu")
    options.add_argument("disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')  # 메모리 관련 오류 방지
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(3)
    return driver

def safe_click(driver, element, retry=3, use_js=False, scroll_first=True):
    """안전하게 요소를 클릭하는 함수"""
    for attempt in range(retry):
        try:
            if scroll_first:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.5)
            if use_js:
                driver.execute_script("arguments[0].click();", element)
            else:
                element.click()
            time.sleep(1)  # 클릭 후 잠시 대기
            return True
        except (ElementNotInteractableException, TimeoutException) as e:
            print(f"클릭 시도 {attempt+1}/{retry} 실패: {e}")
            if attempt == retry - 1:
                try:
                    driver.execute_script("arguments[0].click();", element)
                    return True
                except Exception as js_e:
                    print(f"JavaScript 클릭도 실패: {js_e}")
                    return False
            time.sleep(1)
        except Exception as e:
            print(f"기타 오류 발생: {e}")
            return False
    return False

def extract_product_info_from_html(soup):
    """
    HTML에서 상품 정보 테이블 데이터 추출
    """
    product_info = {}
    table_selectors = [
        'table.TH_yvPweZa',
        'table[class*="_yvPweZa"]',
        'div._1Hbih69XFT table',
        'div[class*="product_info"] table'
    ]
    for selector in table_selectors:
        tables = soup.select(selector)
        for table in tables:
            rows = table.select('tr')
            for row in rows:
                th_cells = row.select('th')
                td_cells = row.select('td')
                for i, th in enumerate(th_cells):
                    if i < len(td_cells):
                        label = th.get_text(strip=True)
                        value = td_cells[i].get_text(strip=True)
                        if label and value:
                            product_info[label] = value
    return product_info

def get_text_from_element(element):
    """
    BeautifulSoup 요소에서 텍스트 추출 (내부 b, button 태그 등을 고려)
    """
    b_tag = element.find('b')
    if b_tag:
        return b_tag.get_text(strip=True)
    button_tag = element.find('button')
    if button_tag:
        return button_tag.get_text(strip=True)
    return element.get_text(strip=True)

def parse_product_info_tables(html_source):
    """
    네이버 스마트스토어 상품 정보 테이블 파싱
    """
    from text_based_parser import parse_product_info_by_text
    product_info = parse_product_info_by_text(html_source)
    if not product_info:
        soup = BeautifulSoup(html_source, 'html.parser')
        product_info = {}
        product_info_divs = soup.select('div._1Hbih69XFT')
        if not product_info_divs:
            print("[WARN] 상품 정보 영역(_1Hbih69XFT)을 찾을 수 없습니다.")
            product_info_divs = soup.select('div[class*="product_info"], div[class*="productInfo"]')
        for div in product_info_divs:
            tables = div.select('table')
            for table in tables:
                print(f"[DEBUG] 테이블 클래스: {table.get('class', '')}")
                rows = table.select('tr')
                for row in rows:
                    th_cells = row.select('th')
                    td_cells = row.select('td')
                    for i, th in enumerate(th_cells):
                        if i < len(td_cells):
                            key = th.get_text(strip=True)
                            value = get_text_from_element(td_cells[i])
                            if not value or value.isspace():
                                div_container = td_cells[i].select_one('div')
                                if div_container:
                                    value = get_text_from_element(div_container)
                            if key and value:
                                print(f"[DEBUG] 추출: {key} -> {value}")
                                product_info[key] = value
                                if key == "상품번호" and not value and td_cells[i].find('b'):
                                    b_value = td_cells[i].find('b').get_text(strip=True)
                                    if b_value:
                                        product_info[key] = b_value
                                        print(f"[DEBUG] b 태그에서 상품번호 추출: {b_value}")
        if '영수증발급' in product_info and not 'A/S 안내' in product_info:
            as_rows = soup.select('th:contains("A/S"), th:contains("AS")')
            for as_row in as_rows:
                if as_row.parent:
                    td_cell = as_row.parent.select_one('td')
                    if td_cell:
                        as_value = get_text_from_element(td_cell)
                        if as_value:
                            product_info['A/S 안내'] = as_value
        all_tables = soup.select('table')
        print(f"[DEBUG] 페이지 내 총 테이블 수: {len(all_tables)}")
        for idx, table in enumerate(all_tables):
            print(f"[DEBUG] 테이블 {idx+1} 클래스: {table.get('class', '')}")
    print(f"[DEBUG] 수집된 총 상품 정보 항목 수: {len(product_info)}")
    return product_info

def generate_product_code(product_info):
    """
    상품 정보를 바탕으로 고유한 상품 코드를 생성합니다.
    (예: 상품 URL과 상품명을 결합하여 MD5 해시의 앞 8자리를 사용)
    """
    string_to_hash = product_info.get('상품URL', '') + product_info.get('상품명', '')
    product_code = hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()[:8]
    return product_code
