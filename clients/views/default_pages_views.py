from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Prefetch

from ..forms import ClientSignupForm, StoreForm
from ..models import Client, Store, StoreOfferTransaction

########## Pages ##########


def client_signup(request):
    if request.method == "POST":
        form = ClientSignupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = User.objects.create_user(
                username=data["username"],
                email=data["email"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                password=data["password"],
            )
            Client.objects.create(user=user, phone=data.get("phone", ""))
            login(request, user, backend="clients.backends.EmailBackend")
            return redirect("client_dashboard_page", username=user.username)
    else:
        form = ClientSignupForm()
    return render(request, "clients/client_signup_page.html", {"form": form})


def client_login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect("client_dashboard_page", username=user.username)
        else:
            return render(
                request,
                "clients/client_login_page.html",
                {"error": "Invalid credentials"},
            )
    return render(request, "clients/client_login_page.html")


@login_required(login_url="client_login")
def client_dashboard_page(request, username):
    user = get_object_or_404(User, username=username)
    if request.user != user:
        return redirect("client_dashboard_page", username=request.user.username)
    client = user.client_profile
    stores = client.locations.all().order_by("-created_at")
    form = StoreForm()

    if request.method == "POST":
        form_type = request.POST.get("form_type")

        if form_type == "edit_client":
            user.first_name = request.POST.get("first_name", "").strip()
            user.last_name = request.POST.get("last_name", "").strip()
            user.email = request.POST.get("email", "").strip()
            user.save()
            client.phone = request.POST.get("phone", "").strip()
            client.save()
            return redirect("client_dashboard_page", username=username)

        elif form_type == "add_store":
            form = StoreForm(request.POST, request.FILES)
            if form.is_valid():
                store = form.save(commit=False)
                store.client = client
                store.status = Store.STATUS_PENDING
                store.save()
                return redirect("client_dashboard_page", username=username)

        elif form_type == "edit_store":
            store = get_object_or_404(
                Store, id=request.POST.get("store_id"), client=client
            )
            store.name = request.POST.get("name", "").strip()
            store.address_line1 = request.POST.get("address_line1", "").strip()
            store.phone = request.POST.get("phone", "").strip()
            store.save()
            return redirect("client_dashboard_page", username=username)

    active_stores = Store.objects.filter(
        client=client, status=Store.STATUS_APPROVED
    ).prefetch_related(
        Prefetch(
            "transactions",
            queryset=StoreOfferTransaction.objects.select_related(
                "plan__offer"
            ).order_by("-created_at"),
        )
    )
    pending_blocked_stores = Store.objects.filter(client=client).exclude(
        status=Store.STATUS_APPROVED
    )

    return render(
        request,
        "clients/client_dashboard_page.html",
        {
            "client": client,
            "stores": stores,
            "form": form,
            "active_stores": active_stores,
            "pending_blocked_stores": pending_blocked_stores,
        },
    )
