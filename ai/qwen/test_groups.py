import os, time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
import json

base_dir = os.path.dirname(os.path.abspath(__file__))
chrome_driver_path = r"C:\hustmedia4\startproject\chromedrive\chromedriver.exe"
raw = r"C:\Users\Administrator\AppData\Local\Google\Chrome\User Data"
profile_dir = "Profile 2"
# cấu hình headless
# Không cần escape space, dùng raw string là đủ
opts = Options()
opts.add_argument(f"--user-data-dir={raw}")
opts.add_argument(f"--profile-directory={profile_dir}")
opts.add_argument("--start-maximized")
# thêm các flag ổn định
# opts.add_argument("--disable-gpu")
opts.add_argument("--no-sandbox")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--force-device-scale-factor=1")
opts.add_argument("--high-dpi-support=1")
opts.add_argument("--window-position=0,0")
opts.add_argument("--window-size=1500,900")

# Khởi động driver
driver = webdriver.Chrome(
        service=Service(chrome_driver_path),
        options=opts
    )
driver.get("https://www.facebook.com/groups/545078256871565")

time.sleep(5)  # chờ login

# 👉 Scroll để load thêm post
for i in range(3):   # số lần scroll, tăng nếu muốn nhiều bài hơn
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(5)  # chờ nội dung load

# Lấy 5 bài viết đầu tiên
posts = driver.find_elements(By.XPATH, '//div[@data-focus="feed_story"]')[:5]

data = []
for idx, post in enumerate(posts, 1):
    full_text = post.get_attribute("textContent")  # raw text bên trong element
    # Nếu muốn giữ nguyên HTML thay vì text thì dùng:
    # full_html = post.get_attribute("innerHTML")

    data.append({
        "id": idx,
        "full_text": full_text,   # không replace, không phân tích
        # "full_html": full_html  # nếu cần HTML
    })

print(json.dumps(data, ensure_ascii=False, indent=2))
driver.quit()