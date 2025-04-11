# reviewcrawler/product_info.py
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
import os

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from reviewcrawler.utils import safe_click, extract_product_info_from_html, parse_product_info_tables

def standardize_product_info(product_info):
    """
    상품 정보를 표준화하고 논리적인 순서로 정렬합니다.
    """
    # 모든 가능한 필드를 논리적 그룹별로 정의
    category_fields = ['1st_depth', '2nd_depth', '3rd_depth', '4th_depth']
    id_fields = ['PRODUCT_CODE', '상품번호', '상품명', '상품URL']
    
    # 인기도 및 평가 정보 추가
    popularity_fields = ['관심고객수', '전체리뷰수', '평점', '5점리뷰수', '리뷰요약태그']
    evaluation_fields = ['평가_사이즈', '평가_사이즈_비율', '평가_두께', '평가_두께_비율', '평가_핏', '평가_핏_비율']
    
    price_fields = ['상품가격', '할인전가격', '할인정보']
    manufacture_fields = ['제조사', '브랜드', '모델명', '원산지', '생산방식']
    detail_fields = ['주요소재', '종류', '상품상태', '제품설명']
    apparel_fields = ['착용계절', '디테일', '여밈방식', '핏', '소매기장', '칼라종류', '패턴', '총기장', '사용대상']
    service_fields = ['배송정보', '배송옵션', 'A/S 안내', '영수증발급', '이벤트', '사은품']
    
    # 모든 필드를 합쳐서 표준 필드 목록 생성
    all_standard_fields = (
        category_fields + id_fields + popularity_fields + evaluation_fields + price_fields + 
        manufacture_fields + detail_fields + apparel_fields + service_fields
    )
    
    # 표준화된 정보 초기화
    standardized_info = {field: "" for field in all_standard_fields if field != 'PRODUCT_CODE'}
    
    # 원본 정보에서 값 복사
    for field in standardized_info:
        if field in product_info:
            standardized_info[field] = product_info[field]
    
    # 필드 간 매핑 (동일한 의미를 가진 다른 필드명)
    if '제조국' in product_info and standardized_info['원산지'] == "":
        standardized_info['원산지'] = product_info['제조국']
    if '제조자(사)' in product_info and standardized_info['제조사'] == "":
        standardized_info['제조사'] = product_info['제조자(사)']
    if '제품소재' in product_info and standardized_info['주요소재'] == "":
        standardized_info['주요소재'] = product_info['제품소재']
    if 'A/S 책임자와 전화번호' in product_info and standardized_info['A/S 안내'] == "":
        standardized_info['A/S 안내'] = product_info['A/S 책임자와 전화번호']
    
    # PRODUCT_CODE가 원본에 있으면 추가
    if 'PRODUCT_CODE' in product_info:
        standardized_info['PRODUCT_CODE'] = product_info['PRODUCT_CODE']
    
    # 정의된 표준 필드 외의 추가 필드가 있으면 추가
    for field in product_info:
        if field not in standardized_info and field not in ['제조국', '제조자(사)', '제품소재', 'A/S 책임자와 전화번호']:
            standardized_info[field] = product_info[field]
    
    return standardized_info

