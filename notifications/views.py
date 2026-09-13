from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Notification

########## API ##########

@login_required
def mark_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, recipient=request.user.client_profile)
    n.is_read = True
    n.save()
    return redirect('notifications:all')

########## Pages ##########

@login_required
def all_notifications(request):
    notifications = request.user.client_profile.notifications.all()
    notifications.filter(is_read=False).update(is_read=True)
    return render(request, 'notifications/all.html', {'notifications': notifications})