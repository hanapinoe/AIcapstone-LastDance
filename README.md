# Alcapstone-LastDance

## Mô tả
Dự án này là hệ thống gợi ý món ăn dựa trên AI, bao gồm backend (FastAPI) và frontend (Python). Hệ thống sử dụng cơ sở dữ liệu, mô hình AI và các dịch vụ để cung cấp gợi ý món ăn cá nhân hóa cho người dùng.

## Cấu trúc dự án
```
Backend/
    app/
        controllers/
        models/
        repositories/
        routes/
        services/
        utils/
        data/
        test/
    requirements.txt
Frontend/
    mainFE.py
    input_query.py
    login.py
    logout.py
    resigter.py
    result_recommedation.py
    welcome.py
```

## Hướng dẫn cài đặt

### 1. Clone repository
```bash
git clone https://github.com/hanapinoe/Alcapstone-LastDance.git
cd Alcapstone-LastDance
```

### 2. Cài đặt backend
```bash
cd Backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. Thiết lập biến môi trường
Tạo file `.env` trong thư mục `Backend/app/` với nội dung ví dụ:
```
VECTOR_DB_PATH=path/to/vector_db
RAG_TOP_K=5
RAG_MAX_TRY=10
RAG_SEED=42
```

### 4. Chạy backend
```bash
uvicorn app.controllers.APIhandler:app --reload
```

### 5. Chạy frontend
```bash
cd ../Frontend
python mainFE.py
```

## Tính năng chính
- Đăng ký, đăng nhập người dùng
- Gợi ý món ăn dựa trên truy vấn và sở thích người dùng
- Lưu lịch sử gợi ý
- Tích hợp mô hình AI và vector database

## Đóng góp
Mọi đóng góp đều được hoan nghênh! Vui lòng tạo pull request hoặc issue nếu bạn có ý tưởng hoặc phát hiện lỗi.

## License
[MIT](LICENSE) (hoặc license bạn chọn)