from django.shortcuts import render

from ..models import Offer, OfferCategory


def client_index_page(request):
    offers = Offer.objects.filter(is_active=True)
    categories = OfferCategory.objects.all()

    selected_category = None
    category_id = request.GET.get("category")
    if category_id:
        offers = offers.filter(category_id=category_id)
        selected_category = categories.filter(id=category_id).first()

    context = {
        "offers": offers,
        "categories": categories,
        "selected_category": selected_category,
    }
    return render(request, "core/client_index.html", context)