#karaoke_frontend/musicas/urls.py
from django.urls import path
from .views import lista_musicas, detalhe_musica, stream_video

urlpatterns = [
    path('', lista_musicas, name='lista_musicas'),
    path('<str:codigo>/', detalhe_musica, name='detalhe_musica'),
    path('<str:codigo>/stream/', stream_video, name='stream_video'),
]
