from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    ########## APIs #########

    path('mark-read/<int:pk>/', views.mark_read, name='mark_read'),

    ########## Pages #########

    # notifications/all.html
    path('all/', views.all_notifications, name='all'),
]
