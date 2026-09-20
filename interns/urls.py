from django.urls import path
from . import views

urlpatterns = [
    path("logout/", views.commercials_logout, name="commercials_logout"),
    ########## Pages ##########
    # if already loged in: interns/commercials_dashboard_page.html
    # if not loged in:     interns/commercials_login_page.html
    path("", views.commercials_index_page, name="commercials_index_page"),
    path("login/", views.commercials_login, name="commercials_login"),
    path(
        "dashboard/",
        views.commercials_dashboard_page,
        name="commercials_dashboard_page",
    ),
    # interns/commercials_offers_page.html
    path("offers/", views.commercials_offers_page, name="commercials_offers_page"),
    # interns/commercials_offers_edit__page.html
    path(
        "offers/<slug:slug>/edit/",
        views.commercials_offer_edit_page,
        name="commercials_offer_edit_page",
    ),
    # interns/commercials_clients_page.html
    path("clients/", views.commercials_clients_page, name="commercials_clients_page"),
    # interns/commercials_client_detail_page.html
    path(
        "clients/<int:client_id>/",
        views.commercials_client_detail_page,
        name="commercials_client_detail_page",
    ),
    # interns/commercials_store_detail_page.html
    path(
        "stores/<int:store_id>/",
        views.commercials_store_detail_page,
        name="commercials_store_detail_page",
    ),
    ########## APIs ##########
    path(
        "stores/<int:store_id>/approve/",
        views.commercials_approve_store,
        name="commercials_approve_store",
    ),
    path(
        "stores/<int:store_id>/block/",
        views.commercials_block_store,
        name="commercials_block_store",
    ),
    path(
        "transactions/<int:transaction_id>/approve/",
        views.commercials_approve_transaction,
        name="commercials_approve_transaction",
    ),
    path(
        "transactions/<int:transaction_id>/deny/",
        views.commercials_deny_transaction,
        name="commercials_deny_transaction",
    ),
    path(
           "transactions/<int:transaction_id>/fulfill-waitlist/",
           views.commercials_fulfill_waitlist_transaction,
           name="commercials_fulfill_waitlist_transaction",
       ),
]
