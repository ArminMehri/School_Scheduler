"""
URL configuration for School project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from main import views
from main import panel_views as v
urlpatterns = [
    path('admin/', admin.site.urls),

    # Account Manager
    path(
        'company/accounts/',
        views.account_manage,
        name='account_manage'
    ),

    # Cart
    path(
        'company/cart/',
        views.cart_page,
        name='cart_page'
    ),

    path("", views.company_index, name="company_index"),
    path("company/about/", views.about, name="company_about"),
    path("Scheduler/", views.site_index, name="site_index"),
    # path('', views.schedule_table, name='schedule_table'),
    path('build-schedule/', views.build_schedule, name='build_schedule'),
    path('export-excel/', views.export_schedule_excel, name='export_excel'),
    path("export-excel-teacher/", views.export_schedule_excel_teacher, name="export_excel_teacher"),
    path('export-excel-per-class/', views.export_schedule_excel_per_class, name='export_excel_per_class'),
    path('export-excel-per-teacher/', views.export_schedule_excel_per_teacher, name='export_excel_per_teacher'),
    path("panel/", include("main.panel_urls")),
    path('Logs/', views.schedule_build_view, name='schedule-build'),
    path("login/", v.auth_login, name="panel_login"),
    path("register/", v.auth_register, name="panel_register"),
    path("logout/", v.auth_logout, name="panel_logout"),
    path("schedule/progress/", views.schedule_progress_api, name="schedule_progress"),
    path("company/register/", views.company_register, name="company_register"),
    path("company/services/", views.company_services, name="company_services"),
    path("company/contact/", views.company_contact, name="company_contact"),
    path("company/dashboard/", views.company_dashboard, name="company_dashboard"),
    path("company/orders/", views.company_orders, name="company_orders"),
    path("company/projects/", views.company_projects, name="company_projects"),
    path("company/tickets/", views.company_tickets, name="company_tickets"),
]
from django.conf import settings
from django.conf.urls.static import static

urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)