# urlcrawler/page_navigation.py
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from utils import safe_click

def navigate_to_base_page(driver):
    """
    기본 카테고리 페이지로 이동 후 대분류(여성의류)를 선택합니다.
    """
    base_url = "https://shopping.naver.com/window/style/category?menu=20033952"
    print(">> [DEBUG] 접속할 URL:", base_url)
    driver.get(base_url)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul.flicking-camera")))
    time.sleep(1)

    # 대분류(여성의류) 선택 (이미 선택되어 있다면 클릭 건너뜁니다.)
    outer_buttons = driver.find_elements(By.CSS_SELECTOR, "button.imageMenu_button__q1s9j")
    target_outer = None
    for btn in outer_buttons:
        try:
            txt = btn.text.strip()
            classes = btn.get_attribute("class") or ""
            if "여성의류" in txt and "전체" not in txt:
                target_outer = btn
                if "active" in classes.lower() or "selected" in classes.lower():
                    print(">> [DEBUG] 대분류 이미 선택됨:", txt)
                    break
                else:
                    # 클릭이 필요한 경우
                    break
        except Exception:
            continue

    if not target_outer:
        raise Exception("대분류 메뉴에서 '여성의류' 버튼(전체 제외)을 찾지 못했습니다.")

    if not ("active" in target_outer.get_attribute("class").lower() or "selected" in target_outer.get_attribute("class").lower()):
        safe_click(driver, target_outer, "대분류")
    else:
        print(">> [DEBUG] 대분류 버튼 클릭 건너뜀 (이미 선택됨)")

    print(">> [DEBUG] 대분류 선택:", target_outer.text.strip())
    time.sleep(1)

def get_subcategory_items(driver):
    """
    소분류 메뉴 항목들의 텍스트를 수집합니다.
    """
    WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "button.roundButtonMenu_button__K8uup")))
    sub_buttons = driver.find_elements(By.CSS_SELECTOR, "button.roundButtonMenu_button__K8uup")

    subcategory_texts = []
    for btn in sub_buttons:
        try:
            txt = btn.text.strip()
            if txt and txt != "전체":
                subcategory_texts.append(txt)
                print(f">> [DEBUG] 소분류 항목: '{txt}'")
        except Exception:
            continue

    return subcategory_texts

def click_subcategory(driver, subcategory_text):
    """
    소분류 메뉴 항목 중 지정된 텍스트를 가진 항목을 클릭합니다.
    """
    WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "button.roundButtonMenu_button__K8uup")))
    sub_buttons = driver.find_elements(By.CSS_SELECTOR, "button.roundButtonMenu_button__K8uup")
    target_button = None
    for btn in sub_buttons:
        try:
            txt = btn.text.strip()
            if txt == subcategory_text:
                target_button = btn
                break
        except Exception:
            continue

    if not target_button:
        raise Exception(f"소분류 메뉴에서 '{subcategory_text}' 항목을 찾지 못했습니다.")

    classes = target_button.get_attribute("class") or ""
    if "active" in classes.lower() or "selected" in classes.lower():
        print(f">> [DEBUG] 소분류 '{subcategory_text}' 이미 선택됨")
    else:
        safe_click(driver, target_button, f"소분류 '{subcategory_text}'")
    print(f">> [DEBUG] 소분류 선택: {subcategory_text}")
    time.sleep(1)

def get_first_detail_menu_items(driver):
    """
    첫 번째 detail 메뉴 항목들의 텍스트를 리스트로 반환합니다.
    """
    WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "div.textMenuPc_text_menu_pc__7l6HC.textMenuPc_second_menu__wdNMp"))
    )
    first_detail_containers = driver.find_elements(By.CSS_SELECTOR, "div.textMenuPc_text_menu_pc__7l6HC.textMenuPc_second_menu__wdNMp")
    if not first_detail_containers:
        print(">> [DEBUG] 첫 번째 detail 메뉴 컨테이너를 찾지 못했습니다.")
        return []
    first_detail_container = first_detail_containers[0]
    detail_buttons = first_detail_container.find_elements(By.CSS_SELECTOR, "button.textMenuPc_menu_button__aUoDb")
    menu_texts = []
    for btn in detail_buttons:
        try:
            txt = btn.text.strip()
            if txt and txt != "전체":
                menu_texts.append(txt)
                print(f">> [DEBUG] 첫 번째 detail 메뉴 항목: '{txt}'")
        except Exception:
            continue
    return menu_texts

