from PyQt5 import QtCore, QtGui, QtWidgets, uic

from utils import *
from config import UI


# ================= LOGIN =================
# Диалог авторизации пользователя / входа гостем
class Login(QtWidgets.QDialog):
    def __init__(s):
        super().__init__(); uic.loadUi(UI["login"], s); s.setWindowTitle("Вход")
        # Значения по умолчанию — гость
        s.user_id=None; s.full_name="Гость"; s.role="guest"
        # Обработчики кнопок
        s.btn_login.clicked.connect(s._go); s.btn_guest.clicked.connect(s._guest)
        # Нажатие Enter в поле пароля
        s.lineEdit_password.returnPressed.connect(s._go)


    # Попытка входа по логину и паролю
    def _go(s):
        lg=s.lineEdit_login.text().strip(); pw=s.lineEdit_password.text().strip()
        if not lg or not pw: return s.label_message.setText("Введите логин и пароль")
        try: row=q("SELECT user_id, full_name, role FROM public.users WHERE login=%s AND user_password=%s",(lg,pw),"one")
        except Exception as e: s.label_message.setText("Ошибка БД"); return err(s,"Ошибка БД","Не удалось выполнить вход.",str(e))
        if not row: return s.label_message.setText("Неверный логин или пароль")
        # Сохраняем данные пользователя и закрываем диалог с Accept
        s.user_id, s.full_name, s.role = row[0], row[1], row[2] or ""; s.accept()


    # Вход как гость (без учётной записи)
    def _guest(s): s.user_id=None; s.full_name="Гость"; s.role="guest"; s.accept()

