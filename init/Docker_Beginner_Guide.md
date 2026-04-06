# Hướng dẫn Chạy PostgreSQL Schema với Docker & TablePlus

Để dễ dàng thiết lập và chạy cơ sở dữ liệu cho dự án trên máy móc cá nhân, cách tốt nhất là sử dụng Docker (để khởi tạo nhanh PostgreSQL) và TablePlus (để trực quan kết nối và gửi lệnh SQL).

## Bước 1: Khởi chạy PostgreSQL với Docker Compose

### 1.1 Khởi tạo tệp `docker-compose.yml`
Tại thư mục dự án của bạn (`d:\PROJECTS\Databases\DBMS\`), file `docker-compose.yml` nên được cấu hình tự động mapping data sau:

```yaml
services:
  db:
    image: postgres:15-alpine
    container_name: my-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: hieu1205  # Mật khẩu
      POSTGRES_DB: mydb
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
      # Dòng dưới này tự động nạp file schema.sql để khởi tạo table
      - ./schema.sql:/docker-entrypoint-initdb.d/init.sql
    restart: always

volumes:
  pgdata:
```

### 1.2 Chạy Docker Container
Mở công cụ dòng lệnh (Terminal/Command Prompt/PowerShell) ở cùng cấp thư mục chứa file nói trên, và gõ lệnh:

```bash
docker-compose up -d
```
> [!NOTE]
> Giải thích: Cờ `-d` chạy khối DB ở chế độ nền (background). Nếu tệp `schema.sql` đang nằm cùng thư mục, Docker sẽ **tự lấy nội dung script bạn viết vào** và tự động thực thi nó trong lúc init Database. Tức là CSDL của bạn có sẵn bảng luôn rồi. (Nếu bạn bật container lên trước khi mapping init.sql, vui lòng xoá volume pgdata đi và build lại container).

## Bước 2: Kết nối Database bằng TablePlus

TablePlus là một Client GUI Database rất tối ưu.

1. Khởi động ứng dụng **TablePlus**.
2. Bấm vào nút `+ Create a new connection...` (hoặc biểu tượng **+**).
3. Chọn loại Database: Nhấp chọn biểu tượng hình con voi xanh **PostgreSQL** cuối trang.

### Cấu hình thiết lập thông tin (Connection Form)

Hãy điền thông tin sau vào ô trống tương ứng:

- **Name**: `Local Postgres` (Đặt tên gợi nhớ trên giao diện)
- **Host**: `localhost` (Hoặc `127.0.0.1`)
- **Port**: `5432`
- **User**: `postgres` (Khớp với POSTGRES_USER trong yml)
- **Password**: `hieu1205` (Khớp với POSTGRES_PASSWORD con yml)
- **Database**: `mydb` (Khớp với tên CSDL bạn chỉ định)

Nhấp nút `Test` (để kiểm tra xem đèn có báo xanh ko).
Nếu xanh, nhấp nút `Connect` (hoặc `Save` để lưu lại lần sau dùng).

## Bước 3: Đảm bảo Schema hoạt động trên TablePlus (Chạy SQL thủ công)

Nếu việc Init (Tự động nạp `init.sql` ở **Bước 1**) thành công, bạn sẽ thấy cột bên trái trên TablePlus của bạn hiển thị các bảng: `users`, `students`, `teachers`,...

> [!CAUTION]
> Nếu trong trường hợp bạn quên không gán hoặc chạy lỗi **Volumes init.sql** ở **bước 1**, ở trong thư mục làm việc, DB của bạn trống không. Thì đây là cách nạp bằng tay:

1. Trong TablePlus (lúc bạn đã Connect vào db thành công).
2. Nhấn nút biểu tượng mã SQL `[ SQL ]` trên thanh công cụ trên nắp của Window (Phím tắt: `Ctrl + E` trên Win hoặc `Cmd + E` trên Mac).
3. Copy nhúng nội dung từ tệp `schema.sql` (hoặc mở thẻ File > Open file > Trỏ tới schema.sql) dán toàn bộ vào vùng soạn thảo màu đen mới mở ra.
4. Nhấn phím `Run All` ở góc hoặc tổ hợp phím tắt: (`Ctrl + Enter`) để gửi toàn bộ câu lệnh sang Server PostgreSQL.

Sau khi hoàn thành không có báo màu đỏ nào, nhấn nút Reload ở panel (`Cmd + R` hoặc `F5`), bạn sẽ thấy dánh sách của toàn bộ hàng chục table đã được tạo mới. PostgreSQL server của bạn đã sẵn sàng sử dụng.
