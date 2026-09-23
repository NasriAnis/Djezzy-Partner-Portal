from django.contrib.auth import logout
from django.shortcuts import redirect
from django.http import JsonResponse

from ..models import Commune, Store

########## Utils ##########


def client_logout(request):
    logout(request)
    return redirect("client_login")


def get_communes(request):
    """Used to get communes when selecting a wilaya in forms."""
    wilaya_code = request.GET.get("wilaya") or request.GET.get("wilaya_code")
    if not wilaya_code:
        return JsonResponse([], safe=False)

    padded_code = str(wilaya_code).zfill(2)
    communes = (
        Commune.objects.filter(wilaya_code=padded_code)
        .order_by("name")
        .values("id", "name")
    )
    return JsonResponse(list(communes), safe=False)


def get_selected_store(request, client, *, post_field="store_id"):
    """
    Returns (store, stores): the client's approved stores, and the
    one selected via ?store=<id> / a POSTed field, defaulting to the
    first. `store` is None when the client has no approved store yet
    — callers should treat that as the "no store" empty state.
    """
    stores = Store.objects.filter(
        client=client, status=Store.STATUS_APPROVED
    ).order_by("name")

    if not stores.exists():
        return None, stores

    store_id = request.GET.get("store") or request.POST.get(post_field)
    store = stores.filter(id=store_id).first() if store_id else None
    return store or stores.first(), stores