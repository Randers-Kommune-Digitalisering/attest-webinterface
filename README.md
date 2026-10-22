# attest-webinterface
[**Formål**](#formål) | [**Beskrivelse**](#beskrivelse) | [**Dataflow**](#dataflow) | [**Features**](#features) | [**Login og adgang**](#login-og-adgang) | [**Afhængigheder**](#afh%C3%A6ngigheder) | [**API**](#api) | [**Udvikling**](#udvikling)

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
sequenceDiagram
    participant UI as Vue-webinterface
    participant API as Flask-API
    participant DB as PostgreSQL-database

    Note over UI,DB: Læsning: vis bestillinger og historik
    UI->>API: GET /api/orders, /api/ordercount, /api/history/...
    API->>DB: Henter bestillinger
    DB-->>API: Bestillinger
    API-->>UI: JSON

    Note over UI,DB: Opdatering: markér som bestilt eller afvis
    UI->>API: POST /api/processorders eller /api/rejectorder/{order_id}
    API->>DB: Opdaterer status og opretter hændelse i order_event
    DB-->>API: Antal opdaterede bestillinger
    API-->>UI: Resultat
```

Webinterfacet taler kun med Flask-API'et. Ved **læsning** henter API'et bestillinger og historik fra databasen og returnerer dem som JSON. Ved **opdatering** ændrer API'et bestillingens status og registrerer handlingen som en hændelse i `order_event`


## Features

- Viser ventende bestillinger fordelt på attesttype og subtype
- Viser antal ventende bestillinger
- Markerer én eller flere bestillinger som bestilt
- Afviser en ventende bestilling
- Viser historik over bestilte og færdigbehandlede bestillinger
- Udbyder et healthcheck-endpoint til overvågning

## Login og adgang

Brugere logger ind via Keycloak (OpenID Connect). Kun brugere med klientrollen `attest-admin` på Keycloak-klienten (`KEYCLOAK_CLIENT_ID`) får adgang

1. Frontend'en kalder API'et. Hvis brugeren ikke er logget ind, svarer API'et `401`, og frontend'en sender brugeren videre til `/api/login`.
2. `/api/login` sender brugeren til Keycloak
3. Efter login vender brugeren tilbage til `/api/auth`. Backend'en kontrollerer rollen `attest-admin`:
    - Har brugeren rollen, gemmes navn, e-mail og roller i en session-cookie
    - Mangler rollen, svarer backend'en `403`
4. Når en bestilling markeres som bestilt eller afvises, gemmes brugerens e-mail som `actor` i `order_event`

### Lokal udvikling uden Keycloak

Når `DISABLE_KEYCLOAK=true` er sat, logges der automatisk ind som en fast testbruger (`test@test.dk`) med rollen `attest-admin`. Det er kun tilladt med `FLASK_ENV=dev`. med `FLASK_ENV=prod` stopper applikationen ved opstart.

## Afhængigheder

### Database

Applikationen kræver adgang til en PostgreSQL-database

Databasen skal indeholde de tabeller og felter, som backendens forespørgsler bruger:
`attestation_order`, `attestation_request` og `order_event`.

Ved hver handling oprettes en hændelse i `order_event` med brugerens e-mail (`actor`). Ved afvisning gemmes også `rejection_reason` og `rejection_description`.

### Teknologier
- [Flask](https://flask.palletsprojects.com/) - backend og API
- [Vue](https://vuejs.org/) og [vite](https://vite.dev/) - brugergrænseflade
- [PostgreSQL](https://www.postgresql.org/) - lagring af bestillinger og hændelser
- [Keycloak](https://www.keycloak.org/) og [AuthLib](https://docs.authlib.org/) - login via OpenID Connect

### Miljøvariabler
| Variabel | Påkrævet | Beskrivelse |
|---|---:|---|
| `DATABASE_URL` | Ja | Forbindelsesstreng til PostgreSQL-databasen. |
| `FLASK_ENV` | Nej | Flask-konfiguration: `dev` eller `prod`. Standard er `dev`. |
| `PORT` | Nej | Backendens port. Standard er `8080`. |
| `DEBUG` | Nej | Aktiverer debug-logning. Standard afhænger af `FLASK_ENV`. |
| `POD_NAME` | Nej | Navn på applikationens pod. Standard er `pod_name_not_set`. |
| `SECRET_KEY` | Ja med Keycloak | Bruges til at signere session-cookien. Applikationen starter ikke hvis den mangler eller er `CHANGE_ME`. |
| `DISABLE_KEYCLOAK` | Nej | `true` slår Keycloak fra og bruger en testbruger. Kun tilladt med `FLASK_ENV=dev`. Standard er `false`. |
| `KEYCLOAK_URL` | Ja med Keycloak | Base-URL til Keycloak. | 
| `KEYCLOAK_REALM` | Ja med Keycloak | Keycloak-realm |
| `KEYCLOAK_CLIENT_ID` | Ja med Keycloak | Klient-id i Keycloak. Rollen `attest-admin` skal ligge på denne klient. | 
| `KEYCLOAK_CLIENT_SECRET` | Ja med Keycloak | Klienthemmelighed i Keycloak | 

Lokalt kan variablerne sættes i en `.env`-fil (se [.env.example](.env.example)). Filen ignoreres af git.
Hemmelige værdier og adgangsoplysninger må ikke gemmes i kildekoden eller versionsstyres

## API 

Backendens API bruger præfikset `/api`.

| Metode | Endpoint | Beskrivelse |
|---|---|---|
| `GET` | `/healthz` | Healthcheck for Flask-applikationen. |
| `GET` | `/api/login` | Sender brugeren til login i Keycloak |
| `GET` | `/api/auth` | Modtager brugeren efter login og opretter sessionen. |
| `GET` | `/api/userinfo` | Returnerer navn, e-mail og roller for den indloggede bruger. |
| `GET` | `/api/status` | Status for backend-API'et |
| `GET` | `/api/orders` | Henter alle ventende bestillinger. |
| `GET` | `/api/orders/<attest_type>/<sub_type>` | Henter ventende bestillinger for en attesttype og subtype. Brug `null` som undertype hvis den ikke er angivet. |
| `GET` | `/api/ordercount` | Henter antal ventende bestillinger fordelt på attesttype og subtype |
| `GET` | `/api/history/ordered` | Henter bestillinger, der er markeret som bestilt. |
| `GET` | `/api/history/completed` | henter færdigbehandlede bestillinger. |
| `POST` | `/api/rejectorder/<order_id>` | Afviser en ventende bestilling. |
| `POST` | `/api/processorders` | Markerer en liste af ventende bestillinger som bestilt. |

Kald uden gyldig session svarer `401 Not authenticated`.

`POST /api/processorders` forventer en JSON-liste med bestillings-id'er:
```json
["order-id-1", "order-id-2"]
```

`POST /api/rejectorder/<order_id>` forventer et JSON-objekt med reason og description for rejection:
```json
{
    "reason": "incorrect",
    "description": "Fejl i CPR-nummer. CPR-nummeret findes ikke i CPR-registeret."
}
```
`reason` er en af koderne `incorrect`, `duplicate` eller `other`. `description` gemmes sammen med afvisningshændelsen i `order_event`. For `other` sendes brugerens egen beskrivelse, for de to andre
faste årsager bruger backend de tilhørende faste tekster. 

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
$env:PORT = "1880"
$env:FLASK_ENV = "dev"
$env:DISABLE_KEYCLOAK = "true"
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