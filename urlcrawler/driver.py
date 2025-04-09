# urlcrawler/driver.py
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

def setup_driver():
    options = webdriver.ChromeOptions()
    # 필요에 따라 headless 모드를 활성화할 수 있습니다.
    # options.add_argument("--headless")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(5)
    print(">> [DEBUG] 웹드라이버 초기화 완료")
    return driver
