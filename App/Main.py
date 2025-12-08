import sys
import os
import psycopg2
from PyQt5 import QtWidgets, uic, QtGui, QtCore

PATH_LOGIN_UI = "/home/astep/DemoExamenShoes/UI/login.ui"
PATH_MAIN_UI = "/home/astep/DemoExamenShoes/UI/main.ui"
PATH_PRODUCT_ITEM_UI = "/home/astep/DemoExamenShoes/UI/product_item.ui"
PATH_PHOTOS = "/home/astep/DemoExamenShoes/import"

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "DE",
    "user": "postgres",
    "password": "9090"
}

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


# =====================================================
#  ЛОГИН ОКНО
# =====================================================
class LoginDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi(PATH_LOGIN_UI, self)

        self.btn_login.clicked.connect(self.try_login)
        self.btn_guest.clicked.connect(self.continue_as_guest)
        self.lineEdit_password.returnPressed.connect(self.try_login)

    def try_login(self):
        login = self.lineEdit_login.text().strip()
        password = self.lineEdit_password.text().strip()

        if not login or not password:
            self.label_message.setText("Введите логин и пароль")
            return

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT user_id, full_name, role
                FROM public.users
                WHERE login=%s AND user_password=%s;
            """, (login, password))

            row = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as e:
            self.label_message.setText(f"Ошибка БД: {e}")
            return

        if row:
            user_id, full_name, role = row
            self.open_main(full_name, role)
        else:
            self.label_message.setText("Неверный логин или пароль")

    def continue_as_guest(self):
        self.open_main("Гость", "guest")

    def open_main(self, full_name, role):
        self.accept()
        self.main_win = MainWindow(full_name=full_name, role=role)
        self.main_win.show()


# =====================================================
#  ГЛАВНОЕ ОКНО
# =====================================================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, full_name: str, role: str):
        super().__init__()
        uic.loadUi(PATH_MAIN_UI, self)

        self.full_name = full_name
        self.role = role.lower()

        self.label_user.setText(self.full_name)
        self.btn_logout.clicked.connect(self.logout)

        self.set_role_page()
        self.load_products()

    # ---------------------------------------------------
    def set_role_page(self):
        r = self.role
        if r in ("guest", "гость"):
            idx = 0
        elif "клиент" in r:
            idx = 1
        elif "менеджер" in r:
            idx = 2
        elif "администратор" in r or "admin" in r:
            idx = 3
        else:
            idx = 0

        self.stackedWidget.setCurrentIndex(idx)

    # ---------------------------------------------------
    def load_products(self):
        """Загрузка карточек товаров в layout_products"""

        try:
            conn = get_db_connection()
            cur = conn.cursor()

            cur.execute("""
                SELECT id, product_name, price, manufacturer, photo, category, discount, unit, supplier, description
                FROM public.products;
            """)

            rows = cur.fetchall()
            cur.close()
            conn.close()

        except Exception as e:
            print("Ошибка загрузки:", e)
            return

        layout: QtWidgets.QVBoxLayout = self.layout_products

        # Очистка старых карточек
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Создание карточек
        for pid, name, price, manufacturer, photo, category, discount, unit, supplier, description in rows:
            widget = uic.loadUi(PATH_PRODUCT_ITEM_UI)

            widget.name.setText(name)
            widget.price.setText(f"{price} ₽")
            widget.manufacturer.setText(manufacturer)
            widget.category.setText(category)
            widget.discount.setText(str(discount))
            #TODO СДЕЛАТЬ СКИДКУ РАЗНЫХ ЦВЕТОВ
            widget.unit.setText(unit)
            widget.supplier.setText(supplier)
            widget.description.setText(description)
            # Загрузка фото
            if photo:
                full_path = os.path.join(PATH_PHOTOS, photo)
                if os.path.exists(full_path):
                    pix = QtGui.QPixmap(full_path)
                    widget.photo.setPixmap(
                        pix.scaled(150, 150, QtCore.Qt.KeepAspectRatio)
                    )
                else:
                    widget.photo.setText("Нет фото")
            else:
                widget.photo.setText("Нет фото")

            layout.addWidget(widget)

        layout.addStretch()

    # ---------------------------------------------------
    def logout(self):
        self.close()
        login = LoginDialog()
        login.show()


# =====================================================
#  ЗАПУСК
# =====================================================
def main():
    app = QtWidgets.QApplication(sys.argv)

    dlg = LoginDialog()
    dlg.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
