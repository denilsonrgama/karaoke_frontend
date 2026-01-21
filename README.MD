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
