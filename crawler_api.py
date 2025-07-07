from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
import os
import unicodedata
import sys

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.set_page_load_timeout(30)
    return driver


def wait_for_element(driver, by_method, selector, timeout=20):
    """Chờ element xuất hiện trên trang."""
    return WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located((by_method, selector))
    )


def get_table_data(soup, selector):
    """Trích xuất dữ liệu từ bảng HTML."""
    rows = soup.select(selector)
    data = []
    for tr in rows:
        tds = tr.find_all("td")
        row = [td.find("span").get_text(strip=True) if td.find("span") else "" for td in tds]
        if row:  # loại bỏ dòng rỗng
            data.append(row)
    return data


def get_table_headers(driver, header_id):
    """Lấy tiêu đề các cột của bảng."""
    header_table = driver.find_element(By.ID, header_id)
    header_html = header_table.get_attribute("outerHTML")
    header_soup = BeautifulSoup(header_html, "html.parser")
    
    header_tr = header_soup.select_one("tbody > tr:nth-of-type(2)")
    header_ths = header_tr.find_all("th")
    return [th.get_text(strip=True) for th in header_ths]


def click_tab(driver, tab_id):
    """Click vào tab theo ID."""
    tab = driver.find_element(By.ID, tab_id)
    driver.execute_script("arguments[0].scrollIntoView(true);", tab)
    time.sleep(1)  # để ổn định
    driver.execute_script("arguments[0].click();", tab)
    time.sleep(2)  # đảm bảo render xong


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize('NFD', text)
    return ''.join(ch for ch in nfkd if unicodedata.category(ch) != 'Mn')

def extract_quarter_year(report_name: str) -> str:
    """
    - Báo cáo bán niên YYYY  → H1.YYYY
    - Báo cáo năm YYYY      → YYYYY
    - Quý N[/ ]YYYY         → QN.YYYY
    fallback “unknown” nếu không tìm thấy số năm/quý
    """
    name = strip_accents(report_name)

    # 1) Bán niên YYYY
    m = re.search(r'ban nien\s*(\d{4})', name, re.IGNORECASE)
    if m:
        return f"H1.{m.group(1)}"

    # 2) Báo cáo tài chính năm YYYY
    m = re.search(r'\bnam\s*(\d{4})', name, re.IGNORECASE)
    if m:
        return f"Y{m.group(1)}"

    # 3) Quý N[/ ]YYYY hoặc Quý N năm YYYY
    for pattern in (r'\bquy\s*(\d+)[/ ]*(\d{4})',
                    r'\bquy\s*(\d+)[/ ]*nam\s*(\d{4})'):
        m = re.search(pattern, name, re.IGNORECASE)
        if m:
            return f"Q{m.group(1)}.{m.group(2)}"

    # 4) Chưa rõ năm/quý → fallback
    return "unknown"


def extract_quarter_year_from_detail(driver):
    """Trích xuất thông tin quý và năm từ chi tiết báo cáo, bỏ qua mọi dấu và không phụ thuộc ID cố định."""
    def strip_accents(text: str) -> str:
        # chuyển về NFD rồi loại bỏ các ký tự dấu (Mn)
        nfkd = unicodedata.normalize('NFD', text)
        return ''.join(ch for ch in nfkd if unicodedata.category(ch) != 'Mn')
    
    try:
        div_html = driver.find_element(By.ID, "pt2:tt1::db").get_attribute("outerHTML")
        soup = BeautifulSoup(div_html, "html.parser")

        year = None
        quarter = None

        # duyệt qua từng <tr> trong bảng
        for tr in soup.select("tr"):
            tds = tr.find_all("td")
            if len(tds) < 3:
                continue

            raw_label = tds[0].get_text(strip=True)
            raw_value = tds[2].get_text(strip=True)

            # chuẩn hóa (bỏ dấu, lowercase)
            label = strip_accents(raw_label).lower()
            value = raw_value.strip()

            # nếu nhãn chứa "nam" và chưa tìm thấy năm
            if "nam" in label and not year:
                m = re.search(r"\d{4}", value)
                if m:
                    year = m.group()

            # nếu nhãn chứa "quy" và chưa tìm thấy quý
            if "quy" in label and not quarter:
                m = re.search(r"\d+", value)
                if m:
                    quarter = m.group()

            # nếu đã có cả 2 thì dừng sớm
            if year and quarter:
                break

        if year and quarter:
            return f"Q{quarter}.{year}"
        if year:
            return f"Y{year}"
        return "unknown"

    except Exception as e:
        print(f"Lỗi khi trích xuất quý/năm: {e}")
        return "unknown"


