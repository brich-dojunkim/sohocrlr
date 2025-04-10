# reviewcrawler/main.py
import argparse
import time
import pandas as pd
import os
from tqdm import tqdm
from reviewcrawler.crawler import NaverShoppingCrawler

def run_review_crawler(url=None, url_file=None, max_pages=5, output_csv='review_all.csv', 
                      product_output_csv='product_info_all.csv', reviews_only=False, 
                      product_only=False, max_products=None, use_tqdm=True):
    """
    리뷰 크롤러 실행 함수
    
    Args:
        url: 단일 URL 크롤링 시 사용
        url_file: URL 목록 CSV 파일
        max_pages: 수집할 리뷰 최대 페이지 수
        output_csv: 리뷰 저장 CSV 파일명
        product_output_csv: 상품 정보 저장 CSV 파일명
        reviews_only: 리뷰만 수집 여부
        product_only: 상품 정보만 수집 여부
        max_products: 최대 처리할 제품 수
        use_tqdm: tqdm 진행 표시줄 사용 여부
        
    Returns:
        tuple: (product_info_df, reviews_df) 수집된 제품 정보와 리뷰 데이터프레임
    """
    
    # 단일 URL 또는 URL 파일 확인
    if url:
        # 단일 URL 모드
        target_urls = [url]
        product_codes = [None]  # 상품 코드는 크롤러에서 생성될 것임
        depth_info = [(None, None, None, None)]  # 카테고리 정보 없음
    elif url_file:
        # CSV 파일에서 URL 목록 불러오기
        if not os.path.exists(url_file):
            print(f"[ERROR] URL 파일이 존재하지 않습니다: {url_file}")
            return None, None
        
        try:
            url_df = pd.read_csv(url_file)
            # 필요한 컬럼 확인
            required_cols = ['제품_URL']
            missing_cols = [col for col in required_cols if col not in url_df.columns]
            if missing_cols:
                print(f"[ERROR] URL 파일에 필요한 컬럼이 누락되었습니다: {missing_cols}")
                return None, None
            
            # PRODUCT_CODE 컬럼이 없으면 None으로 초기화
            if 'PRODUCT_CODE' not in url_df.columns:
                url_df['PRODUCT_CODE'] = None
            
            # 카테고리 depth 정보 추출
            depth_cols = ['1st_depth', '2nd_depth', '3rd_depth', '4th_depth']
            for col in depth_cols:
                if col not in url_df.columns:
                    url_df[col] = None
            
            # 최대 제품 수 제한
            if max_products:
                url_df = url_df.head(max_products)
            
            # URL 및 상품 코드 리스트 생성
            target_urls = url_df['제품_URL'].tolist()
            product_codes = url_df['PRODUCT_CODE'].tolist()
            depth_info = list(zip(
                url_df['1st_depth'].tolist(), 
                url_df['2nd_depth'].tolist(), 
                url_df['3rd_depth'].tolist(), 
                url_df['4th_depth'].tolist()
            ))
            
            print(f"[INFO] URL 파일에서 {len(target_urls)}개의 URL을 읽었습니다.")
        except Exception as e:
            print(f"[ERROR] URL 파일 읽기 오류: {e}")
            return None, None
    else:
        # 기본 URL 설정
        target_urls = ['https://brand.naver.com/onnon/products/8045986719']
        product_codes = [None]
        depth_info = [(None, None, None, None)]
        print(f"[INFO] URL이 제공되지 않아 기본 URL을 사용합니다: {target_urls[0]}")
    
    print("="*50)
    print("네이버 스마트스토어 상품 정보 및 리뷰 크롤러")
    print("="*50)
    
    # 결과를 저장할 리스트 초기화
    product_info_list = []
    review_dfs = []
    
    # 네이버 쇼핑 크롤러 초기화
    crawler = NaverShoppingCrawler()
    
    try:
        # 각 URL에 대해 크롤링 수행
        iterator = enumerate(zip(target_urls, product_codes, depth_info))
        if use_tqdm:
            iterator = tqdm(iterator, total=len(target_urls), desc="제품 크롤링 진행")
        
        for idx, (url, product_code, (depth1, depth2, depth3, depth4)) in iterator:
            print(f"\n처리 중: {idx+1}/{len(target_urls)} - {url}")
            if any([depth1, depth2, depth3, depth4]):
                print(f"카테고리: {depth1 or ''} > {depth2 or ''} > {depth3 or ''} > {depth4 or ''}")
            
            start_time = time.time()
            
            try:
                # 제품 정보 크롤링
                if not reviews_only:
                    temp_product_file = f"temp_product_{idx}.csv" if product_output_csv else None
                    product_info = crawler.crawl_product_info(
                        target_url=url,
                        output_csv=temp_product_file,
                        external_product_code=product_code
                    )
                    
                    # 상품 코드 업데이트 (외부 코드가 없었던 경우)
                    if not product_code:
                        product_code = crawler.product_code
                    
                    if product_info:
                        # 카테고리 정보 추가
                        if depth1:
                            product_info['1st_depth'] = depth1
                        if depth2:
                            product_info['2nd_depth'] = depth2
                        if depth3:
                            product_info['3rd_depth'] = depth3
                        if depth4:
                            product_info['4th_depth'] = depth4
                        
                        # 결과 리스트에 추가
                        product_info_list.append(product_info)
                        
                        # 임시 파일 삭제
                        if temp_product_file and os.path.exists(temp_product_file):
                            os.remove(temp_product_file)
                    
                # 리뷰 크롤링
                if not product_only:
                    temp_review_file = f"temp_review_{idx}.csv" if output_csv else None
                    reviews_df = crawler.crawl_reviews(
                        target_url=url,
                        max_pages=max_pages,
                        output_csv=temp_review_file,
                        return_df=True,
                        product_code=product_code
                    )
                    
                    if reviews_df is not None and not reviews_df.empty:
                        # 카테고리 정보 추가
                        if depth1:
                            reviews_df['1st_depth'] = depth1
                        if depth2:
                            reviews_df['2nd_depth'] = depth2
                        if depth3:
                            reviews_df['3rd_depth'] = depth3
                        if depth4:
                            reviews_df['4th_depth'] = depth4
                        
                        # 결과 리스트에 추가
                        review_dfs.append(reviews_df)
                        
                        print(f"  - 수집된 리뷰 수: {len(reviews_df)}개")
                        
                        # 임시 파일 삭제
                        if temp_review_file and os.path.exists(temp_review_file):
                            os.remove(temp_review_file)
                    else:
                        print("  - 수집된 리뷰가 없습니다.")
                
                # 처리 시간 출력
                elapsed_time = time.time() - start_time
                print(f"  - 처리 시간: {elapsed_time:.2f}초")
                
            except Exception as e:
                print(f"[ERROR] URL 처리 중 오류 발생: {e}")
                import traceback
                traceback.print_exc()
                
                # 드라이버 재설정
                crawler.close()
                crawler.setup_driver()
                continue
    
    finally:
        # 크롤러 종료
        crawler.close()
    
    # 결과 DataFrame 생성 및 저장
    product_info_df = None
    reviews_df = None
    
    if product_info_list and not reviews_only:
        product_info_df = pd.DataFrame(product_info_list)
        if product_output_csv:
            product_info_df.to_csv(product_output_csv, index=False, encoding='utf-8-sig')
            print(f"\n제품 정보 저장 완료: {product_output_csv} ({len(product_info_df)}개)")
    
    if review_dfs and not product_only:
        reviews_df = pd.concat(review_dfs, ignore_index=True) if review_dfs else None
        if output_csv and reviews_df is not None:
            reviews_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
            print(f"리뷰 정보 저장 완료: {output_csv} ({len(reviews_df)}개)")
    
    elapsed_time = time.time() - start_time
    print(f"\n총 소요 시간: {elapsed_time:.2f}초")
    print("="*50)
    
    return product_info_df, reviews_df

