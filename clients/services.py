from django.db.models import Count, Q

from .models import Commercial, Store


def get_least_loaded_commercial():
    """
    Return the READ_WRITE Commercial currently responsible for the fewest
    active (pending or approved) stores. Ties are broken by id.
    """
    active_statuses = [Store.STATUS_PENDING, Store.STATUS_APPROVED]

    return (
        Commercial.objects
        .filter(access_rights=Commercial.AccessRights.READ_WRITE)
        .annotate(
            store_count=Count(
                "store",
                filter=Q(store__status__in=active_statuses),
            )
        )
        .order_by("store_count", "id")
        .first()
    )