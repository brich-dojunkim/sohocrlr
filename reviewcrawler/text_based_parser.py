# reviewcrawler/text_based_parser.py
from bs4 import BeautifulSoup

def parse_product_info_by_text(html_source):
    """
    텍스트 기반으로 상품 정보를 파싱하는 함수
    
    Args:
        html_source (str): HTML 소스
        
    Returns:
        dict: 파싱된 상품 정보
    """
    soup = BeautifulSoup(html_source, 'html.parser')
    product_info = {}
    
    # 찾고자 하는 상품 정보 라벨 목록
    target_labels = [
        '상품번호', '상품상태', '제조사', '브랜드', '모델명', '이벤트', '사은품', '원산지',
        '착용계절', '디테일', '사용대상', '여밈방식', '핏', '종류', '주요소재', '소매기장',
        '칼라종류', '패턴', '총기장', '영수증발급', 'A/S 안내', '제품소재', '색상', '치수',
        '제조자(사)', '제조국', '세탁방법 및 취급시 주의사항', '제조연월', '품질보증기준',
        'A/S 책임자와 전화번호'
    ]
    
    # 모든 th 태그 검색
    all_th = soup.find_all('th')
    
    for th in all_th:
        # th 텍스트 추출
        label_text = th.get_text(strip=True)
        
        # 타겟 라벨과 일치하는지 확인
        for target in target_labels:
            if label_text == target:
                # 같은 행에 있는 td 태그 찾기
                parent_tr = th.find_parent('tr')
                if parent_tr:
                    td_tags = parent_tr.find_all('td')
                    
                    if td_tags:
                        # colspan이 있는지 확인하여 적절한 td 선택
                        if th.has_attr('colspan') and int(th.get('colspan', 1)) > 1:
                            continue  # colspan이 있는 th는 헤더이므로 스킵
                        
                        # td 태그에서 텍스트 추출
                        td_index = list(parent_tr.find_all('th')).index(th)
                        if td_index < len(td_tags):
                            td = td_tags[td_index]
                            
                            # b 태그 확인
                            b_tag = td.find('b')
                            if b_tag:
                                value = b_tag.get_text(strip=True)
                            else:
                                # button 태그 확인
                                button_tag = td.find('button')
                                if button_tag:
                                    value = button_tag.get_text(strip=True)
                                else:
                                    # div 태그 확인
                                    div_tag = td.find('div')
                                    if div_tag:
                                        value = div_tag.get_text(strip=True)
                                    else:
                                        value = td.get_text(strip=True)
                            
                            # 값이 있으면 저장
                            if value and not value.isspace():
                                product_info[label_text] = value
                                print(f"[DEBUG] 텍스트 매칭으로 추출: {label_text} -> {value}")
    
    # 상품명 추출 (별도 처리)
    title_selectors = [
        'h3._22kNQuEXmb',
        'h3[class*="product_title"]',
        'div[class*="headingArea"] h2',
        'h2[class*="product_title"]',
        'h3.product_title',
        'h2.product_name'
    ]
    
    for selector in title_selectors:
        title_element = soup.select_one(selector)
        if title_element:
            product_info['상품명'] = title_element.get_text(strip=True)
            break
    
    # 가격 추출 (별도 처리)
    price_selectors = [
        'span[class*="price_num"]',
        'span.price_num__OMokY',
        'div[class*="price"] strong',
        'em[class*="price"]',
        'span.price',
        'strong.price'
    ]
    
    for selector in price_selectors:
        price_element = soup.select_one(selector)
        if price_element:
            price_text = price_element.get_text(strip=True)
            import re
            price_value = re.sub(r'[^\d]', '', price_text)
            if price_value:
                product_info['가격'] = price_value
                break
    
    return product_info