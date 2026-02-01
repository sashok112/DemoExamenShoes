import os
from PyQt5 import QtCore, QtGui, QtWidgets, uic

from utils import *
from config import *


# ================= ORDER FORM (admin) =================
# Диалог добавления/редактирования заказа (только админ)
class OrderForm(QtWidgets.QDialog):
    # Сигнал, который посылается после сохранения заказа
    saved = QtCore.pyqtSignal()
    def __init__(s,parent,role,oid=None):
        super().__init__(parent); uic.loadUi(UI["order"], s); s.setModal(True)
        # role — роль пользователя, oid — id заказа (None для нового)
        s.role, s.oid = role, oid
        # Кнопки
        s.btn_cancel.clicked.connect(s.reject); s.btn_save.clicked.connect(s._save)
        # Заполнение списка статусов заказа
        s.cb_status.clear(); s.cb_status.addItems(["Новый","В обработке","Отправлен","Готов к выдаче","Выдан","Отменён"])
        # Установка текущих дат
        s.de_order.setDate(QtCore.QDate.currentDate()); s.de_delivery.setDate(QtCore.QDate.currentDate())
        # Загрузка пунктов выдачи
        s._pickups()
        if oid is None: s.lbl_title.setText("Добавление заказа")
        else: s._load()


    # Загрузка пунктов выдачи в комбобокс
    def _pickups(s):
        try: rows=q("SELECT pickup_point_id, address FROM public.pickup_points ORDER BY address",fetch="all")
        except Exception as e: rows=[]; err(s,"Ошибка БД","Не удалось загрузить пункты выдачи.",str(e))
        s.cb_pickup.clear()
        for pid,addr in rows: s.cb_pickup.addItem(addr,pid)


    # Загрузка существующего заказа по oid и заполнение полей
    def _load(s):
        try:
            r=q("""SELECT order_id, pickup_code, status, order_date, delivery_date, pickup_point_id
                   FROM public.orders WHERE order_id=%s""",(s.oid,), "one")
        except Exception as e: err(s,"Ошибка БД","Не удалось загрузить заказ.",str(e)); return s.reject()
        if not r: err(s,"Ошибка","Заказ не найден."); return s.reject()
        oid,code,st,od,dd,ppid=r
        s.lbl_title.setText(f"Редактирование заказа (ID {oid})")
        s.ed_pickup_code.setText("" if code is None else str(code))
        # Установка статуса в комбобокс
        if st:
            i=s.cb_status.findText(st); (s.cb_status.setCurrentIndex(i) if i>=0 else (s.cb_status.addItem(st), s.cb_status.setCurrentText(st)))
        # Установка дат заказа и доставки
        if od: s.de_order.setDate(QtCore.QDate(od.year,od.month,od.day))
        if dd: s.de_delivery.setDate(QtCore.QDate(dd.year,dd.month,dd.day))
        # Выбор пункта выдачи по его id
        if ppid is not None:
            for i in range(s.cb_pickup.count()):
                if s.cb_pickup.itemData(i)==ppid: s.cb_pickup.setCurrentIndex(i); break


    # Сохранение заказа (INSERT/UPDATE)
    def _save(s):
        if not is_admin(s.role): return err(s,"Доступ запрещён","Добавлять/редактировать заказы может только администратор.")
        t=s.ed_pickup_code.text().strip(); code=None
        # Валидация кода получения (артикула)
        if t:
            try:
                code=int(t)
                if code<0: return err(s,"Ошибка ввода","Артикул (код получения) не может быть отрицательным.")
            except: return err(s,"Ошибка ввода","Артикул (код получения) должен быть числом.")
        st=s.cb_status.currentText().strip(); ppid=s.cb_pickup.currentData()
        od=s.de_order.date().toPyDate(); dd=s.de_delivery.date().toPyDate()
        try:
            if s.oid is None:
                # Добавление нового заказа
                q("""INSERT INTO public.orders (order_date, delivery_date, pickup_point_id, pickup_code, status)
                     VALUES (%s,%s,%s,%s,%s)""",(od,dd,ppid,code,st))
            else:
                # Обновление существующего заказа
                q("""UPDATE public.orders SET order_date=%s, delivery_date=%s, pickup_point_id=%s, pickup_code=%s, status=%s
                     WHERE order_id=%s""",(od,dd,ppid,code,st,s.oid))
            s.saved.emit(); inf(s,"Готово","Заказ сохранён."); s.accept()
        except Exception as e:
            err(s,"Ошибка БД","Не удалось сохранить заказ.",str(e))

