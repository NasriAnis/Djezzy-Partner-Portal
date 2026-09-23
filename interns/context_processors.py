from .views.utils_views import get_commercial_info
from .views.permissions import MANAGE_OFFERS, MANAGE_CLIENTS, MANAGE_ALL

ACCESS_RIGHT_LABELS = {
    MANAGE_OFFERS: "Manage Offers",
    MANAGE_CLIENTS: "Manage Clients",
    MANAGE_ALL: "Manage All",
}


def _describe_access(rights):
    """
    Turns a set of access-right codes into a (label, badge_color)
    pair for display. MANAGE_ALL wins outright; otherwise show
    whichever of clients/offers are actually granted.
    """
    if MANAGE_ALL in rights:
        return ACCESS_RIGHT_LABELS[MANAGE_ALL], "bg-danger"

    if MANAGE_CLIENTS in rights and MANAGE_OFFERS in rights:
        return "Clients & Offers", "bg-info text-dark"

    if MANAGE_OFFERS in rights:
        return ACCESS_RIGHT_LABELS[MANAGE_OFFERS], "bg-info text-dark"

    if MANAGE_CLIENTS in rights:
        return ACCESS_RIGHT_LABELS[MANAGE_CLIENTS], "bg-secondary"

    return "No Access", "bg-secondary"


def commercial_context(request):
    """
    Adds the logged-in commercial's identity/role to every template's
    context, so the sidebar (or any page) can show a hint of who's
    logged in and what they can do — without every view having to
    pass it manually.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    commercial, can_edit, commercial_type = get_commercial_info(request)
    if not commercial:
        return {}

    label, badge_color = _describe_access(commercial_type)

    return {
        "current_commercial": commercial,
        "current_commercial_type": commercial_type,
        "current_commercial_can_edit": can_edit,
        "current_commercial_type_label": label,
        "current_commercial_type_badge_color": badge_color,
    }