def click_first_detail_menu(driver, menu_text):
    """
    첫 번째 detail 메뉴에서 지정된 텍스트 항목을 클릭합니다.
    """
    WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "div.textMenuPc_text_menu_pc__7l6HC.textMenuPc_second_menu__wdNMp"))
    )
    first_detail_containers = driver.find_elements(By.CSS_SELECTOR, "div.textMenuPc_text_menu_pc__7l6HC.textMenuPc_second_menu__wdNMp")
    if not first_detail_containers:
        raise Exception("첫 번째 detail 메뉴 컨테이너를 찾지 못했습니다.")
    first_detail_container = first_detail_containers[0]
    detail_buttons = first_detail_container.find_elements(By.CSS_SELECTOR, "button.textMenuPc_menu_button__aUoDb")
    target_button = None
    for btn in detail_buttons:
        try:
            txt = btn.text.strip()
            if txt == menu_text:
                target_button = btn
                break
        except Exception:
            continue
    if not target_button:
        raise Exception(f"첫 번째 detail 메뉴에서 '{menu_text}' 항목을 찾지 못했습니다.")
    safe_click(driver, target_button, f"첫 번째 detail 메뉴 '{menu_text}'")
    time.sleep(2)

def get_second_detail_menu_items(driver):
    """
    두 번째 detail 메뉴 영역의 항목 텍스트들을 리스트로 반환합니다.
    """
    WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "div.textMenuPc_text_menu_pc__7l6HC.textMenuPc_second_menu__wdNMp"))
    )
    detail_containers = driver.find_elements(By.CSS_SELECTOR, "div.textMenuPc_text_menu_pc__7l6HC.textMenuPc_second_menu__wdNMp")
    if len(detail_containers) >= 2:
        second_container = detail_containers[1]
        print(">> [DEBUG] 두 번째 detail 메뉴 영역 발견")
        second_buttons = second_container.find_elements(By.CSS_SELECTOR, "button.textMenuPc_menu_button__aUoDb")
        menu_texts = []
        for btn in second_buttons:
            try:
                txt = btn.text.strip()
                if txt and txt != "전체" and "선택됨" not in txt:
                    menu_texts.append(txt)
                    print(f">> [DEBUG] 두 번째 detail 메뉴 항목: '{txt}'")
                elif "전체" in txt and "선택됨" in txt:
                    menu_texts.append(txt)
                    print(f">> [DEBUG] 두 번째 detail 메뉴 항목: '{txt}'")
            except Exception:
                continue
        return menu_texts
    else:
        print(">> [DEBUG] 두 번째 detail 메뉴 영역이 나타나지 않았습니다.")
        return []

def click_second_detail_menu(driver, menu_text):
    """
    두 번째 detail 메뉴에서 지정된 텍스트 항목을 클릭합니다.
    """
    WebDriverWait(driver, 20).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, "div.textMenuPc_text_menu_pc__7l6HC.textMenuPc_second_menu__wdNMp"))
    )
    detail_containers = driver.find_elements(By.CSS_SELECTOR, "div.textMenuPc_text_menu_pc__7l6HC.textMenuPc_second_menu__wdNMp")
    if len(detail_containers) < 2:
        raise Exception("두 번째 detail 메뉴 영역을 찾지 못했습니다.")
    second_container = detail_containers[1]
    second_buttons = second_container.find_elements(By.CSS_SELECTOR, "button.textMenuPc_menu_button__aUoDb")
    target_button = None
    for btn in second_buttons:
        try:
            txt = btn.text.strip()
            if menu_text in txt:  # 부분 일치 허용
                target_button = btn
                break
        except Exception:
            continue
    if not target_button:
        raise Exception(f"두 번째 detail 메뉴에서 '{menu_text}' 항목을 찾지 못했습니다.")
    safe_click(driver, target_button, f"두 번째 detail 메뉴 '{menu_text}'")
    time.sleep(2)
