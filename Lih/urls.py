from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('LihStudio.urls')),
    path('admin/', admin.site.urls),
]

from django.conf.urls import handler404

handler404 = 'LihStudio.views.pagina_erro_404'