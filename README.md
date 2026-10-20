# attest-webinterface
[**Formål**](#formål) | [**Beskrivelse**](#beskrivelse) | [**Dataflow**](#dataflow) | [**Features**](#features) | [**Afhængigheder**](#afh%C3%A6ngigheder) | [**API**](#api) | [**Udvikling**](#udvikling)

# Formål

Attest-webinterfacet bruges til at håndtere bestillinger af attester. 
Medarbejdere kan gennemgå ventende bestillinger, markere dem som bestilt eller afvise dem
og se historik over bestillinger

Løsningen består af en Vue-baseret brugergrænseflade og en Flask-backend, der læser og
opdaterer bestillinger i en PostgreSQL-database

## Beskrivelse

Webinterfacet henter ventende attestbestillinger fra databasen og viser dem fordelt på attesttype
og subtype. Brugeren kan markere en eller flere bestillinger som bestilt eller afvise en bestilling
Handlingerne opdaterer bestillingens status og opretter en hændelse i databasen

Interfacet viser også historik over bestilte og færdigbehandlede bestillinger.

## Dataflow
```mermaid
flowchart LR
    DB[(PostgreSQL-database)]
    API[Flask-API]
    UI[Vue-webinterface]

    DB -- "Ventende bestillinger og historik" --> API
    API -- "JSON via /api" --> UI
    UI -- "Markér som bestilt / afvis" --> API
    API -- "Opdaterer status og opretter hændelse" --> DB
```

Webinterfacet taler kun med Flask-API'et. Det er det, der læser og opdaterer bestillinger 
i databasen


## Features

- Viser ventende bestillinger fordelt på attesttype og subtype
- Viser antal ventende bestillinger
- Markerer én eller flere bestillinger som bestilt
- Afviser en ventende bestilling
- Viser historik over bestilte og færdigbehandlede bestillinger
- Udbyder et healthcheck-endpoint til overvågning

## Afhængigheder

### Database

Applikationen kræver adgang til en PostgreSQL-database

Databasen skal indeholde de tabeller og felter, som backendens forespørgsler bruger:
`attestation_order`, `attestation_request` og `order_event`

### Teknologier
- [Flask](https://flask.palletsprojects.com/) - backend og API
- [Vue](https://vuejs.org/) og [vite](https://vite.dev/) - brugergrænseflade
- [PostgreSQL](https://www.postgresql.org/) - lagring af bestillinger og hændelser

### Miljøvariabler
| Variabel | Påkrævet | Beskrivelse |
|---|---:|---|
| `DATABASE_URL` | Ja | Forbindelsesstreng til PostgreSQL-databasen. |
| `FLASK_ENV` | Nej | Flask-konfiguration: `dev` eller `prod`. Standard er `dev`. |
| `PORT` | Nej | Backendens port. Standard er `8080`. |
| `DEBUG` | Nej | Aktiverer debug-logning. Standard afhænger af `FLASK_ENV`. |
| `POD_NAME` | Nej | Navn på applikationens pod. Standard er `pod_name_not_set`. |
| `SECRET_KEY` | Nej | Flask secret key. Skal konfigureres sikkert i driftsmiljøet. 

Hemmelige værdier og adgangsoplysninger må ikke gemmes i kildekoden eller versionsstyres

## API 

Backendens API bruger præfikset `/api`.

| Metode | Endpoint | Beskrivelse |
|---|---|---|
| `GET` | `/healthz` | Healthcheck for Flask-applikationen. |
| `GET` | `/api/status` | Status for backend-API'et |
| `GET` | `/api/orders` | Henter alle ventende bestillinger. |
| `GET` | `/api/orders/<attest_type>/<sub_type>` | Henter ventende bestillinger for en attesttype og subtype. Brug `null` som undertype hvis den ikke er angivet. |
| `GET` | `/api/ordercount` | Henter antal ventende bestillinger fordelt på attesttype og subtype |
| `GET` | `/api/history/ordered` | Henter bestillinger, der er markeret som bestilt. |
| `GET` | `/api/history/completed` | henter færdigbehandlede bestillinger. |
| `POST` | `/api/rejectorder/<order_id>` | Afviser en ventende bestilling. |
| `POST` | `/api/processorders` | Markerer en liste af ventende bestillinger som bestilt. |

`POST /api/processorders` forventer en JSON-liste med bestillings-id'er:
```json
["order-id-1", "order-id-2"]
```


## Udvikling

<!--
Beskrivelse af hvordan løsningen startes lokalt.
Overblik over eventuelle API endpoints som løsningen udstiller.
Notering af eventuelle hard-codede værdier, og hvordan værdierne kan ændres.
-->

### Lokal udvikling

Løsningen kan køres lokalt med tre dele: en PostgreSQL-database i Docker, 
Flask-backend og Vue-frontend. Hver del køres i sin egen powershell-terminal.

**Brug kun opdigtede testdata.** Indsæt aldrig produktionsdata eller ægte CPR-numre i den lokale database.

#### Forudsætninger

- Python 3.10+
- Node.js
- Docker Desktop

#### 1) Start en lokal database

```powershell
docker run --name attest-local-db `
    -e POSTGRES_USER=attest `
    -e POSTGRES_PASSWORD=kun_til_lokal_test `
    -e POSTGRES_DB=attest_local `
    -p 127.0.0.1:5433:5432 `
    -d postgres:16
```

Hvis containeren allerede findes, startes den med `docker start attest-local-db`.

#### 2) Opret tabeller og testdata

Kør fra projektroden:
```powershell
Get-Content local\seed.sql | docker exec -i attest-local-db psql -U attest -d attest_local
```

[local/seed.sql](local/seed.sql) opretter et minimalt testskema med opdigtede testdata. Skemaet
dækker kun de felter som backenden bruger og er ikke identisk med produktionsdata. 

Attesttyperne (`attest_type`, `attest_subtype`) skal matche værdierne i [vue/src/assets/attestTypes.json](vue/src/assets/attestTypes.json)
ellers vises bestillingerne ikke i frontenden

#### 3) Start backend

Kør fra projektroden:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt -r requirements-dev.txt

$env:DATABASE_URL = "postgresql://attest:kun_til_lokal_test@127.0.0.1:5433/attest_local"
$env:PORT ="1880"
$env:FLASK_ENV = "dev"
$env:PYTHONPATH = "$PWD;$PWD\backend\src"

python -m backend.src.main
```

Bemærk:
- Backenden skal køre på port `1880`, fordi frontendens udviklingsproxy i [vue/vite.config.js](vue/vite.config.js)
sender `/api`-kald dertil
- Miljøvariablerne gælder kun i den terminal hvor de er sat
- Hvis PowerShell blokerer aktivering af `.venv` køres først `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`.

Kontrollér i en ny terminal at backenden svarer:

```powershell
Invoke-RestMethod http://localhost:1880/healthz
Invoke-RestMethod http://localhost:1880/api/ordercount
```

#### 4) Start frontend

Kør i en ny terminal:

```powershell
cd vue
npm ci
npm run dev
```

Åbn adressen, som Vite skriver i terminalen (typisk `http://localhost:5173`). Gå til **Bestillinger**,
og klik på en orange attesttype for at se testbestillingerne.

> Når du tester flowet "Bestil attester", skal du bruge **"Spring over"** i trin 2 i stedet for at åbne Politiets hjemmeside.

#### Nulstil testdata

Kør seed-filen igen. Den sletter testtabellerne og opretter dem med de oprindelige testdata:

```powershell
Get-Content local\seed.sql | docker exec -i attest-local-db psql -U attest -d attest_local
```

Sådan fjernes den lokale database helt:
```powershell
docker rm -f attest-local-db
```

### Formatering, linting, test

Organisér imports med iSort:

```bash
isort .
```

Formatér kode, så den overholder PEP 8 med Autopep8:

```bash
autopep8 .
```

Kør linting med Flake8:

```bash
flake8
```

Kør tests med Pytest:

```bash
pytest
```