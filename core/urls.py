from django.urls import path

from . import views

urlpatterns = [
    ######## Pages ##########

    # core/client_index.html
    path("", views.client_index_page, name="client_index_page"),

    # core/offer_details_page.html
    path("offers/<slug:offer_slug>/", views.offer_detail_page, name="offer_detail_page")
]