# app.py
import sys
import psycopg2
from PyQt5 import QtWidgets, uic
import pandas as pd


DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "DE",
    "user": "postgres",
    "password": "9090"
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


class LoginDialog(QtWidgets.QDialog):
    def __init__(self):
        super().__init__()
        uic.loadUi("login.ui", self)  # убедись, что файл в той же папке
        # ожидаемые имена виджетов из .ui:
        # lineEdit_login, lineEdit_password, btn_login, btn_guest, label_message

        self.btn_login.clicked.connect(self.try_login)
        self.btn_guest.clicked.connect(self.continue_as_guest)
        self.lineEdit_password.returnPressed.connect(self.try_login)
        self.db_conn = None

    def try_login(self):
        login = self.lineEdit_login.text().strip()
        password = self.lineEdit_password.text().strip()

        if not login or not password:
            self.statusBar.setText("Введите логин и пароль")
            return

        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(
                "SELECT user_id, full_name, role FROM public.users WHERE login=%s AND user_password=%s;",
                (login, password)
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as e:
            self.statusBar.setText(f"Ошибка БД: {e}")
            return

        if row:
            user_id, full_name, role = row
            # Открываем главный интерфейс и передаём информацию о пользователе
            self.open_main(full_name, role)
        else:
            self.statusBar.setText("Неверный логин или пароль")

    def continue_as_guest(self):
        # Открываем главное окно как гость
        self.open_main("Гость", "guest")

    def open_main(self, full_name, role):
        self.accept()  # Закрываем диалог с результатом accepted
        self.main_win = MainWindow(full_name=full_name, role=role)
        self.main_win.show()


# =====================
# Главное окно (main.ui)
# =====================
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, full_name: str, role: str):
        super().__init__()
        uic.loadUi("main.ui", self)  # ожидает label_user, btn_logout, stackedWidget
        # Сохраняем пользователя
        self.full_name = full_name
        self.role = role.lower()  # ожидаем guest, авторизированный клиент, менеджер, администратор

        # Настроим отображение ФИО в правом верхнем углу
        # label_user — QLabel в main.ui
        self.label_user.setText(self.full_name)

        # Подключаем кнопку выхода
        self.btn_logout.clicked.connect(self.logout)

        # Подберём индекс страницы по роли
        # согласуем: guest -> 0, client -> 1, manager -> 2, admin -> 3
        idx = 0
        if "гость" in self.role or self.role == "guest":
            idx = 0
        elif "клиент" in self.role or "author" in self.role or "client" in self.role or "auth" in self.role:
            idx = 1
        elif "менеджер" in self.role or "manager" in self.role:
            idx = 2
        elif "администратор" in self.role or "admin" in self.role:
            idx = 3
        else:
            # если роль хранится как "Авторизированный клиент" (по-русски) — корректируем:
            if "автор" in self.role and "клиент" in self.role:
                idx = 1

        try:
            self.stackedWidget.setCurrentIndex(idx)
        except Exception:
            # на случай, если имена/структура другой — поставить 0
            self.stackedWidget.setCurrentIndex(0)

    def logout(self):
        # Закрываем главное окно и открываем окно логина снова
        self.close()
        self.login_again = LoginDialog()
        self.login_again.show()


# =====================
# Запуск приложения
# =====================
def main():
    app = QtWidgets.QApplication(sys.argv)

    login = LoginDialog()
    login.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
