def notifications(request):
    if request.user.is_authenticated and hasattr(request.user, 'client_profile'):
        qs = request.user.client_profile.notifications.filter(is_read=False)[:10]
        unread_count = request.user.client_profile.notifications.filter(is_read=False).count()
        return {
            'nav_notifications': qs,
            'unread_notifications_count': unread_count,
        }
    return {}