# Quotas managment system
A Django-based platform for telecom operators (e.g. Djezzy) to manage offers sold through outside sellers. Lets operators set purchase thresholds (seuils) per wilaya and per boutique, track consumption against those limits, and control distribution across their reseller network.
# Project Structure
 
```
├── config/                 # Project settings, root URLconf, WSGI/ASGI entrypoints
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── core/                   # Shared static assets, base templates, landing/home routes
│   ├── static/
│   ├── templates/
│   ├── urls.py
│   └── views.py
├── clients/                 # Client-facing app (signup, login, account page)
│   ├── models.py           # Client model (OneToOne -> User)
│   ├── views.py
│   ├── forms.py
│   ├── backends.py         # Custom EmailBackend for authentication
│   ├── urls.py
│   └── templates/clients/
├── interns/                 # Commercial/staff-facing app
│   ├── models.py           # Commercial model (OneToOne -> User)
│   ├── admin.py            # Custom admin form for creating commercials
│   ├── forms.py            # CommercialAdminForm (creates User + Commercial together)
│   ├── views.py
│   ├── urls.py
│   └── templates/interns/
├── notifications/
│   ├── models.py
│   ├── admin.py
│   ├── utils.py              # notify() function utility
│   ├── context_processors.py # notification processor 
│   ├── views.py
│   ├── urls.py
│   └── templates/notifications/ # Notification html page
├── shared/                  # Cross-app reusable code (no models required)
│   └── ...
├── media/                   # User-uploaded files
└── manage.py
```
# Setup
### 1. Clone and enter the project
```bash
git clone https://github.com/NasriAnis/Quota-ManagementSystem.git
cd https://github.com/NasriAnis/Quota-ManagementSystem.git
```
 
### 2. Create and activate a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```
 
### 3. Install dependencies
```bash
pip install -r requirements.txt
```
 
### 4. Configure environment variables
Create a `.env` file in the project root:
```env
SECRET_KEY=your-secret-key-here
DEBUG=True
```
 
### 5. Apply migrations
```bash
python manage.py migrate
```
 
### 6. Create a superuser (for admin access)
```bash
python manage.py createsuperuser
```
### 8. Load communes to wilaya data
```bash
python manage.py load_communes communes.json
```
 
### 7. Run the development server
```bash
python manage.py runserver
```
 
The site will be available at `http://127.0.0.1:8000/`.
# Key URL Routes
 
| Path                              | App      | Purpose                                  |
|------------------------------------|----------|-------------------------------------------|
| `/admin/`                          | Django   | Admin panel — manage users, clients, commercials, offers |
| `/`                                 | core     | Public/home routes                        |
| `/account/`                         | clients  | Client signup, login, logout, account page |
| `/commercial/`                      | interns  | Commercial index — redirects to login or dashboard |
| `/commercial/login/`                | interns  | Commercial login                          |
| `/commercial/dashboard/`            | interns  | Commercial dashboard (login required)     |
# Creating a Commercial Account
 
Commercials are **admin-managed only** — there is no public signup form for them:
 
1. Log in to `/admin/` as a superuser.
2. Under **Interns → Commercials**, click **Add**.
3. Fill in first name, last name, email, phone, password, and access rights.
4. Saving creates both the `User` account (with hashed password) and the linked `Commercial` profile in one step.
# Managing Superusers
 
Delete an existing superuser:
```bash
python manage.py shell -c "from django.contrib.auth import get_user_model; get_user_model().objects.filter(username='old_username').delete()"
```
 
Create a new one interactively:
```bash
python manage.py createsuperuser
```