def parse_summary_info(html_source):
    soup = BeautifulSoup(html_source, 'html.parser')
    summary_info = {}
    
    # 상품명 추출
    title_elem = soup.select_one("div._1eddO7u4UC h3._22kNQuEXmb")
    if title_elem:
        summary_info['상품명'] = title_elem.get_text(strip=True)
    
    # 관심고객수 추출
    interest_customer_elem = soup.select_one("span._2muLN5Fzlb")
    if interest_customer_elem:
        interest_text = interest_customer_elem.get_text(strip=True)
        if "관심고객수" in interest_text:
            import re
            interest_count = re.sub(r'[^0-9]', '', interest_text)
            summary_info['관심고객수'] = interest_count
            print(f"[DEBUG] 관심고객수 추출: {interest_count}")
    
    # 전체 리뷰 수 추출
    review_count_elem = soup.select_one("div._3GSqlAZeJb span.blind")
    if review_count_elem:
        review_text = review_count_elem.get_text().strip()
        # "1,814개" 형태에서 숫자만 추출
        import re
        review_count = re.sub(r'[^0-9]', '', review_text)
        if review_count:
            summary_info['전체리뷰수'] = review_count
            print(f"[DEBUG] 전체리뷰수 추출: {review_count}")
    
    # 평점 정보 추출
    rating_elem = soup.select_one("div._1T5uchuSaW")
    if rating_elem:
        rating_text = rating_elem.get_text().strip()
        # "최근 6개월 5.0" 형태에서 숫자만 추출
        import re
        rating_match = re.search(r'(\d+\.?\d*)', rating_text)
        if rating_match:
            rating = rating_match.group(1)
            summary_info['평점'] = rating
            print(f"[DEBUG] 평점 추출: {rating}")
    
    # 5점 비율 추출
    star5_elem = soup.select_one("li._2Vmt6-4BvP._3d-jESzl9J em._1JW7r9h1sP")
    if star5_elem:
        star5_text = star5_elem.get_text().strip()
        # "1,206명" 형태에서 숫자만 추출
        import re
        star5_count = re.sub(r'[^0-9]', '', star5_text)
        if star5_count:
            summary_info['5점리뷰수'] = star5_count
            print(f"[DEBUG] 5점리뷰수 추출: {star5_count}")
    
    # 사이즈, 두께, 핏 정보 추출
    evaluation_elems = soup.select("li.nm0BTjARAv")
    for elem in evaluation_elems:
        category_elem = elem.select_one("em._1ehAE1FZXP")
        value_elem = elem.select_one("span._3TuFT_dyR9")
        percent_elem = elem.select_one("span._1j8ap1C9-S")
        
        if category_elem and value_elem and percent_elem:
            category = category_elem.get_text().strip()
            value = value_elem.get_text().strip()
            percent = percent_elem.get_text().strip().replace('%', '')
            
            field_name = f'평가_{category}'
            summary_info[field_name] = value
            summary_info[f'{field_name}_비율'] = percent
            print(f"[DEBUG] {field_name} 추출: {value} ({percent}%)")
    
    # AI 리뷰요약 태그 추출
    review_tags = []
    tag_elems = soup.select("ul._3nvipoK9DW li._2NAGswzFgY button._33Rpy54LBS")
    for tag_elem in tag_elems:
        tag_text = tag_elem.get_text().strip()
        review_tags.append(tag_text)
    
    if review_tags:
        summary_info['리뷰요약태그'] = ', '.join(review_tags)
        print(f"[DEBUG] 리뷰요약태그 추출: {review_tags}")
    
    # 생산방식 추출
    custom_elem = soup.select_one("div._1eddO7u4UC em._1SHgFqYghw.gvkucAUfCS")
    if custom_elem:
        summary_info['생산방식'] = custom_elem.get_text(strip=True)
    
    # 배송옵션 추출
    nextday_elem = soup.select_one("div._1eddO7u4UC em._1SHgFqYghw._1NXyF7xfLC span.blind")
    if nextday_elem:
        summary_info['배송옵션'] = nextday_elem.get_text(strip=True)
    
    # 할인정보 추출
    discount_elem = soup.select_one("div.WrkQhIlUY0 span._1G-IvlyANt span.blind")
    if discount_elem:
        summary_info['할인정보'] = discount_elem.get_text(strip=True)
    
    # 할인전가격 추출
    original_price_elem = soup.select_one("div._3my-5FC8OB del.Xdhdpm0BD9 span._1LY7DqCnwR")
    if original_price_elem:
        summary_info['할인전가격'] = original_price_elem.get_text(strip=True)
    
    # 상품가격 추출
    discounted_price_elem = soup.select_one("div._3my-5FC8OB strong.aICRqgP9zw._2oBq11Xp7s span._1LY7DqCnwR")
    if discounted_price_elem:
        summary_info['상품가격'] = discounted_price_elem.get_text(strip=True)
    
    # 배송정보 추출
    shipping_elem = soup.select_one("div._3my-5FC8OB div._1bJwyyeSAa span._2LwlYHFpvU")
    if shipping_elem:
        summary_info['배송정보'] = shipping_elem.get_text(strip=True)
    
    return summary_info

