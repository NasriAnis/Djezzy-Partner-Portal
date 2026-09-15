from django.urls import path
from . import views

urlpatterns = [
    path("logout/", views.client_logout, name="client_logout"),
    ######## Pages ##########
    # clients/client_signup_page.html
    path("signup/", views.client_signup, name="client_signup"),
    # clients/client_login_page.html
    path("login/", views.client_login, name="client_login"),
    # clients/client_manage_offer_page.html
    path("manage/", views.client_offer_manage_page, name="client_offer_manage_page"),
    # clients/client_offer_draft_and_stock_page.html
    path("draft-stock/", views.client_offer_draft_and_stock_page, name="client_offer_draft_and_stock_page"),
    # clients/client_dashboard_page.html
    path("<str:username>/", views.client_dashboard_page, name="client_dashboard_page"),
    ####### APIs #########
    path("ajax/communes/", views.get_communes, name="get_communes"),
]
