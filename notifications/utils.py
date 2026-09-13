from .models import Notification


def notify(recipient, message, target=None):
    Notification.objects.create(recipient=recipient, message=message, target=target)
