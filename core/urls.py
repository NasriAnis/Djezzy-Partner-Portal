from django.urls import path

from core.views import index_page_views
from core.views import offer_details_views

urlpatterns = [
    ######## Pages ##########
    # core/client_index.html
    path("", index_page_views.client_index_page, name="client_index_page"),
    # core/offer_details_page.html
    path(
        "offers/<slug:offer_slug>/", offer_details_views.offer_detail_page, name="offer_detail_page"
    ),
]
