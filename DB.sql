-- ==========================
--   Таблица пользователей
-- ==========================
CREATE TABLE public.users (
    user_id SERIAL PRIMARY KEY,
    full_name CHARACTER VARYING(255) NOT NULL,
    login CHARACTER VARYING(255) UNIQUE NOT NULL,
    user_password CHARACTER VARYING(255) NOT NULL,
    role CHARACTER VARYING(100)
);

-- ==========================
--   Таблица товаров
-- ==========================
CREATE TABLE public.products (
    id SERIAL PRIMARY KEY,
    article CHARACTER VARYING(50),
    product_name CHARACTER VARYING(255) NOT NULL,
    unit CHARACTER VARYING(20),
    price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
    supplier CHARACTER VARYING(50),
    manufacturer CHARACTER VARYING(50),
    category CHARACTER VARYING(50),
    discount NUMERIC(5,2) DEFAULT 0 CHECK (discount >= 0),
    stock_quantity INTEGER DEFAULT 0 CHECK (stock_quantity >= 0),
    description TEXT,
    photo CHARACTER VARYING(255)
);

-- ==========================
--   Таблица заказов
-- ==========================
CREATE TABLE public.orders (
    order_id SERIAL PRIMARY KEY,
    order_date DATE NOT NULL,
    delivery_date DATE,
    pickup_point CHARACTER VARYING(500),  -- адрес пункта выдачи
    user_id INTEGER,
    pickup_code INTEGER,
    status CHARACTER VARYING(50)
);

-- ==========================
--   Таблица элементов заказа
-- ==========================
CREATE TABLE public.order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0)
);

-- ========================================
--   Установка внешних ключей отдельными командами
-- ========================================

-- Связь: orders → users
ALTER TABLE public.orders
ADD CONSTRAINT fk_orders_user
FOREIGN KEY (user_id)
REFERENCES public.users(user_id)
ON DELETE SET NULL;

-- Связь: order_items → orders
ALTER TABLE public.order_items
ADD CONSTRAINT fk_order_items_order
FOREIGN KEY (order_id)
REFERENCES public.orders(order_id)
ON DELETE CASCADE;

-- Связь: order_items → products
ALTER TABLE public.order_items
ADD CONSTRAINT fk_order_items_product
FOREIGN KEY (product_id)
REFERENCES public.products(id)
ON DELETE RESTRICT;
