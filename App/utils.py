import os, sys, uuid
import psycopg2
from PyQt5 import QtCore, QtGui, QtWidgets, uic

from config import *

# --- helpers (small but readable) ---
# Нормализация строки роли к нижнему регистру, защита от None
def R(role): return (role or "").lower()
# Проверка, является ли пользователь администратором (англ./рус. варианты)
def is_admin(r): r=R(r); return r=="admin" or "администратор" in r
# Проверка роли менеджера
def is_mgr(r):   return "менеджер" in R(r)
# Проверка роли клиента
def is_cli(r):   return "клиент" in R(r)


# Безопасное преобразование строки в число с плавающей точкой
def fnum(s):
    s=(s or "").strip().replace(",", ".")
    try: return float(s) if s else None
    except: return None


# Универсальная функция для запросов к БД
def q(sql, p=(), fetch="none"):
    c=psycopg2.connect(**DB)
    try:
        cur=c.cursor(); cur.execute(sql, p)
        # В зависимости от параметра fetch выбираем режим выборки
        out = cur.fetchone() if fetch=="one" else cur.fetchall() if fetch=="all" else None
        c.commit(); cur.close(); return out
    finally:
        c.close()


# Унифицированное создание и показ окна сообщений
def mbox(w, icon, title, text, details=""):
    b=QtWidgets.QMessageBox(w); b.setIcon(icon); b.setWindowTitle(title); b.setText(text)
    if details: b.setDetailedText(details)
    return b.exec_()


# Сообщение об ошибке
def err(w,t,s,d=""): return mbox(w, QtWidgets.QMessageBox.Critical, t, s, d)
# Информационное сообщение
def inf(w,t,s):      return mbox(w, QtWidgets.QMessageBox.Information, t, s)
# Вопрос пользователю (Да/Нет), возвращает True/False
def ask(w,t,s):
    b=QtWidgets.QMessageBox(w); b.setIcon(QtWidgets.QMessageBox.Warning); b.setWindowTitle(t); b.setText(s)
    b.setStandardButtons(QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.No); b.setDefaultButton(QtWidgets.QMessageBox.No)
    return b.exec_()==QtWidgets.QMessageBox.Yes


# Установка изображения в QLabel, с масштабированием и проверкой существования файла
def setpix(lbl, path, w, h):
    if os.path.exists(path):
        p=QtGui.QPixmap(path)
        lbl.setPixmap(p.scaled(w, h, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
    else:
        lbl.setText("Нет фото")


# Установить картинку по умолчанию в QLabel
def phpix(lbl): setpix(lbl, PH, lbl.width(), lbl.height())