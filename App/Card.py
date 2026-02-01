import os, sys, uuid
import psycopg2
from PyQt5 import QtCore, QtGui, QtWidgets, uic

from utils import *
from config import UI, DB

# ================= CART (client) =================
# Диалог оформления заказа из корзины (для клиента)
class Cart(QtWidgets.QDialog):
    # Сигнал, который отправляется после успешного создания заказа
    order_created = QtCore.pyqtSignal()
    def __init__(s,parent,uid,cart,idx):
        super().__init__(parent); uic.loadUi(UI["cart"], s); s.setModal(True); s.setWindowTitle("Оформление заказа")
        # uid — id пользователя, cart — {product_id: количество}, idx — {product_id: данные товара}
        s.uid, s.cart, s.idx = uid, dict(cart), idx
        # Кнопки управления корзиной
        s.btn_cancel.clicked.connect(s.reject); s.btn_remove.clicked.connect(s._rm); s.btn_confirm.clicked.connect(s._ok)
        # Дата доставки по умолчанию — текущая
        s.de_delivery.setDate(QtCore.QDate.currentDate())
        # Настройка таблицы товаров в корзине
        t=s.table_items; t.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        t.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows); t.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        # Загрузка пунктов выдачи и заполнение таблицы корзины
        s._pickups(); s._fill()


    # Загрузка пунктов выдачи в комбобокс
    def _pickups(s):
        try: rows=q("SELECT pickup_point_id, address FROM public.pickup_points ORDER BY address",fetch="all")
        except Exception as e: rows=[]; err(s,"Ошибка БД","Не удалось загрузить пункты выдачи.",str(e))
        s.cb_pickup.clear()
        for pid,addr in rows: s.cb_pickup.addItem(addr,pid)


    # Заполнение таблицы корзины товарами и подсчёт общей суммы
    def _fill(s):
        t=s.table_items; t.setRowCount(0); total=0.0
        for r,(pid,qty) in enumerate(s.cart.items()):
            p=s.idx.get(pid)
            if not p: continue
            price,disc=float(p["price"]),float(p["discount"])
            # Применение скидки к цене
            fp=price*(1-disc/100.0) if disc>0 else price
            sm=fp*qty; total+=sm
            t.insertRow(r)
            # В первой колонке храним имя товара и его id в UserRole
            it=QtWidgets.QTableWidgetItem(p["product_name"]); it.setData(QtCore.Qt.UserRole,pid)
            t.setItem(r,0,it); t.setItem(r,1,QtWidgets.QTableWidgetItem(str(qty)))
            t.setItem(r,2,QtWidgets.QTableWidgetItem(f"{fp:.2f}")); t.setItem(r,3,QtWidgets.QTableWidgetItem(f"{sm:.2f}"))
        # Отображение итоговой суммы
        s.lbl_total.setText(f"{total:.2f} ₽")


    # Удаление выбранной позиции из корзины
    def _rm(s):
        r=s.table_items.currentRow()
        if r<0: return
        pid=s.table_items.item(r,0).data(QtCore.Qt.UserRole)
        s.cart.pop(pid,None); s._fill()


    # Подтверждение оформления заказа и запись в БД (orders + order_items)
    def _ok(s):
        if not s.uid: return err(s,"Доступ запрещён","Оформить заказ может только авторизованный клиент.")
        if not s.cart: return err(s,"Ошибка","Корзина пустая.")
        ppid=s.cb_pickup.currentData()
        if ppid is None: return err(s,"Ошибка","Выберите пункт выдачи.")
        od=QtCore.QDate.currentDate().toPyDate(); dd=s.de_delivery.date().toPyDate()
        # Генерация 6‑значного кода получения на основе UUID
        code=int(str(uuid.uuid4().int)[:6])
        try:
            # Здесь используется ручная транзакция, т.к. нужно создать заказ и его позиции одним блоком
            c=psycopg2.connect(**DB)
            try:
                cur=c.cursor()
                cur.execute("""INSERT INTO public.orders (order_date, delivery_date, pickup_point_id, user_id, pickup_code, status)
                               VALUES (%s,%s,%s,%s,%s,%s) RETURNING order_id""",(od,dd,ppid,s.uid,code,"Новый"))
                oid=cur.fetchone()[0]
                for pid,qty in s.cart.items():
                    cur.execute("INSERT INTO public.order_items (order_id, product_id, quantity) VALUES (%s,%s,%s)",(oid,pid,qty))
                c.commit(); cur.close()
            finally: c.close()
            # Уведомление пользователя о создании заказа
            inf(s,"Готово",f"Заказ оформлен!\nНомер: {oid}\nКод получения: {code}")
            # Сигнал для очистки корзины в главном окне
            s.order_created.emit(); s.accept()
        except Exception as e:
            err(s,"Ошибка БД","Не удалось оформить заказ.",str(e))

