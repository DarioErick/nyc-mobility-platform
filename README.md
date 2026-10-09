# NYC Mobility Platform

Pipeline local de corridas de taxi de Nova York com o clima da cidade.

Dois meses, janeiro de 2023 e janeiro de 2024, entram pelo script em Python, caem no MinIO e saem em tres etapas:

- landing: Parquet bruto do taxi e JSON do clima
- lake: schema unico (airport_fee), clima por hora e resumo hora a hora
- mart.resumo_horario no Postgres: corridas, receita e temperatura por hora

## Como rodar

Com Docker Desktop aberto, na pasta do projeto:

    docker compose up -d

MinIO em http://127.0.0.1:9001. Postgres em localhost:5432, banco mobility, usuario mobility. As senhas ficam no .env, que nao vai para o Git. O modelo esta no .env.example.

Os scripts estao em ingestion/ e rodam em container, com a rede do compose.
