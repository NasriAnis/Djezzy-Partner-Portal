import json
from datetime import timedelta

from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import render, redirect
from django.utils import timezone

from core.models import Offer
from clients.models import Client, Store, StoreOfferTransaction, WILAYA_CHOICES

from .utils_views import commercial_required

# Approximate wilaya-capital coordinates, used to position the density map
# bubbles. These are centroids, not administrative boundaries.
WILAYA_COORDS = {
    "01": (27.870, -0.290), "02": (36.165, 1.335), "03": (33.800, 2.865),
    "04": (35.877, 7.117), "05": (35.555, 6.174), "06": (36.750, 5.084),
    "07": (34.850, 5.728), "08": (31.615, -2.218), "09": (36.470, 2.828),
    "10": (36.373, 3.902), "11": (22.785, 5.522), "12": (35.404, 8.124),
    "13": (34.878, -1.315), "14": (35.371, 1.317), "15": (36.712, 4.045),
    "16": (36.753, 3.058), "17": (34.673, 3.263), "18": (36.822, 5.766),
    "19": (36.190, 5.409), "20": (34.830, 0.151), "21": (36.879, 6.909),
    "22": (35.190, -0.630), "23": (36.900, 7.767), "24": (36.462, 7.427),
    "25": (36.365, 6.615), "26": (36.264, 2.754), "27": (35.935, 0.089),
    "28": (35.706, 4.541), "29": (35.397, 0.140), "30": (31.949, 5.325),
    "31": (35.691, -0.642), "32": (33.686, 1.019), "33": (26.483, 8.467),
    "34": (36.073, 4.762), "35": (36.766, 3.477), "36": (36.767, 8.313),
    "37": (27.671, -8.147), "38": (35.607, 1.811), "39": (33.368, 6.867),
    "40": (35.436, 7.143), "41": (36.286, 7.951), "42": (36.588, 2.448),
    "43": (36.450, 6.264), "44": (36.264, 1.966), "45": (33.266, -0.313),
    "46": (35.297, -1.140), "47": (32.489, 3.673), "48": (35.737, 0.556),
    "49": (29.263, 0.231), "50": (21.328, 0.949), "51": (34.417, 5.067),
    "52": (30.130, -2.170), "53": (27.194, 2.480), "54": (19.573, 5.767),
    "55": (33.107, 6.061), "56": (24.554, 9.483), "57": (33.950, 5.930),
    "58": (30.583, 2.883),
}
WILAYA_NAMES = dict(WILAYA_CHOICES)


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
    all_stores = Store.objects.all()
    all_clients = Client.objects.all()

    # "Djezzy sale" = the operator (Djezzy) selling offer quota to a store,
    # i.e. an approved StoreOfferTransaction — not OfferSale, which is the
    # store reselling to its own end customer.
    all_transactions = StoreOfferTransaction.objects.filter(
        status=StoreOfferTransaction.STATUS_APPROVED
    )
    line_total = ExpressionWrapper(
        F("quantity_bought") * F("plan__price_da"),
        output_field=DecimalField(max_digits=14, decimal_places=2),
    )

    # --- Monthly offers sold / revenue, last 6 months, company-wide ---
    six_months_ago = timezone.now() - timedelta(days=180)
    monthly_qs = (
        all_transactions.filter(created_at__gte=six_months_ago)
        .annotate(month=TruncMonth("created_at"), line_total=line_total)
        .values("month")
        .annotate(offers_sold=Sum("quantity_bought"), revenue=Sum("line_total"))
        .order_by("month")
    )
    monthly_labels = [row["month"].strftime("%b %Y") for row in monthly_qs]
    monthly_sold = [row["offers_sold"] or 0 for row in monthly_qs]
    monthly_revenue = [float(row["revenue"] or 0) for row in monthly_qs]

    # --- Per-wilaya store density, offers sold and revenue, company-wide ---
    density_qs = all_stores.values("wilaya").annotate(store_count=Count("id"))
    sales_by_wilaya_qs = (
        all_transactions.annotate(line_total=line_total)
        .values("store__wilaya")
        .annotate(offers_sold=Sum("quantity_bought"), revenue=Sum("line_total"))
    )

    wilaya_stats = {}
    for row in density_qs:
        code = row["wilaya"]
        wilaya_stats[code] = {
            "code": code,
            "name": WILAYA_NAMES.get(code, code),
            "store_count": row["store_count"],
            "offers_sold": 0,
            "revenue": 0.0,
            "lat": WILAYA_COORDS.get(code, (None, None))[0],
            "lng": WILAYA_COORDS.get(code, (None, None))[1],
        }
    for row in sales_by_wilaya_qs:
        code = row["store__wilaya"]
        entry = wilaya_stats.setdefault(
            code,
            {
                "code": code,
                "name": WILAYA_NAMES.get(code, code),
                "store_count": 0,
                "offers_sold": 0,
                "revenue": 0.0,
                "lat": WILAYA_COORDS.get(code, (None, None))[0],
                "lng": WILAYA_COORDS.get(code, (None, None))[1],
            },
        )
        entry["offers_sold"] = row["offers_sold"] or 0
        entry["revenue"] = float(row["revenue"] or 0)

    wilaya_list = sorted(
        (w for w in wilaya_stats.values() if w["lat"] is not None),
        key=lambda w: w["revenue"],
        reverse=True,
    )

    context = {
        "offers_count": Offer.objects.count(),
        "clients_count": all_clients.distinct().count(),
        "stores_count": all_stores.count(),
        "wilaya_stats": wilaya_list,
        "monthly_labels_json": json.dumps(monthly_labels),
        "monthly_sold_json": json.dumps(monthly_sold),
        "monthly_revenue_json": json.dumps(monthly_revenue),
        "wilaya_data_json": json.dumps(wilaya_list, cls=DjangoJSONEncoder),
    }
    return render(request, "interns/commercials_dashboard_page.html", context)