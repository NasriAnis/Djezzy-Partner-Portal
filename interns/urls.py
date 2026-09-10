from django.urls import path
from . import views

urlpatterns = [
    path('', views.commercials_index_page, name='commercials_index_page'),
    path('login/', views.commercials_login, name='commercials_login'),
    path('logout/', views.commercials_logout, name='commercials_logout'),
    path('dashboard/', views.commercials_dashboard_page, name='commercials_dashboard_page'),
    path('offers/', views.commercials_offers_page, name='commercials_offers_page'),
    path('offers/<slug:slug>/edit/', views.commercials_offer_edit_page, name='commercials_offer_edit_page'),
    path('clients/', views.commercials_clients_page, name='commercials_clients_page'),
    path('clients/<int:client_id>/', views.commercials_client_detail_page, name='commercials_client_detail_page'),
    path('stores/<int:store_id>/', views.commercials_store_detail_page, name='commercials_store_detail_page'),
    path('stores/<int:store_id>/approve/', views.commercials_approve_store, name='commercials_approve_store'),
    path('stores/<int:store_id>/block/', views.commercials_block_store, name='commercials_block_store'),
    path('transactions/<int:transaction_id>/approve/', views.commercials_approve_transaction, name='commercials_approve_transaction'),
    path('transactions/<int:transaction_id>/deny/', views.commercials_deny_transaction, name='commercials_deny_transaction'),
]