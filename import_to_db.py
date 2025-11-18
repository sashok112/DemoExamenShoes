import pandas as pd
import psycopg2

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "DE",
    "user": "postgres",
    "password": "9090"
}

PATH_PRODUCTS = "/home/astep/Рабочий стол/DemoExamenShoes/import/Tovar.xlsx"
PATH_USERS = "/home/astep/Рабочий стол/DemoExamenShoes/import/user_import.xlsx"
PATH_ORDERS = "/home/astep/Рабочий стол/DemoExamenShoes/import/Заказ_import.xlsx"
PATH_POINTS = "/home/astep/Рабочий стол/DemoExamenShoes/import/Пункты выдачи_import.xlsx"

# ==========================
#   Основная функция импорта
# ==========================

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # ===== Импорт пунктов выдачи =====
        points_df = pd.read_excel(PATH_POINTS)
        pickup_points = []

        for _, row in points_df.iterrows():
            address = str(row.iloc[0]).strip()
            if not address:
                continue
            pickup_points.append(address)

        print(f"✅ Добавлено пунктов выдачи: {len(pickup_points)}")

        # ===== Импорт пользователей =====
        users = pd.read_excel(PATH_USERS)
        for _, row in users.iterrows():
            cur.execute("""
                INSERT INTO public.users (role, full_name, login, user_password)
                VALUES (%s, %s, %s, %s);
            """, (row["Роль сотрудника"], row["ФИО"], row["Логин"], row["Пароль"]))
        print(f"✅ Импортировано пользователей: {len(users)}")

        # ===== Импорт товаров =====
        products = pd.read_excel(PATH_PRODUCTS)
        for _, row in products.iterrows():
            photo_path = row["Фото"] if pd.notna(row.get("Фото")) and row["Фото"] != "" else "Icon.JPG"
            cur.execute("""
                INSERT INTO public.products (
                    article, product_name, unit, price, supplier, manufacturer,
                    category, discount, stock_quantity, description, photo
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);
            """, (
                row["Артикул"], row["Наименование товара"], row["Единица измерения"],
                float(row["Цена"]), row["Поставщик"], row["Производитель"],
                row["Категория товара"], float(row["Действующая скидка"]),
                int(row["Кол-во на складе"]), row["Описание товара"], photo_path
            ))
        print(f"✅ Импортировано товаров: {len(products)}")

        # ===== Импорт заказов =====
        orders = pd.read_excel(PATH_ORDERS)
        imported_orders = 0
        imported_items = 0

        for _, row in orders.iterrows():
            order_date = pd.to_datetime(row["Дата заказа"], errors="coerce")
            delivery_date = pd.to_datetime(row["Дата доставки"], errors="coerce")

            # Пропускаем строки с некорректными датами
            if pd.isna(order_date):
                print(f"⏩ Пропуск заказа: неверная дата ({row['Дата заказа']})")
                continue

            # Получаем адрес пункта по индексу (например, 1 → первый адрес в списке)
            pickup_index = int(row["Адрес пункта выдачи"]) - 1

            # Ищем пользователя
            user_name = str(row["ФИО авторизированного клиента"]).strip()
            cur.execute("SELECT user_id FROM public.users WHERE full_name=%s;", (user_name,))
            user = cur.fetchone()
            user_id = user[0] if user else None

            # Вставляем заказ
            cur.execute("""
                INSERT INTO public.orders (order_date, delivery_date, pickup_point, user_id, pickup_code, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING order_id;
            """, (
                order_date.date(),
                delivery_date.date() if not pd.isna(delivery_date) else None,
                pickup_points[pickup_index], user_id,
                int(row["Код для получения"]), str(row["Статус заказа"]).strip()
            ))
            order_id = cur.fetchone()[0]
            imported_orders += 1

            # Вставляем товары из заказа
            parts = [p.strip() for p in str(row["Артикул заказа"]).split(",") if p.strip()]
            for i in range(0, len(parts), 2):
                article = parts[i]
                quantity = int(parts[i + 1]) if i + 1 < len(parts) else 1

                cur.execute("SELECT id FROM public.products WHERE article=%s;", (article,))
                product = cur.fetchone()

                cur.execute("""
                    INSERT INTO public.order_items (order_id, product_id, quantity)
                    VALUES (%s, %s, %s);
                """, (order_id, product[0], quantity))
                imported_items += 1

        conn.commit()
        print(f"🎉 Импорт завершён успешно!\nЗаказов: {imported_orders}\nПозиций: {imported_items}")

    except Exception as e:
        conn.rollback()
        print("❌ Ошибка при импорте:", e)
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