def should_skip_based_on_h1(driver):
    """Kiểm tra xem có nên bỏ qua báo cáo này dựa trên nội dung thẻ h1 trong div pt2:pb2."""
    try:
        # Tìm div với id pt2:pb2
        div_element = driver.find_element(By.ID, "pt2:pb2")
        
        # Tìm thẻ h1 trong div đó
        h1_elements = div_element.find_elements(By.TAG_NAME, "h1")
        
        if h1_elements:
            h1_text = h1_elements[0].text.strip()
            
            # Danh sách từ khóa loại trừ
            exclude_keywords = ["Mẹ", "mẹ", "Riêng"]
            
            # Kiểm tra nếu h1 chứa bất kỳ từ khóa nào cần loại trừ
            for keyword in exclude_keywords:
                if keyword in h1_text:
                    print(f"⏭️ Bỏ qua báo cáo vì h1 có chứa từ khóa '{keyword}': '{h1_text}'")
                    return True
        
        return False
    except Exception as e:
        print(f"Lỗi khi kiểm tra h1: {e}")
        # Nếu có lỗi, không bỏ qua báo cáo
        return False


def process_table_data(driver, header_id, data_id, tab_name):
    """Lấy và xử lý dữ liệu của một bảng."""
    try:
        # Lấy headers
        headers = get_table_headers(driver, header_id)
        print(f"\n🧾 Tên các cột {tab_name}:", headers)
        
        # Lấy dữ liệu bảng
        data_div = driver.find_element(By.ID, data_id)
        data_html = data_div.get_attribute("outerHTML")
        data_soup = BeautifulSoup(data_html, "html.parser")
        
        data = get_table_data(data_soup, "tbody > tr")
        
        # Tạo DataFrame
        return pd.DataFrame(data, columns=headers)
    except Exception as e:
        print(f"Lỗi khi xử lý bảng {tab_name}: {e}")
        return pd.DataFrame()  # Trả về DataFrame rỗng nếu có lỗi


def process_report_detail(driver, report_index, report_name, quarter_year, stock_code):
    """Xử lý chi tiết báo cáo và lấy dữ liệu từ các tab."""
    print(f"\n\n=== Đang xử lý báo cáo {report_index + 1}: {report_name} ===")
    
    try:
        # Chờ trang chi tiết
        wait_for_element(driver, By.ID, "pt2:pt1::tabbc")
        time.sleep(2)
        
        # Kiểm tra h1 trong div pt2:pb2
        if should_skip_based_on_h1(driver):
            print(f"❌ Bỏ qua báo cáo {report_name} dựa trên nội dung h1")
            return False
        
        # Nếu không tìm thấy thông tin quý/năm từ tên báo cáo, thử trích xuất từ chi tiết
        if quarter_year == "unknown":
            quarter_year = extract_quarter_year_from_detail(driver)
            print(f"Thông tin quý/năm từ chi tiết báo cáo: {quarter_year}")
        
        # Lấy mã định danh làm tiền tố tên file
        mdn_value = driver.find_element(By.CSS_SELECTOR, "td.xth.xtk").text.strip()
        id_mack = re.sub(r'[\\/*?:"<>|]', "_", mdn_value)
        
        # Tạo thư mục để lưu dữ liệu của mã chứng khoán này theo quý
        if quarter_year == "unknown":
            # Nếu không tìm thấy thông tin quý, sử dụng thư mục mặc định
            report_dir = f"data/{stock_code}"
        else:
            # Nếu tìm thấy thông tin quý, tạo thư mục theo quý
            report_dir = f"{quarter_year}/{stock_code}"
        
        os.makedirs(report_dir, exist_ok=True)
        
        # Xử lý bảng CDKT (bảng mặc định)
        df_cdkt = process_table_data(driver, "pt2:t2::ch::t", "pt2:t2::db", "CDKT")
        if not df_cdkt.empty:
            df_cdkt.to_csv(f"{report_dir}/{id_mack}_baocao_cdkt.csv", index=False, encoding='utf-8-sig')
            print(f"✅ Đã lưu dữ liệu CDKT vào {report_dir}")
        
        # Xử lý bảng KQKD
        click_tab(driver, "pt2:KQKD::disAcr")
        df_kqkd = process_table_data(driver, "pt2:t3::ch::t", "pt2:t3::db", "KQKD")
        if not df_kqkd.empty:
            df_kqkd.to_csv(f"{report_dir}/{id_mack}_baocao_kqkd.csv", index=False, encoding='utf-8-sig')
            print(f"✅ Đã lưu dữ liệu KQKD vào {report_dir}")
        
        # Xử lý bảng LCTT-TT
        click_tab(driver, "pt2:LCTT-TT::disAcr")
        df_lctt_tt = process_table_data(driver, "pt2:t5::ch::t", "pt2:t5::db", "LCTT-TT")
        if not df_lctt_tt.empty:
            df_lctt_tt.to_csv(f"{report_dir}/{id_mack}_baocao_lctt_tt.csv", index=False, encoding='utf-8-sig')
            print(f"✅ Đã lưu dữ liệu LCTT-TT vào {report_dir}")
        
        # Xử lý bảng LCTT-GT
        click_tab(driver, "pt2:LCTT-GT::disAcr")
        df_lctt_gt = process_table_data(driver, "pt2:t6::ch::t", "pt2:t6::db", "LCTT-GT")
        if not df_lctt_gt.empty:
            df_lctt_gt.to_csv(f"{report_dir}/{id_mack}_baocao_lctt_gt.csv", index=False, encoding='utf-8-sig')
            print(f"✅ Đã lưu dữ liệu LCTT-GT vào {report_dir}")
        
        return True
    except Exception as e:
        print(f"Lỗi khi xử lý chi tiết báo cáo: {e}")
        return False


