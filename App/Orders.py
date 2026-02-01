import os
from PyQt5 import QtCore, QtGui, QtWidgets, uic

from utils import *
from config import *

# ================= ORDERS LIST (mgr/admin) =================
# Окно со списком заказов (для менеджера и администратора)
class Orders(QtWidgets.QDialog):
    def __init__(s,parent,role):
        super().__init__(parent); uic.loadUi(UI["orders"], s); s.setModal(True); s.setWindowTitle("Заказы")
        s.role=role
        # Кнопки управления окном
        s.btn_close.clicked.connect(s.accept)
        s.btn_add.clicked.connect(s._add)
        # Добавлять заказы может только админ
        s.btn_add.setVisible(is_admin(role))
        # Первая загрузка списка заказов
        s._reload()


    # Очистка layout со списком заказов
    def _clear(s):
        lay=s.vl_orders
        while lay.count():
            it=lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()


    # Загрузка списка заказов из БД и отрисовка карточек
    def _reload(s):
        try:
            rows=q("""SELECT o.order_id,o.pickup_code,COALESCE(o.status,''),COALESCE(pp.address,''),o.order_date,o.delivery_date
                      FROM public.orders o LEFT JOIN public.pickup_points pp ON pp.pickup_point_id=o.pickup_point_id
                      ORDER BY o.order_id DESC""",fetch="all")
        except Exception as e: rows=[]; err(s,"Ошибка БД","Не удалось загрузить заказы.",str(e))
        s._clear()
        for oid,code,st,addr,od,dd in rows: s.vl_orders.addWidget(s._card(oid,code,st,addr,od,dd))
        s.vl_orders.addStretch(1)


    # Создание виджета‑карточки одного заказа
    def _card(s,oid,code,st,addr,od,dd):
        c=QtWidgets.QFrame(); c.setFrameShape(QtWidgets.QFrame.Box); c.setStyleSheet("QFrame{border-radius:6px; padding:6px;}")
        hl=QtWidgets.QHBoxLayout(c); hl.setContentsMargins(10,8,10,8)
        left=QtWidgets.QVBoxLayout(); hl.addLayout(left,3)
        # Артикул заказа: код получения, если есть, иначе id заказа
        art = code if code is not None else oid
        for t in (f"Артикул заказа: {art}", f"Статус заказа: {st}", f"Адрес пункта выдачи: {addr}", f"Дата заказа: {od}"):
            left.addWidget(QtWidgets.QLabel(t))
        # Правая часть карточки — дата доставки
        right=QtWidgets.QFrame(); right.setFrameShape(QtWidgets.QFrame.Box); right.setFixedWidth(180)
        rbl=QtWidgets.QVBoxLayout(right); rbl.setContentsMargins(10,8,10,8)
        rbl.addWidget(QtWidgets.QLabel("Дата доставки")); rbl.addWidget(QtWidgets.QLabel("" if not dd else str(dd)))
        hl.addWidget(right,1)
        # Для админа — возможность редактирования/удаления заказа
        if is_admin(s.role):
            c.mousePressEvent=lambda e,x=oid: s._edit(x)
            b=QtWidgets.QPushButton("Удалить"); b.setFixedWidth(90); b.clicked.connect(lambda _,x=oid: s._del(x)); hl.addWidget(b)
        return c


    # Открытие формы добавления заказа
    def _add(s):
        if not is_admin(s.role): return
        d=OrderForm(s,s.role,None); d.saved.connect(s._reload); d.exec_()


    # Открытие формы редактирования заказа
    def _edit(s,oid):
        d=OrderForm(s,s.role,oid); d.saved.connect(s._reload); d.exec_()


    # Удаление заказа после подтверждения
    def _del(s,oid):
        if not ask(s,"Подтверждение",f"Удалить заказ ID {oid}? Операцию нельзя отменить."): return
        try: q("DELETE FROM public.orders WHERE order_id=%s",(oid,)); inf(s,"Готово","Заказ удалён."); s._reload()
        except Exception as e: err(s,"Ошибка БД","Не удалось удалить заказ.",str(e))
