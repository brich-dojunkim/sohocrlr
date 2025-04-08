#!/usr/bin/env python
import os
import time
import csv
import argparse
from tqdm import tqdm
from urlcrawler import scrape_multiple_pages
from reviewcrawler import crawl_reviews

def main():
    """
    메인 함수: URL 크롤링 후 각 상품 페이지에서 리뷰 데이터를 단일 스레드로 수집
    (모든 리뷰 페이지 수집, 헤드리스 모드, 터미널에 진행률 표시)
    """
    parser = argparse.ArgumentParser(
        description='네이버 스마트스토어 URL 및 리뷰 크롤러 (단일 스레드, 모든 리뷰 페이지, 헤드리스)'
    )
    parser.add_argument('--url', type=str, required=True,
                        help='크롤링 시작할 스마트스토어 카테고리/검색 URL')
    # review_pages 인자는 사용하지 않고, 모든 리뷰 페이지를 수집합니다.
    parser.add_argument('--output', type=str, default='navershopping_reviews.csv',
                        help='리뷰 결과를 저장할 CSV 파일명')
    parser.add_argument('--save_urls', action='store_true',
                        help='수집한 URL 목록을 CSV로 저장 (저장하지 않으면 임시 파일 사용)')
    args = parser.parse_args()

    print("=" * 50)
    print("네이버 스마트스토어 URL 및 리뷰 크롤러 (단일 스레드, 모든 리뷰 페이지, 헤드리스)")
    print("=" * 50)

    # STEP 1. 상품 URL 수집
    print("\n[STEP 1] 상품 URL 수집 시작")
    start_time = time.time()

    # 모든 상품 페이지를 수집하기 위해 아주 큰 값 설정 (urlcrawler.py에서 처리)
    max_page = 999  
    url_output = "product_urls.csv" if args.save_urls else "temp_urls.csv"

    # ※ urlcrawler.py에서 헤드리스 모드를 사용하려면 아래 줄의 주석을 해제하세요.
    # options.add_argument("--headless")
    scrape_multiple_pages(
        page_url=args.url,
        max_page=max_page,
        output_csv=url_output
    )

    # CSV 파일에서 수집한 상품 URL 읽어오기
    product_urls = []
    try:
        with open(url_output, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # 헤더 건너뛰기
            for row in reader:
                product_urls.append(row[0])
    except Exception as e:
        print(f"[ERROR] URL 파일 읽기 실패: {e}")

    if not args.save_urls and os.path.exists("temp_urls.csv"):
        os.remove("temp_urls.csv")

    if not product_urls:
        print("[ERROR] 상품 URL 수집에 실패했습니다.")
        return

    url_time = time.time() - start_time
    print(f"URL 수집 완료: {len(product_urls)}개 상품 URL 수집 (소요 시간: {url_time:.2f}초)")

    # STEP 2. 각 상품별 리뷰 수집 (모든 리뷰 페이지)
    print(f"\n[STEP 2] 각 상품별 리뷰 수집 시작 (총 {len(product_urls)}개 상품, 모든 리뷰 페이지)")
    review_start_time = time.time()

    # 기존 결과 파일이 있다면 삭제 (append 모드로 실행할 것이므로)
    if os.path.exists(args.output):
        os.remove(args.output)
        print(f"[INFO] 기존 {args.output} 파일을 삭제했습니다.")

    total_reviews = 0
    for idx, url in enumerate(tqdm(product_urls, desc="리뷰 수집 진행", unit="상품")):
        print(f"\n[{idx + 1}/{len(product_urls)}] 상품 리뷰 수집 중: {url}")
        try:
            # max_pages를 None으로 전달하여 모든 리뷰 페이지를 수집합니다.
            df = crawl_reviews(
                target_url=url,
                max_pages=None,
                output_csv=args.output,
                return_df=True,
                append_mode=True
            )
            count = len(df) if df is not None else 0
            print(f"[INFO] {url} 리뷰 수집 완료: {count}건")
            total_reviews += count
        except Exception as e:
            print(f"[ERROR] URL 처리 중 오류 발생: {url} - {str(e)}")

    review_time = time.time() - review_start_time
    total_time = time.time() - start_time

    # STEP 3. 결과 요약 출력
    print("\n" + "=" * 50)
    print("크롤링 완료 요약")
    print("=" * 50)
    print(f"- 총 상품 URL 수집: {len(product_urls)}개")
    print(f"- 총 리뷰 수집: {total_reviews}건")
    print(f"- URL 수집 시간: {url_time:.2f}초")
    print(f"- 리뷰 수집 시간: {review_time:.2f}초")
    print(f"- 총 소요 시간: {total_time:.2f}초")
    print(f"- 결과 저장 위치: {args.output}")
    print("=" * 50)

if __name__ == "__main__":
    main()