def should_skip_report(report_name):
    """Kiểm tra xem có nên bỏ qua báo cáo này không dựa trên tên."""
    # Danh sách từ khóa loại trừ
    exclude_keywords = ["Mẹ", "mẹ", "Riêng"]
    
    # Kiểm tra nếu tên báo cáo chứa bất kỳ từ khóa nào cần loại trừ
    for keyword in exclude_keywords:
        if keyword in report_name:
            return True
    
    return False


def get_report_links(driver):
    """
    Lấy tất cả các báo cáo trên page hiện tại bằng cách query
    trực tiếp các <a> chứa ID kết thúc bằng ':cl1', bỏ qua ones bị lọc.
    Trả về list các tuple (global_index, link_id, report_name, quarter_year).
    """
    reports = []
    skipped = 0

    # 1) Tìm table chứa danh sách
    table = wait_for_element(driver, By.ID, "pt9:t1::db")
    # 2) Lấy tất cả <a> có id kết thúc bằng ':cl1'
    link_els = table.find_elements(By.CSS_SELECTOR, "a[id$=':cl1']")
    
    for el in link_els:
        link_id = el.get_attribute("id")
        report_name = el.text.strip()
        
        # Kiểm skip theo keyword
        if should_skip_report(report_name):
            skipped += 1
            print(f"⏭️ Bỏ qua '{report_name}'")
            continue
        
        # Trích quý/năm
        quarter_year = extract_quarter_year(report_name)
        # Lấy index toàn cục từ ID: pt9:t1:<idx>:cl1
        idx = int(link_id.split(":")[2])
        
        reports.append((idx, link_id, report_name, quarter_year))
        print(f"✅ ID={idx}, {report_name} → {quarter_year}")

    print(f"Đã bỏ qua {skipped} báo cáo theo từ khóa lọc")
    return reports


def main(stock_code="PVS"):
    driver = setup_driver()
    try:
        # 1. Mở trang và search
        driver.get("https://congbothongtin.ssc.gov.vn/faces/NewsSearch")
        wait_for_element(driver, By.ID, "pt9:it8112::content").send_keys(stock_code)
        driver.find_element(By.XPATH, "//span[text()='Tìm kiếm']/ancestor::a")\
              .click()
        wait_for_element(driver, By.ID, "pt9:t1::db")
        time.sleep(2)

        # 2. Lấy tổng số báo cáo
        initial_reports = get_report_links(driver)
        total = len(initial_reports)

        # 3. Duyệt theo index
        for i in range(total):
            # mỗi vòng lặp re-fetch link list để có ID mới
            reports = get_report_links(driver)
            idx, link_id, report_name, quarter_year = reports[i]

            # click vào báo cáo thứ i
            el = driver.find_element(By.ID, link_id)
            driver.execute_script("arguments[0].scrollIntoView(true);", el)
            time.sleep(0.5)
            el.click()

            # xử lý detail như bình thường
            process_report_detail(driver, idx, report_name, quarter_year, stock_code)

            # quay lại kết quả tìm kiếm
            driver.back()
            wait_for_element(driver, By.ID, "pt9:t1::db")
            time.sleep(1)

    finally:
        driver.quit()



if __name__ == "__main__":
    if len(sys.argv) >= 2:
        stock = sys.argv[1]
    else:
        stock = "PVS"

    main(stock)