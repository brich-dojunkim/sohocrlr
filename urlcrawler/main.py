# urlcrawler/main.py
import csv
import time
import traceback
from tqdm import tqdm
import hashlib
from driver import setup_driver
from page_navigation import (
    navigate_to_base_page,
    get_subcategory_items,       # 기존 소분류 → 2nd depth
    click_subcategory,           # 2nd depth 클릭
    get_first_detail_menu_items, # 기존 첫 번째 detail → 3rd depth
    click_first_detail_menu,     # 3rd depth 클릭
    get_second_detail_menu_items,# 기존 두 번째 detail → 4th depth
    click_second_detail_menu     # 4th depth 클릭
)
from scraper import scrape_product_urls, apply_sort_filter
from utils import safe_click

def run_url_crawler(max_depth=None, product_limit=None):
    """
    URL 크롤러 실행 함수
    
    Args:
        max_depth: 크롤링할 최대 depth (1-4) 
        product_limit: 각 depth에서 크롤링할 제품 수
        
    Returns:
        str: 생성된 CSV 파일명
    """
    # 인자가 제공되지 않았을 경우 사용자 입력 받기
    if max_depth is None:
        try:
            max_depth = int(input("몇번째 depth까지 크롤링할 건지 입력하세요 (1 ~ 4): "))
        except ValueError:
            print("잘못된 입력입니다. 기본값 4로 설정합니다.")
            max_depth = 4
    
    if max_depth < 1 or max_depth > 4:
        print("입력 범위가 잘못되었습니다. 1과 4 사이의 숫자로 설정합니다.")
        max_depth = 4

    if product_limit is None:
        try:
            product_limit = int(input("각 depth에서 크롤링할 제품 URL 개수를 입력하세요 (예: 10): "))
        except ValueError:
            print("잘못된 입력입니다. 기본값 10으로 설정합니다.")
            product_limit = 10

    driver = setup_driver()
    
    print(">> [DEBUG] safe_click 함수:", safe_click, type(safe_click))
    
    # CSV 파일 생성 (헤더: 새 용어 사용)
    csv_filename = "all_category_product_urls.csv"
    with open(csv_filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["1st_depth", "2nd_depth", "3rd_depth", "4th_depth", "제품_URL"])
    
    try:
        print("=" * 50)
        print("네이버 쇼핑 카테고리별 제품 URL 수집기")
        print("=" * 50)
        
        # 1st depth: 기본 페이지 (예, "여성의류")
        navigate_to_base_page(driver)
        
        # 만약 최대 depth가 1이면, 기본 페이지에서 바로 크롤링
        if max_depth == 1:
            apply_sort_filter(driver, safe_click)
            urls = scrape_product_urls(driver, limit=product_limit)
            print(f">> [INFO] 1st depth 페이지에서 제품 URL {len(urls)}개 추출 완료")
            with open(csv_filename, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                for url in urls:
                    writer.writerow(["여성의류", "", "", "", url])
            print(f"\n>> [SUCCESS] 모든 크롤링 완료. URL은 '{csv_filename}'에 저장됨.")
            driver.quit()
            return csv_filename

        # 최대 depth >= 2: 2nd depth (소분류) 처리
        subcategory_texts = get_subcategory_items(driver)
        if not subcategory_texts:
            raise Exception("2nd depth 메뉴 항목(소분류)을 찾지 못했습니다.")
        
        # tqdm으로 진행률 표시 추가
        for subcat_idx, subcategory_text in enumerate(tqdm(subcategory_texts, desc="2nd depth 처리")):
            try:
                print(f"\n>> [INFO] 2nd depth ({subcat_idx+1}/{len(subcategory_texts)}): '{subcategory_text}' 처리 시작")
                click_subcategory(driver, subcategory_text)
                
                # 만약 최대 depth가 2이면, 2nd depth에서 직접 제품 URL 크롤링
                if max_depth == 2:
                    apply_sort_filter(driver, safe_click)
                    urls = scrape_product_urls(driver, limit=product_limit)
                    print(f">> [INFO] 2nd depth '{subcategory_text}'에서 제품 URL {len(urls)}개 추출 완료")
                    with open(csv_filename, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        for url in urls:
                            writer.writerow(["여성의류", subcategory_text, "", "", url])
                    navigate_to_base_page(driver)
                    continue
                
                # 최대 depth >= 3: 3rd depth 처리 (첫 번째 detail 메뉴)
                first_detail_menu_texts = get_first_detail_menu_items(driver)
                if not first_detail_menu_texts:
                    print(f">> [INFO] 2nd depth '{subcategory_text}'에서 3rd depth 항목이 없습니다. 제품 크롤링 진행.")
                    apply_sort_filter(driver, safe_click)
                    urls = scrape_product_urls(driver, limit=product_limit)
                    with open(csv_filename, "a", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        for url in urls:
                            writer.writerow(["여성의류", subcategory_text, "", "", url])
                    navigate_to_base_page(driver)
                    click_subcategory(driver, subcategory_text)
                    continue
                
                # tqdm으로 3rd depth 진행률 표시
                for i, first_detail_text in enumerate(tqdm(first_detail_menu_texts, desc=f"'{subcategory_text}' 3rd depth 처리")):
                    try:
                        print(f"\n>> [INFO] 3rd depth ({i+1}/{len(first_detail_menu_texts)}): '{first_detail_text}' 처리 시작")
                        click_first_detail_menu(driver, first_detail_text)
                        
                        # 만약 최대 depth가 3이면, 여기서 제품 URL 크롤링 진행
                        if max_depth == 3:
                            apply_sort_filter(driver, safe_click)
                            urls = scrape_product_urls(driver, limit=product_limit)
                            print(f">> [INFO] 3rd depth '{first_detail_text}'에서 제품 URL {len(urls)}개 추출 완료")
                            with open(csv_filename, "a", newline="", encoding="utf-8") as f:
                                writer = csv.writer(f)
                                for url in urls:
                                    writer.writerow(["여성의류", subcategory_text, first_detail_text, "", url])
                            navigate_to_base_page(driver)
                            click_subcategory(driver, subcategory_text)
                            continue
                        
                        # 최대 depth가 4이면, 4th depth 처리 (두 번째 detail 메뉴)
                        second_detail_menu_texts = get_second_detail_menu_items(driver)
                        if not second_detail_menu_texts:
                            print(f">> [INFO] 3rd depth '{first_detail_text}'에서 4th depth 항목이 없습니다. 제품 크롤링 진행.")
                            apply_sort_filter(driver, safe_click)
                            urls = scrape_product_urls(driver, limit=product_limit)
                            with open(csv_filename, "a", newline="", encoding="utf-8") as f:
                                writer = csv.writer(f)
                                for url in urls:
                                    writer.writerow(["여성의류", subcategory_text, first_detail_text, "", url])
                            navigate_to_base_page(driver)
                            click_subcategory(driver, subcategory_text)
                            click_first_detail_menu(driver, first_detail_text)
                            continue
                        
                        # tqdm으로 4th depth 진행률 표시
                        for j, second_detail_text in enumerate(tqdm(second_detail_menu_texts, desc=f"'{first_detail_text}' 4th depth 처리")):
                            retry_count = 0
                            max_retries = 3
                            success = False
                            
                            while retry_count < max_retries and not success:
                                try:
                                    print(f"\n>> [INFO] 4th depth ({j+1}/{len(second_detail_menu_texts)}): '{second_detail_text}' 처리 시작")
                                    if retry_count > 0:
                                        print(f">> [DEBUG] 재시도 {retry_count}: 3rd depth '{first_detail_text}' 다시 클릭")
                                        navigate_to_base_page(driver)
                                        click_subcategory(driver, subcategory_text)
                                        click_first_detail_menu(driver, first_detail_text)
                                        time.sleep(1)
                                    
                                    click_second_detail_menu(driver, second_detail_text)
                                    apply_sort_filter(driver, safe_click)
                                    urls = scrape_product_urls(driver, limit=product_limit)
                                    if not urls:
                                        raise Exception(f"'{first_detail_text} > {second_detail_text}'에서 제품 URL 추출 실패")
                                    
                                    print(f">> [INFO] 4th depth '{second_detail_text}'에서 제품 URL {len(urls)}개 추출 완료")
                                    with open(csv_filename, "a", newline="", encoding="utf-8") as f:
                                        writer = csv.writer(f)
                                        for url in urls:
                                            writer.writerow(["여성의류", subcategory_text, first_detail_text, second_detail_text, url])
                                    success = True
                                
                                except Exception as e:
                                    retry_count += 1
                                    print(f">> [ERROR] 4th depth '{second_detail_text}' 처리 오류 (시도 {retry_count}/{max_retries}): {e}")
                                    if retry_count >= max_retries:
                                        print(f">> [ERROR] 최대 재시도 초과: '{second_detail_text}' 건너뜀")
                                        break
                                    navigate_to_base_page(driver)
                                    click_subcategory(driver, subcategory_text)
                                    click_first_detail_menu(driver, first_detail_text)
                        # 3rd depth 내 다음 항목 처리를 위해 초기화
                        navigate_to_base_page(driver)
                        click_subcategory(driver, subcategory_text)
                    
                    except Exception as e:
                        print(f">> [ERROR] 3rd depth '{first_detail_text}' 처리 오류:", e)
                        navigate_to_base_page(driver)
                        click_subcategory(driver, subcategory_text)
                        continue
                # 2nd depth 내 다음 소분류 처리를 위해 초기화
                navigate_to_base_page(driver)
            
            except Exception as e:
                print(f">> [ERROR] 2nd depth '{subcategory_text}' 처리 오류:", e)
                navigate_to_base_page(driver)
                continue
        
        print(f"\n>> [SUCCESS] 모든 크롤링 완료. 수집된 URL은 '{csv_filename}'에 저장되었습니다.")
    
    except Exception as e:
        print(">> [CRITICAL] 프로그램 실행 중 치명적 오류 발생:", e)
        traceback.print_exc()
    
    finally:
        driver.quit()
    
    return csv_filename

# 직접 실행 시
if __name__ == "__main__":
    run_url_crawler()