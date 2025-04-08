import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os

# Selenium 관련
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# webdriver-manager로 크롬드라이버 버전 자동 관리
from webdriver_manager.chrome import ChromeDriverManager

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
                # 먼저 요소로 스크롤
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
                time.sleep(0.5)
            
            if use_js:
                # JavaScript를 사용한 클릭
                driver.execute_script("arguments[0].click();", element)
            else:
                # 일반 클릭
                element.click()
            
            time.sleep(1)  # 클릭 후 잠시 대기
            return True
        except (ElementNotInteractableException, TimeoutException) as e:
            print(f"클릭 시도 {attempt+1}/{retry} 실패: {e}")
            if attempt == retry - 1:
                # 마지막 시도에서 JavaScript로 클릭 시도
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

def crawl_reviews(target_url, max_pages=None, output_csv=None, return_df=False, append_mode=False):
    """
    스마트스토어 상품의 리뷰 데이터 수집
    
    Args:
        target_url (str): 상품 페이지 URL
        max_pages (int, optional): 수집할 최대 페이지 수 (기본값: 모든 페이지)
        output_csv (str, optional): 결과를 저장할 CSV 파일명
        return_df (bool, optional): 데이터프레임을 반환할지 여부
        append_mode (bool, optional): 기존 CSV 파일에 결과를 추가할지 여부
        
    Returns:
        DataFrame: return_df가 True일 경우 수집된 리뷰 데이터프레임 반환
    """

    if target_url.startswith('/'):
        target_url = 'https://brand.naver.com' + target_url
    
    driver = setup_driver()
    
    # -----------------------------------------------------------
    # 1. 크롤링에 필요한 사전 작업 (사이트 열기 & 버튼 클릭)
    # -----------------------------------------------------------
    try:
        # (1-1) 원하는 상품 페이지 열기
        driver.get(target_url)
        time.sleep(3)

        # (1-2) 상품 제목 가져오기
        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        title_tag = soup.find('h3', {'class': '_22kNQuEXmb _copyable'})
        if title_tag:
            product_title = title_tag.get_text(strip=True)
        else:
            product_title = "Unknown Product"
        print(f"[INFO] 상품 제목: {product_title}")

        # (1-3) "리뷰" 탭 버튼 클릭 - 여러 선택자 시도
        review_tab_selectors = [
            '#content > div > div.z7cS6-TO7X > div._27jmWaPaKy > ul > li:nth-child(2) > a',
            '#content > div > div._2-I30XS1lA > div._25tOXGEYJK > ul > li:nth-child(2) > a',
            'a[href="#REVIEW"]',
            'a[aria-selected="true"]',
            'li a:contains("리뷰")'
        ]
        
        review_tab_clicked = False
        for selector in review_tab_selectors:
            try:
                # CSS 선택자 사용
                if selector.startswith('#') or selector.startswith('a['):
                    review_tab = driver.find_element(By.CSS_SELECTOR, selector)
                    if safe_click(driver, review_tab):
                        review_tab_clicked = True
                        print("[INFO] 리뷰 탭 클릭 완료.")
                        break
                # XPath로 리뷰 텍스트 포함 요소 찾기
                elif 'contains' in selector:
                    review_elements = driver.find_elements(By.XPATH, "//a[contains(text(), '리뷰')]")
                    if review_elements:
                        if safe_click(driver, review_elements[0]):
                            review_tab_clicked = True
                            print("[INFO] 리뷰 탭 클릭 완료 (텍스트 검색).")
                            break
            except NoSuchElementException:
                continue
        
        if not review_tab_clicked:
            print("[WARN] 리뷰 탭을 찾을 수 없거나 클릭할 수 없습니다. 이미 리뷰 페이지일 수 있습니다.")
            # 리뷰 섹션이 이미 표시되어 있는지 확인
            if "REVIEW" not in driver.page_source and "리뷰" not in driver.page_source:
                print("[ERROR] 리뷰 섹션을 찾을 수 없습니다.")
                return pd.DataFrame() if return_df else None
        
        time.sleep(3)

        # (1-4) "최신순" 버튼 클릭 - 여러 선택자 시도
        latest_selectors = [
            '#REVIEW > div > div._2LvIMaBiIO > div._2LAwVxx1Sd > div._1txuie7UTH > ul > li:nth-child(2) > a',
            'a.filter_sort:contains("최신순")',
            '//a[contains(text(), "최신순")]',
            'a[aria-selected="false"]'
        ]
        
        latest_clicked = False
        for selector in latest_selectors:
            try:
                if selector.startswith('#'):
                    latest_btn = driver.find_element(By.CSS_SELECTOR, selector)
                    if safe_click(driver, latest_btn, use_js=True):
                        latest_clicked = True
                        print("[INFO] 최신순 버튼 클릭 완료.")
                        break
                elif selector.startswith('//'):
                    latest_btns = driver.find_elements(By.XPATH, selector)
                    if latest_btns and safe_click(driver, latest_btns[0], use_js=True):
                        latest_clicked = True
                        print("[INFO] 최신순 버튼 클릭 완료 (XPath).")
                        break
                elif 'contains' in selector:
                    latest_btns = driver.find_elements(By.XPATH, "//a[contains(text(), '최신순')]")
                    if latest_btns and safe_click(driver, latest_btns[0], use_js=True):
                        latest_clicked = True
                        print("[INFO] 최신순 버튼 클릭 완료 (텍스트 검색).")
                        break
                elif selector.startswith('a[aria'):
                    filter_btns = driver.find_elements(By.CSS_SELECTOR, selector)
                    for btn in filter_btns:
                        if '최신' in btn.text:
                            if safe_click(driver, btn, use_js=True):
                                latest_clicked = True
                                print("[INFO] 최신순 버튼 클릭 완료 (aria 속성).")
                                break
            except NoSuchElementException:
                continue
            except Exception as e:
                print(f"[WARN] 최신순 버튼 클릭 시도 중 오류: {e}")
        
        if not latest_clicked:
            print("[WARN] 최신순 버튼 클릭 실패. 기본 정렬 순서로 진행합니다.")
            
        time.sleep(3)

        # -----------------------------------------------------------
        # 2. 리뷰데이터 수집을 위한 리스트 초기화
        # -----------------------------------------------------------
        write_dt_lst = []
        rating_lst = []
        item_nm_lst = []
        content_lst = []
        option_size_lst = []  # 사이즈 정보
        option_color_lst = []  # 컬러 정보
        reviewer_info_lst = []  # 리뷰어 정보
        review_imgs_lst = []  # 리뷰 이미지 URL

        # -----------------------------------------------------------
        # 3. 여러 페이지 리뷰를 반복적으로 수집하기
        # -----------------------------------------------------------
        page_num = 1
        consecutive_empty_pages = 0  # 연속으로 리뷰가 없는 페이지 수
        max_consecutive_empty = 2    # 최대 허용 연속 빈 페이지 (2페이지 연속으로 리뷰가 없으면 종료)
        
        # 페이지 HTML 저장하여 중복 검사에 사용
        previous_page_html = ""
        
        while True:
            print(f"[INFO] {page_num} 페이지 수집 중...")

            # 3-1. 현재 페이지 HTML 파싱
            html_source = driver.page_source
            
            # 페이지 중복 검사 (이전 페이지와 현재 페이지가 동일하면 페이지네이션 실패로 간주)
            if html_source == previous_page_html:
                print("[INFO] 이전 페이지와 동일한 내용입니다. 더 이상 새로운 페이지가 없는 것으로 판단됩니다.")
                break
            
            previous_page_html = html_source
            soup = BeautifulSoup(html_source, 'html.parser')
            time.sleep(0.5)

            # 3-2. 현재 페이지에 표시된 모든 리뷰 블록 찾기 (여러 클래스명 시도)
            review_selectors = [
                'li.BnwL_cs1av',  # 기존 선택자
                'li[class*="review_"]',  # 부분 클래스명 매칭
                'div[class*="review_item"]',  # 리뷰 아이템 클래스
                'div._1MMhUGHnc_',  # 실제 네이버 쇼핑몰 리뷰 컨테이너
                '.reviewItems_review_item'  # 새로운 클래스 스타일
            ]
            
            reviews = []
            for selector in review_selectors:
                reviews = soup.select(selector)
                if reviews:
                    print(f"[INFO] 리뷰 {len(reviews)}개를 찾았습니다. (선택자: {selector})")
                    break
            
            if not reviews:
                print("[INFO] 이 페이지에서 리뷰를 찾을 수 없습니다.")
                consecutive_empty_pages += 1
                
                # 리뷰를 찾을 수 없는 페이지가 연속으로 나오면 종료
                if consecutive_empty_pages >= max_consecutive_empty:
                    print(f"[INFO] {max_consecutive_empty}페이지 연속으로 리뷰를 찾을 수 없어 크롤링을 종료합니다.")
                    break
                
                # 그렇지 않으면 다음 페이지 시도
            else:
                # 리뷰를 찾았으면 연속 빈 페이지 카운터 초기화
                consecutive_empty_pages = 0

            # 3-3. 리뷰마다 날짜, 평점, 상품명, 리뷰내용을 수집
            for r in reviews:
                # (a) 리뷰 작성 일자 - 여러 클래스명 시도
                write_dt = ""
                date_selectors = [
                    'span._2L3vDiadT9',  # 기존 선택자
                    'span[class*="date"]',  # 날짜 관련 클래스
                    'div[class*="date"]',  # 날짜 div
                    'span[class*="time"]',  # 시간 관련 클래스
                    'em[class*="date"]'  # em 태그 내 날짜
                ]
                
                for selector in date_selectors:
                    date_elements = r.select(selector)
                    if date_elements:
                        try:
                            date_text = date_elements[0].get_text().strip()
                            # 여러 날짜 형식 처리
                            if re.match(r'\d{2}\.\d{2}\.\d{2}', date_text) or re.match(r'\d{2}\.\d{2}\.\d{2}\.', date_text):
                                # 'yy.mm.dd.' or 'yy.mm.dd' → 'YYYYMMDD'
                                date_text = date_text.rstrip('.')
                                write_dt = datetime.strptime(date_text, '%y.%m.%d').strftime('%Y%m%d')
                                break
                            elif re.match(r'\d{4}\.\d{2}\.\d{2}', date_text):
                                # 'YYYY.MM.DD' → 'YYYYMMDD'
                                write_dt = date_text.replace('.', '')
                                break
                            elif re.match(r'\d{4}-\d{2}-\d{2}', date_text):
                                # 'YYYY-MM-DD' → 'YYYYMMDD'
                                write_dt = date_text.replace('-', '')
                                break
                        except (ValueError, IndexError):
                            continue

                # (b) 평점 - 여러 클래스명 시도
                rating = ""
                rating_selectors = [
                    'em._15NU42F3kT',  # 기존 선택자
                    'em[class*="rating"]',  # 평점 관련 클래스
                    'span[class*="rating"]',  # 평점 span
                    'div[class*="star"] em',  # 별점 관련 div 내 em
                    'em[class*="score"]'  # 점수 관련 em
                ]
                
                for selector in rating_selectors:
                    rating_elements = r.select(selector)
                    if rating_elements:
                        rating = rating_elements[0].get_text().strip()
                        if rating:
                            break

                # (c) 상품명(옵션명) 및 옵션 정보(사이즈, 컬러 등)
                option_size = ""
                option_color = ""
                item_nm = ""

                option_selectors = [
                    'div._2FXNMst_ak',  # 기존 선택자
                    'div[class*="option"]',  # 옵션 관련 div
                    'div[class*="product_info"]',  # 상품 정보 div
                    'dl[class*="option"]',  # 옵션 설명 리스트
                    'p[class*="option"]'  # 옵션 관련 p 태그
                ]
                
                for selector in option_selectors:
                    option_elements = r.select(selector)
                    if option_elements:
                        try:
                            item_div = option_elements[0]
                            item_nm_info_raw = item_div.get_text()

                            # 옵션 정보가 담긴 dl 태그 찾기
                            dl_tag = None
                            dl_selectors = ['dl.XbGQRlzveO', 'dl[class*="option"]', 'dl']
                            for dl_selector in dl_selectors:
                                dl_candidates = item_div.select(dl_selector)
                                if dl_candidates:
                                    dl_tag = dl_candidates[0]
                                    break
                            
                            # 옵션 정보 상세 파싱 (dl 태그가 있는 경우)
                            if dl_tag:
                                # 모든 dt, dd 쌍을 찾아서 옵션 정보 추출
                                dt_tags = dl_tag.find_all('dt')
                                dd_tags = dl_tag.find_all('dd')
                                
                                # 옵션 정보 딕셔너리 생성
                                options_dict = {}
                                for i in range(min(len(dt_tags), len(dd_tags))):
                                    option_name = dt_tags[i].get_text().strip().replace(':', '')
                                    option_value = dd_tags[i].get_text().strip()
                                    options_dict[option_name] = option_value
                                    
                                # 사이즈 정보 찾기 (다양한 표현 방식 고려)
                                for key in ['사이즈', 'size', 'SIZE', '크기']:
                                    if key in options_dict:
                                        option_size = options_dict[key]
                                        break
                                        
                                # 컬러 정보 찾기 (다양한 표현 방식 고려)
                                for key in ['색상', '컬러', 'color', 'COLOR']:
                                    if key in options_dict:
                                        option_color = options_dict[key]
                                        break
                                        
                                item_nm_info_for_del = dl_tag.get_text()
                            else:
                                item_nm_info_for_del = ""

                            # 옵션 태그를 제외한 제품 정보 추출
                            item_nm_info = re.sub(item_nm_info_for_del, '', item_nm_info_raw)
                            
                            # "제품 선택:" 텍스트 이후의 내용 추출
                            str_start_idx = item_nm_info.find('제품 선택: ')
                            if str_start_idx != -1:
                                item_nm = item_nm_info[str_start_idx + 6:].strip()
                            else:
                                # "제품 선택:" 문구가 없을 경우 다른 방법으로 추출 시도
                                item_nm = item_nm_info.strip()
                            
                            break
                        except (IndexError, AttributeError):
                            continue

                # (d) 리뷰 내용 - 여러 클래스명 시도
                review_content = ""
                content_selectors = [
                    'div._1kMfD5ErZ6 span._2L3vDiadT9',  # 기존 선택자
                    'div[class*="content"]',  # 컨텐츠 관련 div
                    'p[class*="content"]',  # 컨텐츠 관련 p 태그
                    'span[class*="content"]'  # 컨텐츠 관련 span
                ]
                
                for selector in content_selectors:
                    content_elements = r.select(selector)
                    if content_elements:
                        try:
                            content_raw = content_elements[0].get_text()
                            review_content = re.sub(' +', ' ', re.sub('\n', ' ', content_raw)).strip()
                            if review_content:
                                break
                        except (AttributeError, IndexError):
                            continue

                # (e) 리뷰어 정보 수집 (구매자 정보, 신체 정보 등)
                reviewer_info = ""
                reviewer_selectors = [
                    'div._1_XCKE2RrJ',  # 기존 선택자
                    'div[class*="profile"]',  # 프로필 관련 div
                    'span[class*="profile"]',  # 프로필 관련 span
                    'div[class*="user_info"]'  # 사용자 정보 div
                ]
                
                for selector in reviewer_selectors:
                    reviewer_elements = r.select(selector)
                    if reviewer_elements:
                        try:
                            reviewer_info = reviewer_elements[0].get_text().strip()
                            if reviewer_info:
                                break
                        except (AttributeError, IndexError):
                            continue
                
                # (f) 리뷰 이미지 URL 수집
                review_images = []
                image_selectors = [
                    'div._2389dRohZq img',  # 기존 선택자
                    'div[class*="img"] img',  # 이미지 관련 div 내 img
                    'a[class*="img"] img',  # 이미지 관련 a 태그 내 img
                    'ul[class*="img"] img'  # 이미지 목록 내 img
                ]
                
                for selector in image_selectors:
                    image_elements = r.select(selector)
                    if image_elements:
                        for img in image_elements:
                            if 'src' in img.attrs:
                                review_images.append(img['src'])
                        if review_images:
                            break
                
                # 수집된 정보가 충분한지 확인 (최소한 리뷰 내용이나 별점은 있어야 함)
                if review_content or rating:
                    # 데이터 리스트에 저장
                    write_dt_lst.append(write_dt)
                    rating_lst.append(rating)
                    item_nm_lst.append(item_nm)
                    content_lst.append(review_content)
                    option_size_lst.append(option_size)
                    option_color_lst.append(option_color)
                    reviewer_info_lst.append(reviewer_info)
                    review_imgs_lst.append("|".join(review_images) if review_images else "")

            # 3-4. 최대 페이지 수에 도달했는지 확인
            if max_pages and page_num >= max_pages:
                print(f"[INFO] 최대 페이지 수({max_pages})에 도달했습니다. 크롤링을 종료합니다.")
                break

            # 3-5. 리뷰 계수기를 통해 종료 여부 확인
            # 상품 총 리뷰 개수 및 현재까지 수집한 개수 표시
            total_reviews_text = soup.select_one('span[class*="review_count"], span[class*="review_total"]')
            if total_reviews_text:
                try:
                    total_reviews_text = total_reviews_text.get_text().strip()
                    total_reviews = re.search(r'\d+', total_reviews_text)
                    if total_reviews:
                        total_reviews = int(total_reviews.group())
                        current_reviews = len(write_dt_lst)
                        print(f"[INFO] 총 리뷰 {total_reviews}개 중 {current_reviews}개 수집 완료 (진행률: {current_reviews/total_reviews*100:.1f}%)")
                        
                        # 모든 리뷰를 수집한 경우 종료
                        if current_reviews >= total_reviews:
                            print("[INFO] 모든 리뷰 수집 완료! 크롤링을 종료합니다.")
                            break
                except Exception as e:
                    print(f"[WARN] 리뷰 개수 확인 중 오류: {e}")

            # 3-6. 다음 페이지로 이동 (여러 페이지네이션 선택자 시도)
            next_page_found = False
            
            # 페이지네이션 스타일 1: 숫자 버튼
            if not next_page_found:
                try:
                    # 다음 페이지 번호 계산
                    next_page_number = page_num + 1
                    
                    # 해당 숫자를 가진 페이지 버튼 찾기 (XPath 사용)
                    next_page_xpath = f"//a[contains(text(), '{next_page_number}')]"
                    next_page_elements = driver.find_elements(By.XPATH, next_page_xpath)
                    
                    # 숫자만 있는 버튼 찾기
                    for element in next_page_elements:
                        if element.text.strip() == str(next_page_number):
                            if safe_click(driver, element, use_js=True):
                                next_page_found = True
                                break
                except Exception as e:
                    print(f"[WARN] 숫자 페이지네이션 시도 중 오류: {e}")
            
            # 페이지네이션 스타일 2: 다음 페이지 버튼
            if not next_page_found:
                try:
                    # "다음" 또는 ">" 텍스트가 있는 버튼 찾기
                    next_button_xpaths = [
                        "//a[contains(text(), '다음')]",
                        "//a[contains(text(), '>')]",
                        "//button[contains(text(), '다음')]",
                        "//button[contains(text(), '>')]",
                        "//a[contains(@class, 'next')]",
                        "//button[contains(@class, 'next')]"
                    ]
                    
                    for xpath in next_button_xpaths:
                        next_buttons = driver.find_elements(By.XPATH, xpath)
                        if next_buttons:
                            for btn in next_buttons:
                                # 버튼이 활성화되어 있고 화면에 표시되는지 확인
                                if btn.is_displayed() and btn.is_enabled():
                                    if safe_click(driver, btn, use_js=True):
                                        next_page_found = True
                                        break
                        if next_page_found:
                            break
                except Exception as e:
                    print(f"[WARN] 다음 페이지 버튼 시도 중 오류: {e}")
            
            # 페이지네이션 스타일 3: 전체 페이지네이션 영역에서 다음 페이지 찾기
            if not next_page_found:
                try:
                    # 페이지네이션 영역 선택자들
                    pagination_selectors = [
                        'div._2g7PKvqCKe', 
                        'div[class*="pagination"]',
                        'div[class*="paging"]',
                        'div[class*="page_num"]',
                        'ul[class*="pagination"]'
                    ]
                    
                    for selector in pagination_selectors:
                        pagination_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if pagination_elements:
                            # 페이지네이션 영역에서 모든 a 태그 찾기
                            pagination_area = pagination_elements[0]
                            page_links = pagination_area.find_elements(By.TAG_NAME, 'a')
                            
                            # 현재 페이지 다음 링크 찾기
                            for i, link in enumerate(page_links):
                                if link.text.strip() == str(page_num):
                                    # 현재 페이지 다음 링크가 있으면 클릭
                                    if i + 1 < len(page_links):
                                        next_link = page_links[i + 1]
                                        if safe_click(driver, next_link, use_js=True):
                                            next_page_found = True
                                            break
                        if next_page_found:
                            break
                except Exception as e:
                    print(f"[WARN] 페이지네이션 영역 시도 중 오류: {e}")
            
            if not next_page_found:
                print("[INFO] 더 이상 다음 페이지를 찾을 수 없습니다. 크롤링을 종료합니다.")
                break
            
            # 페이지 로딩 기다리기
            time.sleep(3)
            page_num += 1

        print(f"[{product_title}] 크롤링 완료!")

        # -----------------------------------------------------------
        # 4. 데이터프레임으로 정리 후 CSV 파일로 저장
        # -----------------------------------------------------------
        result_df = pd.DataFrame({
            'RD_WRITE_DT': write_dt_lst,
            'RD_RATING': rating_lst,
            'RD_ITEM_NM': item_nm_lst,
            'RD_CONTENT': content_lst,
            'RD_OPTION_SIZE': option_size_lst,
            'RD_OPTION_COLOR': option_color_lst,
            'RD_REVIEWER_INFO': reviewer_info_lst,
            'RD_REVIEW_IMAGES': review_imgs_lst,
            'PRODUCT_TITLE': [product_title] * len(write_dt_lst)
        })

        # 결과가 없을 경우 빈 데이터프레임 반환
        if len(result_df) == 0:
            print(f"[WARN] {product_title}에서 수집된 리뷰가 없습니다.")
            return pd.DataFrame() if return_df else None

        # 중복 제거 (동일한 내용과 날짜를 가진 리뷰)
        if len(result_df) > 0:
            result_df = result_df.drop_duplicates(subset=['RD_WRITE_DT', 'RD_CONTENT'], keep='first')
            print(f"[INFO] 중복 제거 후 {len(result_df)}개의 리뷰가 남았습니다.")

        # CSV 저장 (옵션)
        if output_csv:
            # 추가 모드인 경우 기존 파일이 있는지 확인
            if append_mode and os.path.exists(output_csv):
                # 헤더 없이 추가
                result_df.to_csv(output_csv, mode='a', index=False, header=False, encoding='utf-8-sig')
                print(f"기존 파일 {output_csv}에 {len(result_df)}건의 리뷰가 추가되었습니다.")
            else:
                # 새 파일 생성
                result_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
                print(f"CSV 저장 완료! {output_csv}에 {len(result_df)}건의 리뷰가 저장되었습니다.")

        if return_df:
            return result_df
    
    finally:
        driver.quit()
        
    return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='네이버 스마트스토어 상품 리뷰 크롤러')
    parser.add_argument('--url', type=str, help='크롤링할 상품 URL')
    parser.add_argument('--pages', type=int, default=None, help='수집할 최대 페이지 수 (기본값: 모든 페이지)')
    parser.add_argument('--output', type=str, default='navershopping_review_data.csv', help='결과를 저장할 CSV 파일명')

    args = parser.parse_args()
    
    # URL이 제공되지 않은 경우 기본 URL 사용
    if not args.url:
        target_url = 'https://brand.naver.com/onnon/products/8045986719'
        print(f"[INFO] URL이 제공되지 않아 기본 URL을 사용합니다: {target_url}")
    else:
        target_url = args.url
    
    print("="*50)
    print("네이버 스마트스토어 상품 리뷰 크롤러")
    print("="*50)
    print(f"대상 URL: {target_url}")
    print(f"최대 페이지 수: {args.pages if args.pages else '제한 없음'}")
    print(f"출력 파일: {args.output}")
    print("="*50)
    
    start_time = time.time()
    
    # 리뷰 수집 실행
    result_df = crawl_reviews(
        target_url=target_url,
        max_pages=args.pages,
        output_csv=args.output,
        return_df=True
    )
    
    # 결과 요약
    elapsed_time = time.time() - start_time
    
    print("\n" + "="*50)
    print("크롤링 완료 요약")
    print("="*50)
    
    if result_df is not None and not result_df.empty:
        print(f"- 수집된 리뷰 수: {len(result_df)}개")
        print(f"- 평균 별점: {result_df['RD_RATING'].astype(float).mean():.1f}/5.0")
        print(f"- 결과 저장 위치: {args.output}")
    else:
        print("- 수집된 리뷰가 없습니다.")
        
    print(f"- 소요 시간: {elapsed_time:.2f}초")
    print("="*50)