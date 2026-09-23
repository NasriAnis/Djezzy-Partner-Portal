from django.contrib.auth import logout
from django.shortcuts import render, redirect
from functools import wraps
from .permissions import MANAGE_ALL, MANAGE_CLIENTS, MANAGE_OFFERS

########### Decorators ###########


def commercial_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("commercials_login")

        if not hasattr(request.user, "commercial_profile"):
            return render(request, "shared/403.html", status=403)

        return view_func(request, *args, **kwargs)

    return _wrapped_view


########### Utils ###########


def get_commercial_info(request):
    commercial = getattr(request.user, "commercial_profile", None)
    can_edit = bool(commercial and commercial.modifications_rights)

    rights = set()
    if commercial:
        if commercial.has_access_to_all:
            rights.add(MANAGE_ALL)
        if commercial.manage_clients_rights:
            rights.add(MANAGE_CLIENTS)
        if commercial.manage_offers_rights:
            rights.add(MANAGE_OFFERS)

    return commercial, can_edit, rights


def commercials_logout(request):
    logout(request)
    return redirect("commercials_login")