from django.urls import path
from . import views

app_name = 'notifications'

urlpatterns = [
    path('mark-read/<int:pk>/', views.mark_read, name='mark_read'),
    path('all/', views.all_notifications, name='all'),
]
