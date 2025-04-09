# reviewcrawler/product_info.py
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
import os

from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

from utils import safe_click, extract_product_info_from_html, parse_product_info_tables

def standardize_product_info(product_info):
    standard_fields = [
        '상품번호', '상품상태', '제조사', '브랜드', '모델명', '이벤트',
        '사은품', '원산지', '착용계절', '디테일', '사용대상', '여밈방식',
        '핏', '종류', '주요소재', '소매기장', '칼라종류', '패턴', '총기장',
        '영수증발급', 'A/S 안내', '생산방식', '배송옵션', '할인정보',
        '할인전가격', '상품가격', '배송정보', '제품설명', '상품URL', '상품명'
    ]
    standardized_info = {field: "" for field in standard_fields}
    for field in standard_fields:
        if field in product_info:
            standardized_info[field] = product_info[field]
    if '제조국' in product_info and standardized_info['원산지'] == "":
        standardized_info['원산지'] = product_info['제조국']
    if '제조자(사)' in product_info and standardized_info['제조사'] == "":
        standardized_info['제조사'] = product_info['제조자(사)']
    if '제품소재' in product_info and standardized_info['주요소재'] == "":
        standardized_info['주요소재'] = product_info['제품소재']
    if 'A/S 책임자와 전화번호' in product_info and standardized_info['A/S 안내'] == "":
        standardized_info['A/S 안내'] = product_info['A/S 책임자와 전화번호']
    return standardized_info

def parse_summary_info(html_source):
    soup = BeautifulSoup(html_source, 'html.parser')
    summary_info = {}
    title_elem = soup.select_one("div._1eddO7u4UC h3._22kNQuEXmb")
    if title_elem:
        summary_info['상품명'] = title_elem.get_text(strip=True)
    custom_elem = soup.select_one("div._1eddO7u4UC em._1SHgFqYghw.gvkucAUfCS")
    if custom_elem:
        summary_info['생산방식'] = custom_elem.get_text(strip=True)
    nextday_elem = soup.select_one("div._1eddO7u4UC em._1SHgFqYghw._1NXyF7xfLC span.blind")
    if nextday_elem:
        summary_info['배송옵션'] = nextday_elem.get_text(strip=True)
    discount_elem = soup.select_one("div.WrkQhIlUY0 span._1G-IvlyANt span.blind")
    if discount_elem:
        summary_info['할인정보'] = discount_elem.get_text(strip=True)
    original_price_elem = soup.select_one("div._3my-5FC8OB del.Xdhdpm0BD9 span._1LY7DqCnwR")
    if original_price_elem:
        summary_info['할인전가격'] = original_price_elem.get_text(strip=True)
    discounted_price_elem = soup.select_one("div._3my-5FC8OB strong.aICRqgP9zw._2oBq11Xp7s span._1LY7DqCnwR")
    if discounted_price_elem:
        summary_info['상품가격'] = discounted_price_elem.get_text(strip=True)
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
        from text_based_parser import parse_product_info_by_text
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
