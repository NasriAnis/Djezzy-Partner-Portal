from django.contrib.auth import logout
from django.shortcuts import redirect
from django.http import JsonResponse

from ..models import Commune

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
