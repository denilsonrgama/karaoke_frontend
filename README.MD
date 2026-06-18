# KARAOKE_frontend

Projeto Django + PostgreSQL

Aplicaçao para escolha de musicasde KARAOKE para cantar em casa ou ser enviada para uma fila de cantores
em um evento de KARAOKE.

A aplicação contem controle de fila, inserção de Karaoke vindo do youtube para que o KJ possa inserir na fila de cantores com a 
escolha e preferência do cantor

## Como rodar
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Versionamento

A versao exibida na interface fica em:

```text
app/version.py
```

Para publicar uma nova versao, altere `APP_VERSION` para o proximo numero, por exemplo `v002`, faca commit e atualize a VPS com `git pull`.

## Variaveis de email no Render

Para a rotina "Esqueci minha senha" enviar email de verdade em producao, configure:

```env
EMAIL_HOST=smtp.seu-provedor.com
EMAIL_PORT=587
EMAIL_HOST_USER=usuario-do-smtp
EMAIL_HOST_PASSWORD=senha-ou-app-password
EMAIL_USE_TLS=True
EMAIL_USE_SSL=False
DEFAULT_FROM_EMAIL=Karaoke do Cowboy <no-reply@karaokedocowboy.art.br>
```

## Acesso inicial de usuario

O limite de musicas iniciais para usuarios cadastrados pode ser ajustado no Render:

```env
FREE_SONG_LIMIT=2
```

## Mercado Pago Pix

Configure no Render:

```env
MERCADOPAGO_ACCESS_TOKEN=APP_USR...
MERCADOPAGO_WEBHOOK_SECRET=segredo_configurado_no_webhook
```

No Mercado Pago, cadastre o webhook:

```text
https://seu-dominio/pagamento/mercadopago/webhook/
```
