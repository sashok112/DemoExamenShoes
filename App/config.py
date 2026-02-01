# --- config ---
# Словарь путей к .ui‑файлам интерфейса Qt Designer
UI = {
    "login": "./UI/login.ui",
    "main": "./UI/main.ui",
    "card": "./UI/product_item.ui",
    "cart": "./UI/cart.ui",
    "prod": "./UI/product_form.ui",
    "order": "./UI/order_form.ui",
    "orders": "./UI/orders_list.ui",
}
# Папка с фотографиями товаров и картинка по умолчанию
PHOTOS, PH = "./import", "./resources/picture.png"
# Параметры подключения к базе данных PostgreSQL
DB = dict(host="localhost", port=5432, database="DE1", user="postgres", password="9090")