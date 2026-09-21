from django.urls import path

from . import views

urlpatterns = [
    # Main page
    path("", views.SubnetsView.as_view(), name="subnets"),

    # IPAM Grid
    path("add/", views.DeviceIPEditView.as_view(), name="deviceip_add"),
    path("import/", views.DeviceIPImportView.as_view(), name="deviceip_import"),
    path("<int:pk>/edit/", views.DeviceIPEditView.as_view(), name="deviceip_edit"),
    path("<int:pk>/delete/", views.DeviceIPDeleteView.as_view(), name="deviceip_delete"),

    # Subnets
    path("subnets/add/", views.SubnetEditView.as_view(), name="subnet_add"),
    path("subnets/<int:pk>/edit/", views.SubnetEditView.as_view(), name="subnet_edit"),

    # Per-cell reserve / assign
    path(
        "subnets/<int:prefix_pk>/ip/<str:address>/",
        views.IPCellEditView.as_view(),
        name="ipcell_edit",
    ),
]
