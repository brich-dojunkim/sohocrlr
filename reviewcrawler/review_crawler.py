# reviewcrawler/review_crawler.py
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import os

# Selenium 관련
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, TimeoutException

# 유틸리티 함수 가져오기
from reviewcrawler.utils import safe_click, setup_driver

def crawl_product_reviews(target_url, driver=None, max_pages=None, output_csv=None, return_df=False, append_mode=False, product_code=None):
    """
    스마트스토어 상품의 리뷰 데이터 수집
    
    Args:
        target_url (str): 상품 페이지 URL
        driver (WebDriver, optional): 기존 WebDriver 인스턴스
        max_pages (int, optional): 수집할 최대 페이지 수
        output_csv (str, optional): 결과를 저장할 CSV 파일명
        return_df (bool, optional): 데이터프레임 반환 여부
        append_mode (bool, optional): 기존 CSV에 결과 추가 여부
        product_code (str, optional): 미리 생성된 상품 코드. 없으면 새로 생성.
        
    Returns:
        DataFrame: 리뷰 데이터프레임(옵션에 따라 반환)
    """
    if target_url.startswith('/'):
        target_url = 'https://brand.naver.com' + target_url
    
    close_driver_after = False
    if driver is None:
        driver = setup_driver()
        close_driver_after = True
    
    try:
        driver.get(target_url)
        time.sleep(3)

        html_source = driver.page_source
        soup = BeautifulSoup(html_source, 'html.parser')
        title_tag = soup.find('h3', {'class': '_22kNQuEXmb _copyable'})
        if title_tag:
            product_title = title_tag.get_text(strip=True)
        else:
            product_title = "Unknown Product"
        print(f"[INFO] 상품 제목: {product_title}")

        # 상품 코드 재생성 없이 전달된 값 사용 (없다면 생성)
        if not product_code:
            from utils import generate_product_code
            product_code = generate_product_code({'상품URL': target_url, '상품명': product_title})
        
        # 리뷰 탭 클릭 시도
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
                if selector.startswith('#') or selector.startswith('a['):
                    review_tab = driver.find_element(By.CSS_SELECTOR, selector)
                    if safe_click(driver, review_tab):
                        review_tab_clicked = True
                        print("[INFO] 리뷰 탭 클릭 완료.")
                        break
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
            print("[WARN] 리뷰 탭을 찾지 못하거나 클릭할 수 없습니다. 이미 리뷰 페이지일 가능성이 있음.")
            if "REVIEW" not in driver.page_source and "리뷰" not in driver.page_source:
                print("[ERROR] 리뷰 섹션을 찾을 수 없음.")
                return pd.DataFrame() if return_df else None
        
        time.sleep(3)

        # 최신순 버튼 클릭 시도
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
            print("[WARN] 최신순 버튼 클릭 실패. 기본 정렬로 진행.")
        time.sleep(3)

        # 리뷰 데이터 수집 리스트 초기화
        write_dt_lst = []
        rating_lst = []
        item_nm_lst = []
        content_lst = []
        option_size_lst = []
        option_color_lst = []
        reviewer_info_lst = []
        review_imgs_lst = []

        page_num = 1
        consecutive_empty_pages = 0
        max_consecutive_empty = 2
        previous_page_html = ""
        
        while True:
            print(f"[INFO] {page_num} 페이지 수집 중...")
            html_source = driver.page_source
            if html_source == previous_page_html:
                print("[INFO] 이전 페이지와 동일한 내용. 새 페이지 없으므로 종료.")
                break
            previous_page_html = html_source
            soup = BeautifulSoup(html_source, 'html.parser')
            time.sleep(0.5)

            review_selectors = [
                'li.BnwL_cs1av',
                'li[class*="review_"]',
                'div[class*="review_item"]',
                'div._1MMhUGHnc_',
                '.reviewItems_review_item'
            ]
            reviews = []
            for selector in review_selectors:
                reviews = soup.select(selector)
                if reviews:
                    print(f"[INFO] 리뷰 {len(reviews)}개 찾음. (선택자: {selector})")
                    break
            if not reviews:
                print("[INFO] 리뷰를 찾지 못함.")
                consecutive_empty_pages += 1
                if consecutive_empty_pages >= max_consecutive_empty:
                    print(f"[INFO] {max_consecutive_empty}페이지 연속 빈 결과로 종료.")
                    break
            else:
                consecutive_empty_pages = 0

            for r in reviews:
                write_dt = ""
                date_selectors = [
                    'span._2L3vDiadT9',
                    'span[class*="date"]',
                    'div[class*="date"]',
                    'span[class*="time"]',
                    'em[class*="date"]'
                ]
                for selector in date_selectors:
                    date_elements = r.select(selector)
                    if date_elements:
                        try:
                            date_text = date_elements[0].get_text().strip()
                            if re.match(r'\d{2}\.\d{2}\.\d{2}', date_text) or re.match(r'\d{2}\.\d{2}\.\d{2}\.', date_text):
                                date_text = date_text.rstrip('.')
                                write_dt = datetime.strptime(date_text, '%y.%m.%d').strftime('%Y%m%d')
                                break
                            elif re.match(r'\d{4}\.\d{2}\.\d{2}', date_text):
                                write_dt = date_text.replace('.', '')
                                break
                            elif re.match(r'\d{4}-\d{2}-\d{2}', date_text):
                                write_dt = date_text.replace('-', '')
                                break
                        except (ValueError, IndexError):
                            continue
                rating = ""
                rating_selectors = [
                    'em._15NU42F3kT',
                    'em[class*="rating"]',
                    'span[class*="rating"]',
                    'div[class*="star"] em',
                    'em[class*="score"]'
                ]
                for selector in rating_selectors:
                    rating_elements = r.select(selector)
                    if rating_elements:
                        rating = rating_elements[0].get_text().strip()
                        if rating:
                            break
                option_size = ""
                option_color = ""
                item_nm = ""
                option_selectors = [
                    'div._2FXNMst_ak',
                    'div[class*="option"]',
                    'div[class*="product_info"]',
                    'dl[class*="option"]',
                    'p[class*="option"]'
                ]
                for selector in option_selectors:
                    option_elements = r.select(selector)
                    if option_elements:
                        try:
                            item_div = option_elements[0]
                            item_nm_info_raw = item_div.get_text()
                            dl_tag = None
                            dl_selectors = ['dl.XbGQRlzveO', 'dl[class*="option"]', 'dl']
                            for dl_selector in dl_selectors:
                                dl_candidates = item_div.select(dl_selector)
                                if dl_candidates:
                                    dl_tag = dl_candidates[0]
                                    break
                            if dl_tag:
                                dt_tags = dl_tag.find_all('dt')
                                dd_tags = dl_tag.find_all('dd')
                                options_dict = {}
                                for i in range(min(len(dt_tags), len(dd_tags))):
                                    option_name = dt_tags[i].get_text().strip().replace(':', '')
                                    option_value = dd_tags[i].get_text().strip()
                                    options_dict[option_name] = option_value
                                for key in ['사이즈', 'size', 'SIZE', '크기']:
                                    if key in options_dict:
                                        option_size = options_dict[key]
                                        break
                                for key in ['색상', '컬러', 'color', 'COLOR']:
                                    if key in options_dict:
                                        option_color = options_dict[key]
                                        break
                                item_nm_info_for_del = dl_tag.get_text()
                            else:
                                item_nm_info_for_del = ""
                            item_nm_info = re.sub(item_nm_info_for_del, '', item_nm_info_raw)
                            str_start_idx = item_nm_info.find('제품 선택: ')
                            if str_start_idx != -1:
                                item_nm = item_nm_info[str_start_idx + 6:].strip()
                            else:
                                item_nm = item_nm_info.strip()
                            break
                        except (IndexError, AttributeError):
                            continue
                review_content = ""
                content_selectors = [
                    'div._1kMfD5ErZ6 span._2L3vDiadT9',
                    'div[class*="content"]',
                    'p[class*="content"]',
                    'span[class*="content"]'
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
                reviewer_info = ""
                reviewer_selectors = [
                    'div._1_XCKE2RrJ',
                    'div[class*="profile"]',
                    'span[class*="profile"]',
                    'div[class*="user_info"]'
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
                review_images = []
                image_selectors = [
                    'div._2389dRohZq img',
                    'div[class*="img"] img',
                    'a[class*="img"] img',
                    'ul[class*="img"] img'
                ]
                for selector in image_selectors:
                    image_elements = r.select(selector)
                    if image_elements:
                        for img in image_elements:
                            if 'src' in img.attrs:
                                review_images.append(img['src'])
                        if review_images:
                            break
                if review_content or rating:
                    write_dt_lst.append(write_dt)
                    rating_lst.append(rating)
                    item_nm_lst.append(item_nm)
                    content_lst.append(review_content)
                    option_size_lst.append(option_size)
                    option_color_lst.append(option_color)
                    reviewer_info_lst.append(reviewer_info)
                    review_imgs_lst.append("|".join(review_images) if review_images else "")
            
            if max_pages and page_num >= max_pages:
                print(f"[INFO] 최대 페이지 수({max_pages}) 도달. 종료.")
                break
            
            total_reviews_text = soup.select_one('span[class*="review_count"], span[class*="review_total"]')
            if total_reviews_text:
                try:
                    total_reviews_text = total_reviews_text.get_text().strip()
                    total_reviews = re.search(r'\d+', total_reviews_text)
                    if total_reviews:
                        total_reviews = int(total_reviews.group())
                        current_reviews = len(write_dt_lst)
                        print(f"[INFO] 총 리뷰 {total_reviews}개 중 {current_reviews}개 수집 (진행률: {current_reviews/total_reviews*100:.1f}%)")
                        if current_reviews >= total_reviews:
                            print("[INFO] 모든 리뷰 수집 완료. 종료.")
                            break
                except Exception as e:
                    print(f"[WARN] 리뷰 개수 확인 오류: {e}")
            
            next_page_found = False
            try:
                next_page_number = page_num + 1
                next_page_xpath = f"//a[contains(text(), '{next_page_number}')]"
                next_page_elements = driver.find_elements(By.XPATH, next_page_xpath)
                for element in next_page_elements:
                    if element.text.strip() == str(next_page_number):
                        if safe_click(driver, element, use_js=True):
                            next_page_found = True
                            break
            except Exception as e:
                print(f"[WARN] 숫자 페이지네이션 오류: {e}")
            
            if not next_page_found:
                try:
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
                                if btn.is_displayed() and btn.is_enabled():
                                    if safe_click(driver, btn, use_js=True):
                                        next_page_found = True
                                        break
                        if next_page_found:
                            break
                except Exception as e:
                    print(f"[WARN] 다음 페이지 버튼 오류: {e}")
            
            if not next_page_found:
                try:
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
                            pagination_area = pagination_elements[0]
                            page_links = pagination_area.find_elements(By.TAG_NAME, 'a')
                            for i, link in enumerate(page_links):
                                if link.text.strip() == str(page_num):
                                    if i + 1 < len(page_links):
                                        next_link = page_links[i + 1]
                                        if safe_click(driver, next_link, use_js=True):
                                            next_page_found = True
                                            break
                        if next_page_found:
                            break
                except Exception as e:
                    print(f"[WARN] 페이지네이션 영역 오류: {e}")
            
            if not next_page_found:
                print("[INFO] 더 이상 다음 페이지 없음. 종료.")
                break
            
            time.sleep(3)
            page_num += 1

        print(f"[{product_title}] 크롤링 완료!")

        result_df = pd.DataFrame({
            'PRODUCT_CODE': [product_code] * len(write_dt_lst),
            'PRODUCT_TITLE': [product_title] * len(write_dt_lst),
            'RD_WRITE_DT': write_dt_lst,
            'RD_RATING': rating_lst,
            'RD_ITEM_NM': item_nm_lst,
            'RD_CONTENT': content_lst,
            'RD_OPTION_SIZE': option_size_lst,
            'RD_OPTION_COLOR': option_color_lst,
            'RD_REVIEWER_INFO': reviewer_info_lst,
            'RD_REVIEW_IMAGES': review_imgs_lst
        })

        if len(result_df) == 0:
            print(f"[WARN] {product_title}에서 수집된 리뷰가 없음.")
            return pd.DataFrame() if return_df else None

        if len(result_df) > 0:
            result_df = result_df.drop_duplicates(subset=['RD_WRITE_DT', 'RD_CONTENT'], keep='first')
            print(f"[INFO] 중복 제거 후 {len(result_df)}개의 리뷰 남음.")

        if output_csv:
            if append_mode and os.path.exists(output_csv):
                result_df.to_csv(output_csv, mode='a', index=False, header=False, encoding='utf-8-sig')
                print(f"기존 파일 {output_csv}에 {len(result_df)}건 리뷰 추가됨.")
            else:
                result_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
                print(f"CSV 저장 완료! {output_csv}에 {len(result_df)}건 리뷰 저장됨.")

        if return_df:
            return result_df
    
    finally:
        if close_driver_after and driver:
            driver.quit()
    return None
