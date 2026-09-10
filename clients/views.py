from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.http.response import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from .forms import ClientSignupForm, StoreForm, OfferSaleForm
from .models import Client, Commune, Store, StoreOfferTransaction, StoreStock, OfferSale
from django.http import JsonResponse
from clients.backends import EmailBackend
from django.db.models import Prefetch, F, Q
from django.db import transaction
from django.contrib import messages
from django.urls import reverse

def client_signup(request):
    if request.method == 'POST':
        form = ClientSignupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = User.objects.create_user(
                username=data['username'],
                email=data['email'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                password=data['password'],
            )
            Client.objects.create(user=user, phone=data.get('phone', ''))
            login(request, user, backend='clients.backends.EmailBackend')
            return redirect('client_dashboard_page', username=user.username)
    else:
        form = ClientSignupForm()
    return render(request, 'clients/client_signup_page.html', {'form': form})


def client_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('client_dashboard_page', username=user.username)
        else:
            return render(request, 'clients/client_login_page.html', {'error': 'Invalid credentials'})
    return render(request, 'clients/client_login_page.html')


def client_logout(request):
    logout(request)
    return redirect('client_login')

def get_communes(request):
    wilaya_code = request.GET.get('wilaya') or request.GET.get('wilaya_code')
    if not wilaya_code:
        return JsonResponse([], safe=False)

    padded_code = str(wilaya_code).zfill(2)

    communes = Commune.objects.filter(wilaya_code=padded_code).order_by('name').values('id', 'name')
    return JsonResponse(list(communes), safe=False)

@login_required(login_url='client_login')
def client_dashboard_page(request, username):
    user = get_object_or_404(User, username=username)
    if request.user != user:
        return redirect('client_dashboard_page', username=request.user.username)
    client = user.client_profile
    stores = client.locations.all().order_by('-created_at')
    form = StoreForm()

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'edit_client':
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name = request.POST.get('last_name', '').strip()
            user.email = request.POST.get('email', '').strip()
            user.save()
            client.phone = request.POST.get('phone', '').strip()
            client.save()
            return redirect('client_dashboard_page', username=username)

        elif form_type == 'add_store':
            form = StoreForm(request.POST, request.FILES)
            if form.is_valid():
                store = form.save(commit=False)
                store.client = client
                store.active_status = False
                store.save()
                return redirect('client_dashboard_page', username=username)

        elif form_type == 'edit_store':
            store = get_object_or_404(Store, id=request.POST.get('store_id'), client=client)
            store.name = request.POST.get('name', '').strip()
            store.address_line1 = request.POST.get('address_line1', '').strip()
            store.phone = request.POST.get('phone', '').strip()
            store.save()
            return redirect('client_dashboard_page', username=username)

    active_stores = Store.objects.filter(client=client, active_status=True).prefetch_related(
        Prefetch(
            'transactions',
            queryset=StoreOfferTransaction.objects.select_related('plan__offer').order_by('-created_at')
        )
    )
    pending_blocked_stores = Store.objects.filter(
        Q(client=client, active_status=False, blocked_status=False) |
        Q(client=client, active_status=False, blocked_status=True)
    )

    return render(request, 'clients/client_dashboard_page.html', {
        'client': client,
        'stores': stores,
        'form': form,
        'active_stores': active_stores,
        'pending_blocked_stores': pending_blocked_stores,
    })

@login_required(login_url='client_login')
def client_offer_manage_page(request):
    client = request.user.client_profile
    stores = Store.objects.filter(client=client, active_status=True).order_by('name')

    if not stores.exists():
        messages.info(request, "You don't have any store yet. Add one first.")
        return render(request, 'clients/client_manage_offer_page.html', {
            'store': None, 'stores': stores, 'stock_list': [], 'sales': [], 'form': None,
        })

    store_id = request.GET.get('store') or request.POST.get('store_id_selected')
    store = None
    if store_id:
        store = stores.filter(id=store_id).first()
    if store is None:
        store = stores.first()
    
    if request.method == 'POST':
        form = OfferSaleForm(request.POST, store=store)
        if form.is_valid():
            with transaction.atomic():
                stock = StoreStock.objects.select_for_update().get(
                    store=store, plan_id=form.cleaned_data['plan_id']
                )

                if stock.remaining < 1:
                    form.add_error(None, "Stock changed — nothing left. Try again.")
                else:
                    stock.sold = F('sold') + 1
                    stock.save(update_fields=['sold'])

                    OfferSale.objects.create(
                        store=store,
                        plan_id=form.cleaned_data['plan_id'],
                        phone_number=form.cleaned_data['phone_number'],
                        sold_by=request.user,
                    )
                    messages.success(request, "Offer sold successfully.")
                    return redirect(f"{reverse('client_offer_manage_page')}?store={store.id}")
    else:
        form = OfferSaleForm(store=store)

    stock_qs = (
        StoreStock.objects
        .filter(store=store)
        .select_related('plan__offer')
        .order_by('plan__offer__title', 'plan__label')
    )
    sales_qs = (
        OfferSale.objects
        .filter(store=store)
        .select_related('plan__offer')
        .order_by('-created_at')[:50]
    )

    return render(request, 'clients/client_manage_offer_page.html', {
        'store': store,
        'stores': stores,
        'stock_list': stock_qs,
        'sales': sales_qs,
        'form': form,
    })