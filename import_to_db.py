import pandas as pd
import psycopg2
from datetime import datetime

# ==========================
# Настройки подключения к БД
# ==========================
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "DE",
    "user": "postgres",
    "password": "9090"
}

# ==========================
# Пути к файлам Excel
# ==========================
PATH_PRODUCTS = "/home/astep/Рабочий стол/DemoExamenShoes/import/Tovar.xlsx"
PATH_USERS = "/home/astep/Рабочий стол/DemoExamenShoes/import/user_import.xlsx"
PATH_ORDERS = "/home/astep/Рабочий стол/DemoExamenShoes/import/Заказ_import.xlsx"
PATH_POINTS = "/home/astep/Рабочий стол/DemoExamenShoes/import/Пункты выдачи_import.xlsx"

# ==========================
# Функции импорта
# ==========================

def import_pickup_points(cur):
    df = pd.read_excel(PATH_POINTS)
    col = df.columns[0]

    for _, row in df.iterrows():
        addr = str(row[col]).strip()
        if addr:
            cur.execute("INSERT INTO pickup_points (point_address) VALUES (%s);", (addr,))
    print("✅ Пункты выдачи импортированы")


def import_users(cur):
    df = pd.read_excel(PATH_USERS)
    for _, row in df.iterrows():
        cur.execute(
            "INSERT INTO users (role, full_name, login, user_password) VALUES (%s,%s,%s,%s);",
            (row["Роль сотрудника"], row["ФИО"], row["Логин"], row["Пароль"])
        )
    print("✅ Пользователи импортированы")


def import_products(cur):
    df = pd.read_excel(PATH_PRODUCTS)
    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO products (
                article, product_name, unit, price, supplier, manufacturer,
                category, discount, stock_quantity, description, photo
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
        """, (
            row["Артикул"], row["Наименование товара"], row["Единица измерения"],
            float(row["Цена"]), row["Поставщик"], row["Производитель"],
            row["Категория товара"], float(row["Действующая скидка"]),
            int(row["Кол-во на складе"]), row["Описание товара"], row.get("Фото")
        ))
    print("✅ Товары импортированы")


def import_orders(cur):
    df = pd.read_excel(PATH_ORDERS)
    for _, row in df.iterrows():
        # Даты
        order_date = pd.to_datetime(row["Дата заказа"], errors="coerce")
        delivery_date = pd.to_datetime(row["Дата доставки"], errors="coerce")
        if pd.isna(order_date):
            print(f"⏩ Пропуск заказа №{row['Номер заказа']} из-за неверной даты")
            continue

        order_date = order_date.date()
        delivery_date = delivery_date.date() if not pd.isna(delivery_date) else None

        # Получаем user_id
        cur.execute("SELECT user_id FROM users WHERE full_name=%s;", (row["ФИО авторизированного клиента"],))
        user = cur.fetchone()
        user_id = user[0] if user else None

        # Вставляем заказ
        cur.execute("""
            INSERT INTO orders (order_id, order_date, delivery_date, pickup_point_id, user_id, pickup_code, status)
            VALUES (%s,%s,%s,%s,%s,%s,%s);
        """, (
            int(row["Номер заказа"]),
            order_date,
            delivery_date,
            int(row["Адрес пункта выдачи"]),
            user_id,
            int(row["Код для получения"]),
            row["Статус заказа"]
        ))

        # Вставляем позиции заказа
        parts = [p.strip() for p in str(row["Артикул заказа"]).split(",") if p.strip()]
        for i in range(0, len(parts), 2):
            article = parts[i]
            quantity = int(parts[i+1]) if i+1 < len(parts) else 1

            cur.execute("SELECT id FROM products WHERE article=%s;", (article,))
            product = cur.fetchone()
            if product:
                cur.execute("INSERT INTO order_items (order_id, product_id, quantity) VALUES (%s,%s,%s);",
                            (int(row["Номер заказа"]), product[0], quantity))

    print("✅ Заказы и позиции импортированы")


# ==========================
# Основная функция
# ==========================
def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    try:
        import_pickup_points(cur)
        import_users(cur)
        import_products(cur)
        import_orders(cur)
        conn.commit()
        print("🎉 Импорт завершён успешно!")
    except Exception as e:
        conn.rollback()
        print("❌ Ошибка при импорте:", e)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
