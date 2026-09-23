from django.contrib.auth import logout
from django.shortcuts import render, redirect
from functools import wraps

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
    """Helper: returns (commercial, can_edit, commercial_type)."""
    commercial = getattr(request.user, "commercial_profile", None)
    can_edit = bool(commercial and commercial.modifications_rights)
    commercial_type = commercial.access_rights if commercial else False
    return commercial, can_edit, commercial_type


def commercials_logout(request):
    logout(request)
    return redirect("commercials_login")
