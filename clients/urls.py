from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.client_signup, name='client_signup'),
    path('login/', views.client_login, name='client_login'),
    path('logout/', views.client_logout, name='client_logout'),
    path('manage/', views.client_offer_manage_page, name='client_offer_manage_page'),
    path('<str:username>/', views.client_dashboard_page, name='client_dashboard_page'),
    path('ajax/communes/', views.get_communes, name='get_communes'),
]