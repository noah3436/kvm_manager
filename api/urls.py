from django.urls import path
from . import views

urlpatterns = [
    path('create/', views.create_vm),
    path('list/', views.list_vms),
    path('delete/', views.delete_vm),
]
