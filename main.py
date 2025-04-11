#!/usr/bin/env python
# main.py - urlcrawler와 reviewcrawler를 통합 실행하는 메인 스크립트

import os
import sys
import argparse
import pandas as pd
from tqdm import tqdm
import time
import hashlib

# URLCrawler와 ReviewCrawler 모듈 경로 추가
sys.path.append('./urlcrawler')
sys.path.append('./reviewcrawler')

# urlcrawler와 reviewcrawler에서 필요한 모듈 import
from urlcrawler.driver import setup_driver as setup_url_driver
from urlcrawler.main import run_url_crawler
from reviewcrawler.crawler import NaverShoppingCrawler

def convert_csv_to_excel(csv_path, excel_path=None):
    """
    CSV 파일을 엑셀 파일로 변환합니다.
    
    Args:
        csv_path (str): CSV 파일 경로
        excel_path (str, optional): 생성할 엑셀 파일 경로 (None인 경우 CSV와 동일한 이름 사용)
    
    Returns:
        str: 생성된 엑셀 파일 경로
    """
    if excel_path is None:
        excel_path = csv_path.replace('.csv', '.xlsx')
    
    try:
        df = pd.read_csv(csv_path, encoding='utf-8-sig')
        df.to_excel(excel_path, index=False, engine='openpyxl')
        print(f"Excel 파일 생성 완료: {excel_path}")
        return excel_path
    except Exception as e:
        print(f"Excel 파일 생성 중 오류 발생: {e}")
        return None

def crawl_urls(max_depth=None, product_limit=None):
    """
    URL 크롤링 단계 실행
    
    Args:
        max_depth: 크롤링할 최대 depth (1-4)
        product_limit: 각 depth에서 크롤링할 제품 수
    
    Returns:
        DataFrame: 크롤링된 URL과 depth 정보가 포함된 DataFrame
    """
    print("="*80)
    print("1단계: URL 크롤링 시작")
    print("="*80)
    
    # 매개변수가 지정되지 않은 경우 터미널에서 입력 받기
    if max_depth is None:
        while True:
            try:
                max_depth = int(input("몇번째 depth까지 크롤링할 건지 입력하세요 (1 ~ 4): "))
                if 1 <= max_depth <= 4:
                    break
                else:
                    print("입력 범위가 잘못되었습니다. 1과 4 사이의 숫자를 입력하세요.")
            except ValueError:
                print("숫자를 입력하세요.")
    
    if product_limit is None:
        while True:
            try:
                product_limit = int(input("각 depth에서 크롤링할 제품 URL 개수를 입력하세요 (예: 10): "))
                if product_limit > 0:
                    break
                else:
                    print("0보다 큰 숫자를 입력하세요.")
            except ValueError:
                print("숫자를 입력하세요.")
    
    # url_crawler의 run_url_crawler 함수 호출
    run_url_crawler(max_depth=max_depth, product_limit=product_limit)
    
    # 생성된 CSV 확인 및 로드
    csv_filename = 'all_category_product_urls.csv'
    if not os.path.exists(csv_filename):
        print(f"[ERROR] URL 크롤링 결과 파일을 찾을 수 없습니다: {csv_filename}")
        sys.exit(1)
    
    # DataFrame으로 로드
    url_df = pd.read_csv(csv_filename)
    
    # PRODUCT_CODE 생성 (없는 경우)
    if 'PRODUCT_CODE' not in url_df.columns:
        print("PRODUCT_CODE 생성 중...")
        
        # PRODUCT_CODE 생성 함수
        def create_product_code(row):
            url = row['제품_URL']
            string_to_hash = url
            return hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()[:8]
        
        # PRODUCT_CODE 컬럼 추가
        url_df['PRODUCT_CODE'] = url_df.apply(create_product_code, axis=1)
        
        # 수정된 DataFrame을 다시 저장
        url_df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"PRODUCT_CODE 생성 완료. 총 {len(url_df)}개의 URL에 코드가 생성되었습니다.")
    
    print(f"URL 크롤링 완료. 총 {len(url_df)}개의 URL이 수집되었습니다.")
    return url_df