def main():
    parser = argparse.ArgumentParser(description='네이버 스마트스토어 상품 정보 및 리뷰 크롤러')
    parser.add_argument('--url', type=str, help='크롤링할 상품 URL')
    parser.add_argument('--url-file', type=str, default='all_category_product_urls.csv', help='크롤링할 URL 목록이 포함된 CSV 파일')
    parser.add_argument('--pages', type=int, default=5, help='수집할 최대 페이지 수 (기본값: 5)')
    parser.add_argument('--output', type=str, default='review_all.csv', help='통합 리뷰 결과를 저장할 CSV 파일명')
    parser.add_argument('--product-output', type=str, default='product_info_all.csv', help='통합 상품 정보를 저장할 CSV 파일명')
    parser.add_argument('--reviews-only', action='store_true', help='리뷰만 수집합니다 (상품 정보 수집 건너뜀)')
    parser.add_argument('--product-only', action='store_true', help='상품 정보만 수집합니다 (리뷰 수집 건너뜀)')
    parser.add_argument('--max-products', type=int, default=None, help='처리할 최대 제품 수')
    parser.add_argument('--use-tqdm', action='store_true', help='tqdm을 사용하여 진행 상황 표시')

    args = parser.parse_args()
    
    # 크롤러 실행
    run_review_crawler(
        url=args.url,
        url_file=args.url_file,
        max_pages=args.pages,
        output_csv=args.output,
        product_output_csv=args.product_output,
        reviews_only=args.reviews_only,
        product_only=args.product_only,
        max_products=args.max_products,
        use_tqdm=args.use_tqdm
    )

if __name__ == "__main__":
    main()