def crawl_detailed_product_info(driver, product_info=None):
    if product_info is None:
        product_info = {}
    try:
        detail_tab_selectors = [
            'a[href="#INTRODUCE"]', 'a[href="#DETAIL"]', 'a:contains("상세정보")',
            'a:contains("상품정보")', '//a[contains(text(), "상세정보")]',
            '//a[contains(text(), "상품정보")]'
        ]
        detail_tab_clicked = False
        for selector in detail_tab_selectors:
            try:
                if selector.startswith('a['):
                    detail_tab = driver.find_element(By.CSS_SELECTOR, selector)
                    if safe_click(driver, detail_tab):
                        detail_tab_clicked = True
                        print("[INFO] 상세 정보 탭 클릭 완료.")
                        break
                elif selector.startswith('//'):
                    detail_tabs = driver.find_elements(By.XPATH, selector)
                    if detail_tabs and safe_click(driver, detail_tabs[0]):
                        detail_tab_clicked = True
                        print("[INFO] 상세 정보 탭 클릭 완료 (XPath).")
                        break
                elif ':contains' in selector:
                    text = selector.split('contains("')[1].split('")')[0]
                    tabs = driver.find_elements(By.XPATH, f"//a[contains(text(), '{text}')]")
                    for tab in tabs:
                        if safe_click(driver, tab):
                            detail_tab_clicked = True
                            print(f"[INFO] 상세 정보 탭 클릭 완료 (텍스트: {text}).")
                            break
                    if detail_tab_clicked:
                        break
            except NoSuchElementException:
                continue
            except Exception as e:
                print(f"[WARN] 상세 정보 탭 클릭 오류: {e}")
        if not detail_tab_clicked:
            print("[WARN] 상세 정보 탭을 찾거나 클릭하지 못함.")
        time.sleep(2)
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(1)
        driver.execute_script("window.scrollBy(0, 500);")
        time.sleep(1)
        
        html_source = driver.page_source
        summary_info = parse_summary_info(html_source)
        from reviewcrawler.text_based_parser import parse_product_info_by_text
        text_based_info = parse_product_info_by_text(html_source)
        for key, value in text_based_info.items():
            if key not in summary_info or not summary_info[key]:
                summary_info[key] = value
        table_info = parse_product_info_tables(html_source)
        for key, value in table_info.items():
            if key not in summary_info or not summary_info[key]:
                summary_info[key] = value
        soup = BeautifulSoup(html_source, 'html.parser')
        detail_containers = [
            '#INTRODUCE', '#DETAIL', 'div.detail_area', 'div[class*="detail_content"]',
            'div[class*="product_detail"]', 'div[class*="goods_detail"]'
        ]
        for container_selector in detail_containers:
            container = soup.select_one(container_selector)
            if container:
                text_blocks = container.select('div[class*="text"], p[class*="desc"], div[class*="description"]')
                if text_blocks:
                    combined_text = " ".join([block.get_text(strip=True) for block in text_blocks])
                    summary_info['제품설명'] = combined_text
                break
        combined_info = summary_info
        print("[DEBUG] 수집된 최종 상품 정보:")
        for k, v in combined_info.items():
            print(f"- {k}: {v}")
        return combined_info
    except Exception as e:
        print(f"[ERROR] 상세 상품 정보 수집 오류: {e}")
        import traceback
        traceback.print_exc()
        return product_info

def save_product_info_to_csv(product_info, output_csv):
    order_keys = ['상품명', '할인전가격', '할인정보', '배송옵션', '배송정보']
    other_keys = [key for key in product_info.keys() if key not in order_keys]
    columns_order = order_keys + other_keys
    df = pd.DataFrame([product_info])
    df = df[[col for col in columns_order if col in df.columns]]
    df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"[INFO] 최종 상품 정보가 {output_csv}에 저장됨.")
