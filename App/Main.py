import os, sys, uuid
import psycopg2
from PyQt5 import QtCore, QtGui, QtWidgets, uic


# --- config ---
# Словарь путей к .ui‑файлам интерфейса Qt Designer
UI = {
    "login": "../UI/login.ui",
    "main": "../UI/main.ui",
    "card": "../UI/product_item.ui",
    "cart": "../UI/cart.ui",
    "prod": "../UI/product_form.ui",
    "order": "../UI/order_form.ui",
    "orders": "../UI/orders_list.ui",
}
# Папка с фотографиями товаров и картинка по умолчанию
PHOTOS, PH = "../import", "../resources/picture.png"
# Параметры подключения к базе данных PostgreSQL
DB = dict(host="localhost", port=5432, database="test", user="postgres", password="1234")


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


# ================= PRODUCT FORM (admin) =================
# Диалог добавления/редактирования товара (только админ)
class ProdForm(QtWidgets.QDialog):
    # Сигнал, который будет послан после сохранения товара
    saved = QtCore.pyqtSignal()
    def __init__(s, parent, role, pid=None):
        super().__init__(parent); uic.loadUi(UI["prod"], s); s.setModal(True)
        # role — роль текущего пользователя, pid — id товара (None для нового)
        s.role, s.pid, s.old, s.new = role, pid, None, None
        # Кнопки формы
        s.btn_cancel.clicked.connect(s.reject); s.btn_save.clicked.connect(s._save); s.btn_pick_photo.clicked.connect(s._pick)
        # Заполнение списков категорий и производителей
        s._lists()
        if pid is None: s.lbl_title.setText("Добавление товара"); s.lbl_id.setText(""); phpix(s.photo)
        else: s._load()


    # Загрузка справочников категорий и производителей из БД
    def _lists(s):
        try:
            cats=[x[0] for x in q("SELECT DISTINCT category FROM public.products WHERE category IS NOT NULL ORDER BY category",fetch="all") if x[0]]
            mans=[x[0] for x in q("SELECT DISTINCT manufacturer FROM public.products WHERE manufacturer IS NOT NULL ORDER BY manufacturer",fetch="all") if x[0]]
        except Exception as e: cats,mans=[],[]; err(s,"Ошибка БД","Не удалось загрузить справочники.",str(e))
        s.cb_category.clear(); s.cb_category.addItems(cats if cats else [""])
        s.cb_manufacturer.clear(); s.cb_manufacturer.addItems(mans if mans else [""])


    # Загрузка существующего товара по id и заполнение полей
    def _load(s):
        try:
            r=q("""SELECT id, product_name, unit, price, supplier, manufacturer, category, discount, stock_quantity, description, photo
                   FROM public.products WHERE id=%s""",(s.pid,), "one")
        except Exception as e: err(s,"Ошибка БД","Не удалось загрузить товар.",str(e)); return s.reject()
        if not r: err(s,"Ошибка","Товар не найден."); return s.reject()
        pid,name,unit,price,sup,man,cat,disc,stock,desc,photo=r
        s.lbl_title.setText("Редактирование товара"); s.lbl_id.setText(f"ID: {pid} (только чтение)")
        # Старое имя файла фото (для последующего удаления при замене)
        s.old=photo
        # Заполнение полей формы
        s.ed_name.setText(name or ""); s.ed_unit.setText(unit or "")
        s.ed_price.setText(f"{float(price):.2f}" if price is not None else "")
        s.ed_supplier.setText(sup or ""); s.ed_discount.setText(f"{float(disc):.2f}" if disc is not None else "")
        s.sp_stock.setValue(int(stock or 0)); s.ed_description.setPlainText(desc or "")
        # Установка категории в комбобоксе (если нет — добавляем)
        if cat:
            i=s.cb_category.findText(cat); (s.cb_category.setCurrentIndex(i) if i>=0 else (s.cb_category.addItem(cat), s.cb_category.setCurrentText(cat)))
        # Аналогично для производителя
        if man:
            i=s.cb_manufacturer.findText(man); (s.cb_manufacturer.setCurrentIndex(i) if i>=0 else (s.cb_manufacturer.addItem(man), s.cb_manufacturer.setCurrentText(man)))
        # Показ фото или картинки по умолчанию
        s._show(photo)


    # Отображение фото в QLabel по имени файла
    def _show(s, fn):
        fp=os.path.join(PHOTOS, fn) if fn else ""
        setpix(s.photo, fp if fn and os.path.exists(fp) else PH, s.photo.width(), s.photo.height())


    # Выбор нового изображения через диалог и сохранение его в папку PHOTOS
    def _pick(s):
        fp,_=QtWidgets.QFileDialog.getOpenFileName(s,"Выбор изображения","","Изображения (*.png *.jpg *.jpeg *.bmp)")
        if not fp: return
        p=QtGui.QPixmap(fp)
        if p.isNull(): return err(s,"Ошибка","Не удалось открыть изображение.")
        p=p.scaled(QtCore.QSize(300,200), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        os.makedirs(PHOTOS, exist_ok=True)
        ext=os.path.splitext(fp)[1].lower()
        if ext not in (".png",".jpg",".jpeg",".bmp"): ext=".png"
        # Уникальное имя файла для изображения
        name=f"{uuid.uuid4().hex}{ext}"
        if not p.save(os.path.join(PHOTOS,name)): return err(s,"Ошибка","Не удалось сохранить изображение.")
        s.new=name; s.photo.setPixmap(p)


    # Валидация введённых данных товара; возвращает текст ошибки или None
    def _bad(s):
        if not s.ed_name.text().strip(): return "Заполните «Наименование»."
        pr=fnum(s.ed_price.text()); 
        if pr is None: return "Некорректная цена. Пример: 1999.90"
        if pr<0: return "Цена не может быть отрицательной."
        dc=fnum(s.ed_discount.text() or "0")
        if dc is None: return "Некорректная скидка. Пример: 10"
        if dc<0: return "Скидка не может быть отрицательной."
        return None


    # Сохранение товара (INSERT или UPDATE) в БД
    def _save(s):
        if not is_admin(s.role): return err(s,"Доступ запрещён","Добавлять/редактировать товары может только администратор.")
        if (b:=s._bad()): return err(s,"Ошибка ввода",b)
        # Считывание значений из полей формы
        name=s.ed_name.text().strip(); cat=s.cb_category.currentText().strip()
        desc=s.ed_description.toPlainText().strip(); man=s.cb_manufacturer.currentText().strip()
        sup=s.ed_supplier.text().strip(); pr=fnum(s.ed_price.text()); unit=s.ed_unit.text().strip()
        stock=int(s.sp_stock.value()); dc=fnum(s.ed_discount.text() or "0"); photo=s.new or s.old
        try:
            if s.pid is None:
                # Добавление нового товара
                q("""INSERT INTO public.products (product_name, category, description, manufacturer, supplier, price, unit, stock_quantity, discount, photo)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (name,cat,desc,man,sup,pr,unit,stock,dc,photo))
            else:
                # Обновление существующего товара
                q("""UPDATE public.products SET product_name=%s, category=%s, description=%s, manufacturer=%s, supplier=%s,
                     price=%s, unit=%s, stock_quantity=%s, discount=%s, photo=%s WHERE id=%s""",
                  (name,cat,desc,man,sup,pr,unit,stock,dc,photo,s.pid))
            # Удаление старого файла фото, если был выбран новый
            if s.new and s.old and s.new!=s.old:
                op=os.path.join(PHOTOS,s.old)
                if os.path.exists(op):
                    try: os.remove(op)
                    except: pass
            # Сигнал о сохранении и уведомление пользователя
            s.saved.emit(); inf(s,"Готово","Изменения сохранены."); s.accept()
        except Exception as e:
            err(s,"Ошибка БД","Не удалось сохранить товар.",str(e))


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


# ================= MAIN =================
# Главное окно приложения с каталогом и разным функционалом по ролям
class Main(QtWidgets.QMainWindow):
    def __init__(s,name,role,uid):
        super().__init__(); uic.loadUi(UI["main"], s)
        # Имя пользователя, его роль и id
        s.name, s.role, s.uid = name, role or "", uid
        # Корзина клиента: {product_id: количество}
        s.cart={}; s.lock=False; s.products=[]
        # Отображение имени пользователя
        s.label_user.setText(name); s.btn_logout.clicked.connect(s.close)
        # Настройка страницы по роли, подключение сигналов и первая загрузка каталога
        s._page(); s._wire(); s._reload(); s._view()


    # Переключение видимой страницы (stackedWidget) в зависимости от роли
    def _page(s):
        r=R(s.role)
        idx,title = (0,"Каталог товаров")
        if r in ("guest","гость"): idx,title=(0,"Каталог товаров (Гость)")
        elif is_cli(r):           idx,title=(1,"Каталог товаров (Клиент)")
        elif is_mgr(r):           idx,title=(2,"Каталог товаров (Менеджер)")
        elif is_admin(r):         idx,title=(3,"Каталог товаров (Администратор)")
        s.stackedWidget.setCurrentIndex(idx); s.setWindowTitle(title)


    # Подключение сигналов элементов интерфейса к методам
    def _wire(s):
        # Поля поиска по товарам для разных ролей
        for n in ("ed_search_client","ed_search_manager","ed_search_admin"):
            if hasattr(s,n): getattr(s,n).textChanged.connect(s._view)
        # Комбобоксы фильтра поставщика и сортировки
        for n in ("cb_supplier_client","cb_supplier_manager","cb_supplier_admin","cb_sort_client","cb_sort_manager","cb_sort_admin"):
            if hasattr(s,n): getattr(s,n).currentIndexChanged.connect(s._view)
        # Кнопка открытия корзины (для клиента)
        if hasattr(s,"btn_cart_client"): s.btn_cart_client.clicked.connect(s._open_cart)
        # Кнопки просмотра заказов (менеджер/админ)
        if hasattr(s,"btn_orders_manager"): s.btn_orders_manager.clicked.connect(s._open_orders)
        if hasattr(s,"btn_orders_admin"): s.btn_orders_admin.clicked.connect(s._open_orders)
        # Кнопка добавления товара (только для админа)
        if hasattr(s,"btn_add_product_admin"):
            s.btn_add_product_admin.setVisible(is_admin(s.role))
            s.btn_add_product_admin.clicked.connect(s._add)


    # Загрузка всех товаров из БД в список s.products и обновление фильтров поставщиков
    def _reload(s):
        try:
            rows=q("""SELECT id, article, product_name, price, manufacturer, photo, category, discount, unit, supplier, description, stock_quantity
                      FROM public.products""",fetch="all")
        except Exception as e: rows=[]; err(s,"Ошибка БД","Не удалось загрузить товары.",str(e))
        s.products=[]; sups=set()
        for pid,art,n,pr,man,ph,cat,dc,unit,sup,desc,stk in rows:
            sup=(sup or "").strip(); sups.add(sup)
            s.products.append(dict(id=pid,article=art or "",product_name=n or "",price=float(pr or 0),manufacturer=man or "",
                                   photo=ph or "",category=cat or "",discount=float(dc or 0),unit=unit or "",supplier=sup,
                                   description=desc or "",stock_quantity=int(stk or 0)))
        # Формирование списка поставщиков для комбобоксов
        opts=["Все поставщики"]+sorted([x for x in sups if x])
        for cbn in ("cb_supplier_client","cb_supplier_manager","cb_supplier_admin"):
            if hasattr(s,cbn):
                cb=getattr(s,cbn); cur=cb.currentText() if cb.count() else "Все поставщики"
                cb.blockSignals(True); cb.clear(); cb.addItems(opts)
                i=cb.findText(cur); cb.setCurrentIndex(i if i>=0 else 0); cb.blockSignals(False)


    # Получение текущих параметров поиска, фильтра и сортировки по роли
    def _params(s):
        r=R(s.role)
        if is_admin(r): return (s.ed_search_admin.text().strip().lower(), s.cb_supplier_admin.currentText(), s.cb_sort_admin.currentText())
        if is_mgr(r):   return (s.ed_search_manager.text().strip().lower(), s.cb_supplier_manager.currentText(), s.cb_sort_manager.currentText())
        if is_cli(r):   return (s.ed_search_client.text().strip().lower(), s.cb_supplier_client.currentText(), s.cb_sort_client.currentText())
        return ("","Все поставщики","Без сортировки")


    # Получение нужного layout для отрисовки карточек товаров
    def _layout(s):
        r=R(s.role)
        if is_admin(r) and hasattr(s,"layout_products_admin"): return s.layout_products_admin
        if is_mgr(r)   and hasattr(s,"layout_products_manager"): return s.layout_products_manager
        if is_cli(r)   and hasattr(s,"layout_products_client"): return s.layout_products_client
        return s.layout_products if hasattr(s,"layout_products") else None


    # Применение фильтрации и сортировки и обновление отображения каталога
    def _view(s):
        search,sup,sortm=s._params()
        # Локальная функция проверки, подходит ли товар под текущие фильтры
        def ok(p):
            if sup!="Все поставщики" and p["supplier"]!=sup: return False
            if not search: return True
            hay=" ".join([p["article"],p["product_name"],p["unit"],p["supplier"],p["manufacturer"],p["category"],p["description"],p["photo"]]).lower()
            return search in hay
        # Фильтрация
        arr=[p for p in s.products if ok(p)]
        # Сортировка по количеству на складе
        if sortm=="Кол-во ↑": arr.sort(key=lambda x:x["stock_quantity"])
        elif sortm=="Кол-во ↓": arr.sort(key=lambda x:x["stock_quantity"], reverse=True)
        lay=s._layout()
        if lay: s._render(lay,arr)


    # Очистка layout от карточек товаров
    def _clear(s,lay):
        while lay.count():
            it=lay.takeAt(0)
            if it.widget(): it.widget().deleteLater()


    # Отрисовка карточек товаров в переданный layout
    def _render(s,lay,arr):
        s._clear(lay); A=is_admin(s.role); C=is_cli(s.role)
        for p in arr:
            w=uic.loadUi(UI["card"])
            # Заполнение основных полей карточки
            w.name.setText(p["product_name"])
            w.manufacturer.setText(p["manufacturer"]); w.category.setText(p["category"]); w.discount.setText(f"{p['discount']:.0f}")
            w.unit.setText(p["unit"]); w.supplier.setText(p["supplier"]); w.description.setText(p["description"]); w.stock.setText(str(p["stock_quantity"]))
            pr,dc=float(p["price"]),float(p["discount"])
            # Отображение цены и скидки (зачёркнутая старая цена и новая)
            if dc>0:
                fp=pr*(1-dc/100.0); f=w.price.font(); f.setStrikeOut(True)
                w.price.setFont(f); w.price.setStyleSheet("color:red;")
                w.price.setText(f"{pr:.2f} ₽"); w.final_price.setText(f"{fp:.2f} ₽")
            else:
                w.price.setText(f"{pr:.2f} ₽"); w.final_price.setText("")
            # Загрузка изображения товара или картинки по умолчанию
            fn=p["photo"]; full=os.path.join(PHOTOS,fn) if fn else ""
            setpix(w.photo, full if fn and os.path.exists(full) else PH, 150, 150)
            # Кнопки редактирования/удаления видимы только для админа
            w.btn_edit.setVisible(A); w.btn_delete.setVisible(A)
            # Кнопка "Добавить в корзину" доступна только клиенту
            if hasattr(w,"btn_add_to_cart"):
                w.btn_add_to_cart.setVisible(C)
                if C: w.btn_add_to_cart.clicked.connect(lambda _,pid=p["id"]: s._add_cart(pid))
            if A:
                # Обработчики редактирования и удаления товара
                w.btn_edit.clicked.connect(lambda _,pid=p["id"]: s._edit(pid))
                w.btn_delete.clicked.connect(lambda _,pid=p["id"],n=p["product_name"]: s._del(pid,n))
                # Клик по карточке тоже открывает редактирование
                w.mousePressEvent=lambda e,pid=p["id"]: s._edit(pid)
            lay.addWidget(w)
        lay.addStretch(1)


    # client
    # Добавление товара в корзину (только для роли клиента)
    def _add_cart(s,pid):
        if not is_cli(s.role): return
        s.cart[pid]=s.cart.get(pid,0)+1
        inf(s,"Корзина","Товар добавлен в корзину.")


    # Открытие окна корзины клиента
    def _open_cart(s):
        if not is_cli(s.role): return
        if not s.cart: return inf(s,"Корзина","Корзина пустая.")
        idx={p["id"]:p for p in s.products}
        d=Cart(s,s.uid,s.cart,idx); d.order_created.connect(lambda: s.cart.clear()); d.exec_()


    # admin products
    # Открытие формы добавления товара (с защитой от повторного открытия)
    def _add(s):
        if not is_admin(s.role): return err(s,"Доступ запрещён","Добавлять товары может только администратор.")
        if s.lock: return inf(s,"Информация","Окно редактирования товара уже открыто.")
        s.lock=True
        d=ProdForm(s,s.role,None); d.saved.connect(s._after); d.finished.connect(lambda _: setattr(s,"lock",False)); d.exec_()


    # Открытие формы редактирования товара по id (для админа)
    def _edit(s,pid):
        if not is_admin(s.role): return
        if s.lock: return inf(s,"Информация","Окно редактирования товара уже открыто.")
        s.lock=True
        d=ProdForm(s,s.role,pid); d.saved.connect(s._after); d.finished.connect(lambda _: setattr(s,"lock",False)); d.exec_()


    # Удаление товара из БД (с проверкой, что он не участвует в заказах)
    def _del(s,pid,name):
        if not is_admin(s.role): return
        try: cnt=q("SELECT COUNT(*) FROM public.order_items WHERE product_id=%s",(pid,),"one")[0]
        except Exception as e: return err(s,"Ошибка БД","Не удалось проверить товар в заказах.",str(e))
        if cnt>0: return err(s,"Удаление запрещено","Нельзя удалить товар, который присутствует в заказе.","Удалите/измените order_items или выберите другой товар.")
        if not ask(s,"Подтверждение",f"Удалить товар «{name}»? Операцию нельзя отменить."): return
        try:
            photo=(q("SELECT photo FROM public.products WHERE id=%s",(pid,),"one") or [""])[0]
            q("DELETE FROM public.products WHERE id=%s",(pid,))
        except Exception as e: return err(s,"Ошибка БД","Не удалось удалить товар.",str(e))
        # Удаление файла изображения товара, если он есть
        if photo:
            fp=os.path.join(PHOTOS,photo)
            if os.path.exists(fp):
                try: os.remove(fp)
                except: pass
        inf(s,"Готово","Товар удалён."); s._after()


    # Действия после изменения списка товаров (перезагрузка и перерисовка)
    def _after(s): s._reload(); s._view()


    # orders
    # Открытие окна списка заказов (для менеджера/админа)
    def _open_orders(s): Orders(s,s.role).exec_()


# Точка входа в приложение
def main():
    app=QtWidgets.QApplication(sys.argv)
    while True:
        # Диалог входа пользователя
        lg=Login()
        # Если вход не выполнен (Cancel/закрытие) — выходим из цикла и приложения
        if lg.exec()!=QtWidgets.QDialog.Accepted: break
        # Открываем главное окно с параметрами вошедшего пользователя
        w=Main(lg.full_name, lg.role, lg.user_id); w.show()
        app.exec()
    sys.exit()


# Запуск main при запуске файла как скрипта
if __name__=="__main__": main()
