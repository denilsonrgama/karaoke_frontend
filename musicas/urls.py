#musicas/urls.py

from django.urls import path
from .views import (lista_musicas,detalhe_musica, prepare_video_tom, registrar_play,stream_video,stream_video_tom,modo_palco)



urlpatterns = [

    path("", lista_musicas, name="lista_musicas"),
    path("<str:codigo>/", detalhe_musica, name="detalhe_musica"),
    path("<str:codigo>/palco/", modo_palco, name="modo_palco"),
    path("<str:codigo>/stream/", stream_video, name="stream_video"),
    path("<str:codigo>/stream/tom/<str:tom>/", stream_video_tom, name="stream_video_tom"),
    path("<str:codigo>/stream/tom/<str:tom>/prepare/", prepare_video_tom, name="prepare_video_tom"),
    path("<str:codigo>/play/", registrar_play, name="registrar_play"),  # ✅ novo
]

