import pandas as pd
import psycopg2
from typing import Dict, List

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "DE",
    "user": "postgres",
    "password": "9090"
}

PATH_PRODUCTS = "/home/astep/DemoExamenShoes/import/Tovar.xlsx"
PATH_USERS = "/home/astep/DemoExamenShoes/import/user_import.xlsx"
PATH_ORDERS = "/home/astep/DemoExamenShoes/import/Заказ_import.xlsx"
PATH_POINTS = "/home/astep/DemoExamenShoes/import/Пункты выдачи_import.xlsx"


def import_pickup_points(cur, path):
    """
    Импортирует пункты выдачи в БД.
    Возвращает словарь: {индекс_из_файла: pickup_point_id}
    """
    points_df = pd.read_excel(path)
    pickup_point_map = {}
    
    for index, row in points_df.iterrows():
        address = str(row.iloc[0]).strip()
        if not address:
            continue
        
        # Вставляем адрес или получаем существующий ID
        cur.execute("""
            INSERT INTO public.pickup_points (address)
            VALUES (%s)
            ON CONFLICT (address) DO UPDATE SET address = EXCLUDED.address
            RETURNING pickup_point_id;
        """, (address,))
        
        pickup_point_id = cur.fetchone()[0]
        # Сохраняем соответствие: индекс (начиная с 1) → ID
        pickup_point_map[index + 1] = pickup_point_id
    
    print(f"✅ Импортировано пунктов выдачи: {len(pickup_point_map)}")
    return pickup_point_map


def import_users(cur, path: str) -> int:
    """Импортирует пользователей в БД."""
    users = pd.read_excel(path)
    
    for _, row in users.iterrows():
        cur.execute("""
            INSERT INTO public.users (role, full_name, login, user_password)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (login) DO NOTHING;
        """, (
            row["Роль сотрудника"],
            row["ФИО"],
            row["Логин"],
            row["Пароль"]
        ))
    
    print(f"✅ Импортировано пользователей: {len(users)}")
    return len(users)


def import_products(cur, path: str) -> int:
    """Импортирует товары в БД."""
    products = pd.read_excel(path)
    
    for _, row in products.iterrows():
        photo_path = row["Фото"] if pd.notna(row.get("Фото")) and row["Фото"] != "" else "picture.png"
        
        cur.execute("""
            INSERT INTO public.products (
                article, product_name, unit, price, supplier, manufacturer,
                category, discount, stock_quantity, description, photo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """, (
            row["Артикул"],
            row["Наименование товара"],
            row["Единица измерения"],
            float(row["Цена"]),
            row["Поставщик"],
            row["Производитель"],
            row["Категория товара"],
            float(row["Действующая скидка"]),
            int(row["Кол-во на складе"]),
            row["Описание товара"],
            photo_path
        ))
    
    print(f"✅ Импортировано товаров: {len(products)}")
    return len(products)


def import_orders(cur, path: str, pickup_point_map: Dict[int, int]) -> tuple:
    """
    Импортирует заказы и элементы заказов в БД.
    Возвращает кортеж: (количество_заказов, количество_позиций)
    """
    orders = pd.read_excel(path)
    imported_orders = 0
    imported_items = 0
    
    for _, row in orders.iterrows():
        order_date = pd.to_datetime(row["Дата заказа"], errors="coerce")
        delivery_date = pd.to_datetime(row["Дата доставки"], errors="coerce")
        
        # Пропускаем строки с некорректными датами
        if pd.isna(order_date):
            print(f"⏩ Пропуск заказа: неверная дата ({row['Дата заказа']})")
            continue
        
        # Получаем ID пункта выдачи по индексу
        pickup_index = int(row["Адрес пункта выдачи"])
        pickup_point_id = pickup_point_map.get(pickup_index)
        
        if pickup_point_id is None:
            print(f"⚠️ Предупреждение: пункт выдачи с индексом {pickup_index} не найден")
            continue
        
        # Ищем пользователя
        user_name = str(row["ФИО авторизированного клиента"]).strip()
        cur.execute("SELECT user_id FROM public.users WHERE full_name=%s;", (user_name,))
        user = cur.fetchone()
        user_id = user[0] if user else None
        
        # Вставляем заказ
        cur.execute("""
            INSERT INTO public.orders (
                order_date, delivery_date, pickup_point_id, 
                user_id, pickup_code, status
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING order_id;
        """, (
            order_date.date(),
            delivery_date.date() if not pd.isna(delivery_date) else None,
            pickup_point_id,
            user_id,
            int(row["Код для получения"]),
            str(row["Статус заказа"]).strip()
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
            
            if product is None:
                print(f"⚠️ Товар с артикулом {article} не найден")
                continue
            
            cur.execute("""
                INSERT INTO public.order_items (order_id, product_id, quantity)
                VALUES (%s, %s, %s);
            """, (order_id, product[0], quantity))
            imported_items += 1
    
    return imported_orders, imported_items


def main():
    """Основная функция импорта данных."""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        print("🚀 Начинаем импорт данных...\n")
        
        # 1. Импорт пунктов выдачи (первым делом!)
        pickup_point_map = import_pickup_points(cur, PATH_POINTS)
        
        # 2. Импорт пользователей
        import_users(cur, PATH_USERS)
        
        # 3. Импорт товаров
        import_products(cur, PATH_PRODUCTS)
        
        # 4. Импорт заказов и элементов заказов
        imported_orders, imported_items = import_orders(cur, PATH_ORDERS, pickup_point_map)
        
        # Фиксируем транзакцию
        conn.commit()
        
        print(f"\n{'='*50}")
        print(f"🎉 Импорт завершён успешно!")
        print(f"{'='*50}")
        print(f"📦 Пунктов выдачи: {len(pickup_point_map)}")
        print(f"📦 Заказов: {imported_orders}")
        print(f"📦 Позиций в заказах: {imported_items}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Ошибка при импорте: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
