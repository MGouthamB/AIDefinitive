# myapp/urls.py
from django.urls import path, re_path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('test/', views.test, name='Test'),
    path('step1/<str:link>/', views.step1, name='Step1 Fill the form'),
    path('step2/<str:link>/', views.step2, name='Step2 AI Definitve Non Compete Agreement'),
    path('step3/<str:link>/', views.step3, name='Step3 AI Definitive Promissory Note'),
    path('step4/<str:link>/', views.step4, name='Step4 AI Payment'),
    path('payment_completed',views.payment_completed,name='payment_completed'),
    re_path(r'^media/(?P<path>.*)$', views.serve_protected_media),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)