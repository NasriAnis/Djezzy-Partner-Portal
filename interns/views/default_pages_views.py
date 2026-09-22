from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from core.models import Offer
from clients.models import Client, Store

from .utils_views import commercial_required, get_commercial_info
from .permissions import scope_by_commercial


def commercials_index_page(request):
    if request.user.is_authenticated:
        return redirect("commercials_dashboard_page")
    return redirect("commercials_login")


def commercials_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect("commercials_dashboard_page")
        else:
            return render(
                request,
                "interns/commercials_login_page.html",
                {"error": "Invalid credentials"},
            )
    return render(request, "interns/commercials_login_page.html")


@login_required(login_url="commercials_login")
@commercial_required
def commercials_dashboard_page(request):
    commercial, _, commercial_type = get_commercial_info(request)

    my_stores = scope_by_commercial(Store.objects.all(), commercial, commercial_type)
    my_clients = scope_by_commercial(
        Client.objects.all(), commercial, commercial_type, field="locations__commmercial"
    )

    context = {
        "offers_count": Offer.objects.count(),
        "clients_count": my_clients.distinct().count(),
        "stores_count": my_stores.count(),
        "recent_stores": my_stores.select_related("client__user").order_by(
            "-created_at"
        )[:5],
    }
    return render(request, "interns/commercials_dashboard_page.html", context)
