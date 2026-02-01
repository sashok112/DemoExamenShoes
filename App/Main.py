import os, sys, uuid
import psycopg2
from PyQt5 import QtCore, QtGui, QtWidgets, uic


from Orders import *
from Login import *
from Card import *
from ProdForm import *
from config import *
from ProdForm import *
from OrderForm import *
from utils import *


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
            if dc > 15:
                w.setStyleSheet("background-color: #2E8B57;")
            else:
                w.price.setText(f"{pr:.2f} ₽"); w.final_price.setText("")
            
            if int(p["stock_quantity"]) <= 0:
                w.setStyleSheet("background-color: lightblue;")
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
