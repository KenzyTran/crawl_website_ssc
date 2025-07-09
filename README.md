# Hướng dẫn triển khai dự án crawl_website_ssc trên Linux (Amazon Linux/CentOS)

## 1. Cài đặt Python và pip
```bash
sudo yum update -y
sudo yum install python3 python3-pip -y
```

## 2. Cài đặt Google Chrome (hoặc Chromium)
### Cài Google Chrome:
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_x86_64.rpm
sudo yum install ./google-chrome-stable_current_x86_64.rpm -y
```

### Hoặc cài Chromium (nếu Chrome lỗi):
```bash
sudo yum install chromium -y
```

## 3. Cài đặt các thư viện Python
```bash
cd crawl_website_ssc
pip3 install -r requirements.txt
```

## 4. Chạy FastAPI với Uvicorn dưới nền
### Dùng nohup:
```bash
nohup uvicorn main:app --host 0.0.0.0 --port 8000 > log.txt 2>&1 &
```

### Hoặc dùng screen:
```bash
screen -S fastapi
uvicorn main:app --host 0.0.0.0 --port 8000
# Thoát screen: Ctrl+A rồi D
# Quay lại: screen -r fastapi
```

## 5. (Tuỳ chọn) Mở firewall cho cổng 8000
```bash
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --reload
```

## 6. Gọi API
Truy cập:
```
http://<ip-server>:8000/crawl?stock=PVS&quarter=Q1.2024
```
Thay `stock` và `quarter` theo nhu cầu.

---

**Nếu gặp lỗi, hãy kiểm tra log (log.txt) hoặc gửi thông báo lỗi để được hỗ trợ.**
