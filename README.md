# 🛍️ Django Shoppingo E-Commerce

A complete **E-commerce web application** built with **Django & Django REST Framework**, featuring user authentication, product management, cart system, checkout, and order tracking.

---

## 🚀 Features

- 🔐 **User Authentication** (Login, Register, Logout)
- 🛒 **Shopping Cart** (Add / Remove / Update items)
- 💳 **Checkout System** (Cash on Delivery, Payment Integration Ready)
- 🧾 **Order Management** (Track & Manage Orders)
- 📦 **Product Management** (Admin CRUD operations)
- 🏷️ **Category-based Browsing**
- 🖼️ **Dynamic Image Uploads**
- ⚙️ **Admin Dashboard (Django Admin Panel)**
- 🌐 **Responsive Frontend with Bootstrap 5**

---

## 🧠 Tech Stack

| Component | Technology |
|------------|-------------|
| Backend | Django 5+, Django REST Framework |
| Frontend | HTML, CSS, Bootstrap 5, JS |
| Database | SQLite3 / PostgreSQL |
| Authentication | Django Auth |
| API Testing | Postman |
| Deployment Ready | Gunicorn / Nginx / VPS |

---

## 🛠️ Installation Guide

### 1️⃣ Clone the repository
```bash
git clone https://github.com/Manir96/Django-Shoppingo-Ecom.git
cd Django-Shoppingo-Ecom


2️⃣ Create a virtual environment

python3 -m venv venv
source venv/bin/activate  # On Linux/Mac
venv\Scripts\activate     # On Windows

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Apply migrations
python manage.py makemigrations
python manage.py migrate

5️⃣ Create a superuser
python manage.py createsuperuser

6️⃣ Run the development server
python manage.py runserver
