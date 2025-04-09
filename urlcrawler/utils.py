# urlcrawler/utils.py
import time
from selenium.webdriver.support.ui import WebDriverWait

def wait_until_clickable(driver, element, timeout=20, description=""):
    if element is None:
        raise Exception(f"{description} 요소가 None입니다. (wait_until_clickable)")
    try:
        WebDriverWait(driver, timeout).until(lambda d: element.is_displayed() and element.is_enabled())
        print(f">> [DEBUG] {description} 요소가 클릭 가능해짐")
        return True
    except Exception as e:
        print(f">> [DEBUG] {description} 요소 대기 실패: {e}")
        return False

def safe_click(driver, element, description=""):
    # 요소가 None인 경우 조기에 예외 처리합니다.
    if element is None:
        raise Exception(f"{description} 요소가 None입니다. safe_click 호출 불가")
    
    try:
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    except Exception as e:
        print(f">> [DEBUG] {description} 스크롤 실패: {e}")
    time.sleep(0.5)
    try:
        text = element.text.strip()
        displayed = element.is_displayed()
        enabled = element.is_enabled()
        outer_html = element.get_attribute("outerHTML")[:200]
        print(f">> [DEBUG] {description} safe_click 시도: 텍스트='{text}', displayed={displayed}, enabled={enabled}")
        print(">> [DEBUG] outerHTML 일부:", outer_html)
    except Exception as ex:
        print(f">> [DEBUG] {description} safe_click 디버깅 예외: {ex}")
    if not wait_until_clickable(driver, element, description=description):
        raise Exception(f"{description} 요소가 클릭 가능하지 않음")
    try:
        element.click()
        print(f">> [DEBUG] {description} 클릭 성공")
    except Exception as e:
        print(f">> [DEBUG] {description} 일반 클릭 실패, JS 클릭 시도: {e}")
        try:
            driver.execute_script("arguments[0].click();", element)
            print(f">> [DEBUG] {description} JS 클릭 성공")
        except Exception as e2:
            print(f">> [DEBUG] {description} JS 클릭 실패: {e2}")
            raise
    time.sleep(0.5)
