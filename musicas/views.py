# karaoke_frontend/musicas/views.py
from django.conf import settings
import os
from django.http import StreamingHttpResponse, Http404, HttpResponseForbidden
from django.core import signing
from .services import buscar_musica_por_codigo

from django.shortcuts import render, redirect
from .services import buscar_musica_por_codigo, buscar_musicas



# Token válido por 5 minutos
TOKEN_TTL = 300  # segundos

# -----------------------------
# LISTA DE MÚSICAS
# -----------------------------
def lista_musicas(request):
    codigo = request.GET.get("codigo")
    artista = request.GET.get("artista")
    nome = request.GET.get("nome")

    try:
        pagina = max(int(request.GET.get("page", 1)), 1)
    except ValueError:
        pagina = 1

    # Redireciona para detalhe se código informado
    if codigo:
        return redirect("detalhe_musica", codigo=str(codigo).zfill(5))

    contexto = {
        "musicas": [],
        "total": 0,
        "pagina": pagina,
        "tem_proxima": False,
        "tem_anterior": False,
        "artista": artista or "",
        "nome": nome or "",
    }

    try:
        resultado = buscar_musicas(pagina=pagina, artista=artista, nome=nome)
        contexto.update({
            "musicas": resultado.get("lista", []),
            "total": resultado.get("total", 0),
            "tem_proxima": bool(resultado.get("next")),
            "tem_anterior": bool(resultado.get("previous")),
        })
    except Exception as e:
        print(f"[ERRO] Falha ao buscar músicas: {e}")
        contexto["erro"] = "Erro ao carregar músicas"

    return render(request, "musicas/lista.html", contexto)


# -----------------------------
# DETALHE DA MÚSICA
# -----------------------------
def detalhe_musica(request, codigo):
    codigo = str(codigo).zfill(5)
    musica = buscar_musica_por_codigo(codigo)

    if not musica:
        return render(
            request,
            "musicas/details.html",
            {"erro": "Música não encontrada"},
            status=404
        )

    # Gera token seguro para streaming
    token = signing.dumps(codigo, salt="video-stream")

    return render(
        request,
        "musicas/details.html",
        {"musica": musica, "token": token}
    )


# -----------------------------
# STREAM DE VÍDEO
# -----------------------------
TOKEN_TTL = 300  # 5 minutos

def stream_video(request, codigo):
    token = request.GET.get("token")
    if not token:
        return HttpResponseForbidden("Token não fornecido")

    # valida token
    try:
        token_codigo = signing.loads(token, salt="video-stream", max_age=TOKEN_TTL)
    except signing.SignatureExpired:
        return HttpResponseForbidden("Token expirado")
    except signing.BadSignature:
        return HttpResponseForbidden("Token inválido")

    if str(codigo).zfill(5) != token_codigo:
        return HttpResponseForbidden("Token não corresponde ao vídeo")

    musica = buscar_musica_por_codigo(str(codigo).zfill(5))
    if not musica or not musica.get("caminho_video"):
        raise Http404("Arquivo de vídeo não encontrado")

    # monta caminho físico no disco usando MEDIA_ROOT + nome do arquivo
    path = os.path.join(settings.MEDIA_ROOT, musica["caminho_video"])
    if not os.path.exists(path):
        raise Http404("Arquivo de vídeo não encontrado")

    def file_iterator(path, chunk_size=8192):
        with open(path, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    response = StreamingHttpResponse(file_iterator(path), content_type="video/mp4")
    response["Content-Length"] = os.path.getsize(path)
    response["Accept-Ranges"] = "bytes"
    return response