def crawl_product_info_and_reviews(url_df, max_pages=5, max_products=None, max_retries=3):
    """
    URL 데이터프레임을 받아 각 제품의 정보와 리뷰를 크롤링
    
    Args:
        url_df: URL과 카테고리 정보가 있는 DataFrame
        max_pages: 각 제품에서 크롤링할 최대 리뷰 페이지 수
        max_products: 최대 처리할 제품 수 (None이면 모두 처리)
        max_retries: 실패 시 최대 재시도 횟수
    
    Returns:
        tuple: (product_info_df, reviews_df) - 수집된 제품 정보와 리뷰 DataFrame
    """
    print("="*80)
    print("2단계: 제품 정보 및 리뷰 크롤링 시작")
    print("="*80)
    
    # 결과를 저장할 DataFrame 생성
    product_info_list = []
    review_dfs = []
    
    # 처리할 제품 수 제한
    if max_products and max_products < len(url_df):
        url_df = url_df.head(max_products)
        print(f"처리할 제품 수를 {max_products}개로 제한합니다.")
    
    # 네이버 쇼핑 크롤러 초기화
    crawler = NaverShoppingCrawler()
    
    try:
        # 각 URL에 대해 크롤링 수행
        for index, row in tqdm(url_df.iterrows(), total=len(url_df), desc="제품 크롤링 진행"):
            product_code = row['PRODUCT_CODE']
            url = row['제품_URL']
            
            # 카테고리 정보 추출
            depth1 = row.get('1st_depth', '')
            depth2 = row.get('2nd_depth', '')
            depth3 = row.get('3rd_depth', '')
            depth4 = row.get('4th_depth', '')
            
            print(f"\n처리 중: {index+1}/{len(url_df)} - {url}")
            print(f"카테고리: {depth1} > {depth2} > {depth3} > {depth4}")
            print(f"상품 코드: {product_code}")
            
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    # 제품 정보 크롤링
                    temp_product_file = f"temp_product_{product_code}.csv"
                    product_info = crawler.crawl_product_info(
                        target_url=url,
                        output_csv=temp_product_file
                    )
                    
                    if product_info:
                        # 카테고리 정보 추가
                        product_info['1st_depth'] = depth1
                        product_info['2nd_depth'] = depth2 
                        product_info['3rd_depth'] = depth3
                        product_info['4th_depth'] = depth4
                        
                        # 상품 코드 확인/설정
                        if 'PRODUCT_CODE' not in product_info or not product_info['PRODUCT_CODE']:
                            product_info['PRODUCT_CODE'] = product_code
                        
                        # 결과 리스트에 추가
                        product_info_list.append(product_info)
                        print("  - 제품 정보 수집 완료")
                    else:
                        print("  - 제품 정보 수집 실패")
                    
                    # 리뷰 크롤링
                    temp_review_file = f"temp_review_{product_code}.csv"
                    reviews_df = crawler.crawl_reviews(
                        target_url=url,
                        max_pages=max_pages,
                        output_csv=temp_review_file,
                        return_df=True
                    )
                    
                    if reviews_df is not None and not reviews_df.empty:
                        # 카테고리 정보 추가
                        reviews_df['1st_depth'] = depth1
                        reviews_df['2nd_depth'] = depth2
                        reviews_df['3rd_depth'] = depth3
                        reviews_df['4th_depth'] = depth4
                        
                        # 결과 리스트에 추가
                        review_dfs.append(reviews_df)
                        print(f"  - 리뷰 수집: {len(reviews_df)}개")
                    else:
                        print("  - 리뷰 없음 또는 수집 실패")
                    
                    # 임시 파일 삭제
                    if os.path.exists(temp_product_file):
                        os.remove(temp_product_file)
                    if os.path.exists(temp_review_file):
                        os.remove(temp_review_file)
                    
                    success = True
                
                except Exception as e:
                    retry_count += 1
                    print(f"오류 발생 ({retry_count}/{max_retries}): {e}")
                    
                    # 재시도 전 대기
                    if retry_count < max_retries:
                        print(f"5초 후 재시도...")
                        time.sleep(5)
                        
                        # 드라이버 재설정
                        crawler.close()
                        crawler.setup_driver()
                    else:
                        print(f"최대 재시도 횟수 초과. 다음 제품으로 넘어갑니다.")
        
        # 결과 DataFrame 생성
        product_info_df = None
        reviews_df = None
        
        if product_info_list:
            product_info_df = pd.DataFrame(product_info_list)
            product_info_csv = 'product_info_all.csv'
            product_info_excel = 'product_info_all.xlsx'
            
            product_info_df.to_csv(product_info_csv, index=False, encoding='utf-8-sig')
            print(f"\n제품 정보 저장 완료: {product_info_csv} ({len(product_info_df)}개)")
            
            # CSV를 엑셀로 변환
            convert_csv_to_excel(product_info_csv, product_info_excel)
        else:
            print("\n수집된 제품 정보가 없습니다.")
        
        if review_dfs:
            reviews_df = pd.concat(review_dfs, ignore_index=True)
            review_csv = 'review_all.csv'
            review_excel = 'review_all.xlsx'
            
            reviews_df.to_csv(review_csv, index=False, encoding='utf-8-sig')
            print(f"리뷰 정보 저장 완료: {review_csv} ({len(reviews_df)}개)")
            
            # CSV를 엑셀로 변환
            convert_csv_to_excel(review_csv, review_excel)
        else:
            print("수집된 리뷰가 없습니다.")
        
        return product_info_df, reviews_df
    
    finally:
        # 크롤러 종료
        crawler.close()

