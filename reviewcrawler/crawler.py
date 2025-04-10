# reviewcrawler/crawler.py
import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import os

# Selenium 관련
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, TimeoutException

# webdriver-manager로 크롬드라이버 버전 자동 관리
from webdriver_manager.chrome import ChromeDriverManager

# 유틸리티 함수 가져오기
from reviewcrawler.utils import safe_click, extract_product_info_from_html, parse_product_info_tables, generate_product_code

class NaverShoppingCrawler:
    """네이버 쇼핑몰 크롤러 클래스"""
    
    def __init__(self):
        """초기화"""
        self.driver = None
        self.product_code = None  # 상품 코드 저장 변수 추가
        
    def setup_driver(self):
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
        self.driver = driver
        return driver
    
    def close(self):
        """드라이버 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def crawl_product_info(self, target_url, output_csv=None, external_product_code=None):
        """
        상품 정보 크롤링 함수
        
        Args:
            target_url (str): 상품 페이지 URL
            output_csv (str, optional): 결과를 저장할 CSV 파일명
            external_product_code (str, optional): 외부에서 제공한 상품 코드
            
        Returns:
            dict: 상품 정보 딕셔너리
        """
        print("[INFO] 상품 정보 수집 시작...")
        
        if target_url.startswith('/'):
            target_url = 'https://brand.naver.com' + target_url
            
        try:
            if not self.driver:
                self.setup_driver()
            self.driver.get(target_url)
            time.sleep(3)
            
            html_source = self.driver.page_source
            soup = BeautifulSoup(html_source, 'html.parser')
            
            product_info = {}
            product_info['상품URL'] = target_url
            
            # 상품 제목 추출
            title_selectors = [
                'h3._22kNQuEXmb',
                'h3[class*="product_title"]',
                'div[class*="headingArea"] h2',
                'h2[class*="product_title"]'
            ]
            for selector in title_selectors:
                title_element = soup.select_one(selector)
                if title_element:
                    product_info['상품명'] = title_element.get_text(strip=True)
                    break
            
            # 가격 정보 추출
            price_selectors = [
                'span[class*="price_num"]',
                'span.price_num__OMokY',
                'div[class*="price"] strong',
                'em[class*="price"]'
            ]
            for selector in price_selectors:
                price_element = soup.select_one(selector)
                if price_element:
                    price_text = price_element.get_text(strip=True)
                    price_value = re.sub(r'[^\d]', '', price_text)
                    if price_value:
                        product_info['가격'] = price_value
                        break
            
            # 테이블 파싱
            tables_info = parse_product_info_tables(html_source)
            product_info.update(tables_info)
            print("[DEBUG] 테이블에서 파싱한 정보:")
            for k, v in tables_info.items():
                print(f"- {k}: {v}")
            
            # 상세 상품 정보 수집 및 표준화
            from reviewcrawler.product_info import crawl_detailed_product_info, standardize_product_info
            product_info = crawl_detailed_product_info(self.driver, product_info)
            standardized_info = standardize_product_info(product_info)
            
            # 상품 코드 저장
            # 외부에서 제공된 상품 코드가 있으면 사용, 없으면 생성
            if external_product_code:
                product_code = external_product_code
            else:
                product_code = generate_product_code(standardized_info)
            
            standardized_info['PRODUCT_CODE'] = product_code
            self.product_code = product_code  # 클래스 변수에 저장하여 이후 리뷰에서 재사용
            
            if output_csv and standardized_info:
                df = pd.DataFrame([standardized_info])
                cols = df.columns.tolist()
                new_order = ['PRODUCT_CODE', '상품명'] + [col for col in cols if col not in ['PRODUCT_CODE', '상품명']]
                df = df[new_order]
                df.to_csv(output_csv, index=False, encoding='utf-8-sig')
                print(f"[INFO] 표준화된 상품 정보가 {output_csv}에 저장되었습니다.")
            
            print("[INFO] 상품 정보 수집 완료!")
            return standardized_info
        
        except Exception as e:
            print(f"[ERROR] 상품 정보 수집 중 오류 발생: {e}")
            import traceback
            traceback.print_exc()
            from reviewcrawler.product_info import standardize_product_info
            return standardize_product_info(product_info if 'product_info' in locals() else {})
    
    def crawl_reviews(self, target_url, max_pages=None, output_csv=None, return_df=False, append_mode=False, product_code=None):
        """
        스마트스토어 상품의 리뷰 데이터 수집
        
        Args:
            target_url (str): 상품 페이지 URL
            max_pages (int, optional): 수집할 최대 페이지 수 (기본값: 모든 페이지)
            output_csv (str, optional): 결과를 저장할 CSV 파일명
            return_df (bool, optional): 데이터프레임 반환 여부
            append_mode (bool, optional): 기존 CSV에 결과 추가 여부
            product_code (str, optional): 미리 생성된 상품 코드. 없으면 객체에 저장된 코드 사용
            
        Returns:
            DataFrame: return_df True 시 데이터프레임 반환
        """
        from reviewcrawler.review_crawler import crawl_product_reviews
        
        # product_code 인자가 없으면 객체의 product_code 사용
        if product_code is None:
            product_code = self.product_code
            
        return crawl_product_reviews(
            target_url=target_url,
            driver=self.driver,
            max_pages=max_pages,
            output_csv=output_csv,
            return_df=return_df,
            append_mode=append_mode,
            product_code=product_code  # 상품 코드 전달
        )