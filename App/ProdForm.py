import os
from PyQt5 import QtCore, QtGui, QtWidgets, uic

from utils import *
from config import *

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