def main():
    parser = argparse.ArgumentParser(description='네이버 쇼핑 통합 크롤러')
    parser.add_argument('--skip-url-crawl', action='store_true', help='URL 크롤링 단계 건너뛰기')
    parser.add_argument('--max-depth', type=int, help='크롤링할 최대 depth (1-4) (미지정 시 터미널에서 입력)')
    parser.add_argument('--product-limit', type=int, help='각 depth에서 크롤링할 제품 수 (미지정 시 터미널에서 입력)')
    parser.add_argument('--max-products', type=int, default=None, help='처리할 최대 제품 수')
    parser.add_argument('--max-pages', type=int, default=5, help='각 제품에서 크롤링할 최대 리뷰 페이지 수')
    args = parser.parse_args()
    
    start_time = time.time()
    
    if not args.skip_url_crawl:
        # URL 크롤링 실행 (인자가 없으면 터미널에서 입력 받음)
        url_df = crawl_urls(max_depth=args.max_depth, product_limit=args.product_limit)
    else:
        # 기존 URL CSV 파일 로드
        if not os.path.exists('all_category_product_urls.csv'):
            print("all_category_product_urls.csv 파일이 존재하지 않습니다. URL 크롤링을 먼저 실행하세요.")
            sys.exit(1)
        url_df = pd.read_csv('all_category_product_urls.csv')
        print(f"기존 URL 파일을 로드했습니다. 총 {len(url_df)}개의 URL.")
    
    # 제품 정보 및 리뷰 크롤링
    product_info_df, reviews_df = crawl_product_info_and_reviews(
        url_df, 
        max_pages=args.max_pages,
        max_products=args.max_products
    )
    
    elapsed_time = time.time() - start_time
    print("="*80)
    print(f"크롤링 완료! 총 소요 시간: {elapsed_time:.2f}초")
    
    if product_info_df is not None:
        print(f"수집된 제품 정보: {len(product_info_df)}개")
    if reviews_df is not None:
        print(f"수집된 리뷰: {len(reviews_df)}개")
    print("="*80)

if __name__ == "__main__":
    main()