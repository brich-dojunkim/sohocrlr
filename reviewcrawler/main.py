# reviewcrawler/main.py
import argparse
import time
from crawler import NaverShoppingCrawler

def main():
    parser = argparse.ArgumentParser(description='네이버 스마트스토어 상품 정보 및 리뷰 크롤러')
    parser.add_argument('--url', type=str, help='크롤링할 상품 URL')
    parser.add_argument('--pages', type=int, default=None, help='수집할 최대 페이지 수 (기본값: 모든 페이지)')
    # 리뷰 결과 파일의 기본값을 review.csv로 변경했습니다.
    parser.add_argument('--output', type=str, default='review.csv', help='리뷰 결과를 저장할 CSV 파일명')
    parser.add_argument('--product-output', type=str, default='product_info.csv', help='상품 정보를 저장할 CSV 파일명')
    parser.add_argument('--reviews-only', action='store_true', help='리뷰만 수집합니다 (상품 정보 수집 건너뜀)')
    parser.add_argument('--product-only', action='store_true', help='상품 정보만 수집합니다 (리뷰 수집 건너뜀)')

    args = parser.parse_args()
    
    if not args.url:
        target_url = 'https://brand.naver.com/onnon/products/8045986719'
        print(f"[INFO] URL이 제공되지 않아 기본 URL을 사용합니다: {target_url}")
    else:
        target_url = args.url
    
    print("="*50)
    print("네이버 스마트스토어 상품 정보 및 리뷰 크롤러")
    print("="*50)
    print(f"대상 URL: {target_url}")
    print(f"최대 페이지 수: {args.pages if args.pages else '제한 없음'}")
    if not args.product_only:
        print(f"리뷰 출력 파일: {args.output}")
    if not args.reviews_only:
        print(f"상품 정보 출력 파일: {args.product_output}")
    print("="*50)
    
    start_time = time.time()
    
    crawler = NaverShoppingCrawler()
    
    try:
        product_info = None
        if not args.reviews_only:
            product_info = crawler.crawl_product_info(
                target_url=target_url,
                output_csv=args.product_output
            )
            
            if product_info:
                print("\n상품 정보 수집 완료:")
                for k, v in product_info.items():
                    print(f"- {k}: {v}")
        
        reviews_df = None
        if not args.product_only:
            reviews_df = crawler.crawl_reviews(
                target_url=target_url,
                max_pages=args.pages,
                output_csv=args.output,
                return_df=True
            )
            
            if reviews_df is not None and not reviews_df.empty:
                print(f"\n- 수집된 리뷰 수: {len(reviews_df)}개")
                print(f"- 평균 별점: {reviews_df['RD_RATING'].astype(float).mean():.1f}/5.0")
                print(f"- 결과 저장 위치: {args.output}")
            else:
                print("\n- 수집된 리뷰가 없습니다.")
    
    finally:
        crawler.close()
        
    elapsed_time = time.time() - start_time
    print(f"\n- 총 소요 시간: {elapsed_time:.2f}초")
    print("="*50)

if __name__ == "__main__":
    main()
