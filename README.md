# Airport API

REST API service for airport management and flight ticket booking, written with Django REST Framework.

Manage airports, routes, airplanes, crews and flights, and let authenticated users book tickets with seat validation.

## Tech stack

- Python, Django, Django REST Framework
- PostgreSQL
- JWT authentication (`djangorestframework-simplejwt`)
- API documentation (`drf-spectacular`: Swagger UI and ReDoc)
- Docker and Docker Compose
- Pillow for image uploads, `django-debug-toolbar` (enabled only when `DEBUG=True`)

## Run with Docker (recommended)

Docker and Docker Compose must be installed.

1. Clone the repository:

   ```shell
   git clone https://github.com/Yurii-Hvozd/airport-management-api.git
   cd airport-management-api
   ```

2. Create the `.env` file from the sample (the real `.env` is git-ignored and must never be committed):

   ```shell
   cp .env.sample .env
   ```

   Open `.env` and set your own `SECRET_KEY` and `POSTGRES_PASSWORD`.
   Keep `POSTGRES_HOST=db` for Docker. For local development set `DEBUG=True`.
   

3. Build and start the containers (migrations are applied automatically on startup):

   ```shell
   docker-compose build
   docker-compose up
   ```

4. In a second terminal, create an admin user:

   ```shell
   docker-compose exec airport python manage.py createsuperuser
   ```

5. (Optional) Load sample data (airports, routes, airplanes, crews, flights, orders and 3 test users):

   ```shell
   docker-compose exec airport python manage.py loaddata airport_test_data.json
   ```

   Test accounts:

   | Email               | Password      | Role  |
   |---------------------|---------------|-------|
   | admin@example.com   | `testpass123` | admin |
   | olena@example.com   | `testpass123` | user  |
   | andriy@example.com  | `testpass123` | user  |

6. The API is now available at **http://localhost:8001/**

   - Swagger UI: http://localhost:8001/api/schema/swagger-ui/
   - ReDoc: http://localhost:8001/api/schema/redoc/
   - Admin panel: http://localhost:8001/admin/

To stop the project press `Ctrl+C` or run `docker-compose down`.

## Environment variables

All settings are read from `.env` (copy it from `.env.sample`).

| Variable            | Description                                                 | Example                    |
|---------------------|-------------------------------------------------------------|----------------------------|
| `SECRET_KEY`        | Django secret key. Generate a new one for every environment | `...`                      |
| `DEBUG`             | `True` only for local development. **Default is `False`**   | `True`                     |
| `ALLOWED_HOSTS`     | Comma-separated host names (required when `DEBUG=False`)    | `localhost,127.0.0.1`      |
| `POSTGRES_DB`       | Database name                                               | `airport`                  |
| `POSTGRES_USER`     | Database user                                               | `airport`                  |
| `POSTGRES_PASSWORD` | Database password                                           | `your_password_here`       |
| `POSTGRES_HOST`     | Database host (`db` in Docker)                              | `db`                       |
| `POSTGRES_PORT`     | Database port                                               | `5432`                     |
| `PGDATA`            | PostgreSQL data directory (Docker)                          | `/var/lib/postgresql/data` |

Notes:

- `django-debug-toolbar` is installed only when `DEBUG=True`, so it is never exposed in production.
- With `DEBUG=False` Django does not serve `/media/` files. In production serve them with a web server (nginx) or object storage.
- If a real `.env` was ever committed, rotate `SECRET_KEY` and the database password.

## Getting access

Most read endpoints are public. Booking tickets and managing your profile require authentication.

1. **Register** a user: `POST /api/user/register/`

   ```json
   {
     "email": "user@example.com",
     "password": "strongpassword",
     "first_name": "John",
     "last_name": "Doe"
   }
   ```

2. **Get a token pair** (log in with email): `POST /api/user/token/`

   ```json
   {
     "email": "user@example.com",
     "password": "strongpassword"
   }
   ```

   The response contains `access` (valid 15 minutes) and `refresh` (valid 1 day).

3. **Send the access token** in the header of every protected request:

   ```
   Authorization: Bearer <access_token>
   ```

4. **Refresh** an expired access token: `POST /api/user/token/refresh/` with `{"refresh": "<refresh_token>"}`.

You can test protected endpoints in Postman, Insomnia or curl, or in Swagger UI via the **Authorize** button if it is shown.

## API endpoints

Base URL: `/api/`

### User

| Method    | Endpoint                | Description                         | Access        |
|-----------|-------------------------|-------------------------------------|---------------|
| POST      | `/user/register/`       | Create a new user                   | Anyone        |
| POST      | `/user/token/`          | Obtain JWT access and refresh token | Anyone        |
| POST      | `/user/token/refresh/`  | Refresh access token                | Anyone        |
| POST      | `/user/token/verify/`   | Verify a token                      | Anyone        |
| GET       | `/user/me/`             | Get your profile                    | Authenticated |
| PUT/PATCH | `/user/me/`             | Update your profile and password    | Authenticated |

### Airport

Resources marked **Admin write** can be read by anyone, but created, updated and deleted only by staff users.

| Resource       | Endpoint                         | Access                       |
|----------------|----------------------------------|------------------------------|
| Airports       | `/airport/airports/`             | Read: anyone, write: admin   |
| Routes         | `/airport/routes/`               | Read: anyone, write: admin   |
| Airplane types | `/airport/airplane-types/`       | Read: anyone, write: admin   |
| Airplanes      | `/airport/airplane/`             | Read: anyone, write: admin   |
| Airplane image | `/airport/airplane/{id}/upload_image/` (POST) | Admin           |
| Crews          | `/airport/crews/`                | Read: anyone, write: admin   |
| Flights        | `/airport/flights/`              | Read: anyone, write: admin   |
| Orders         | `/airport/orders/`               | Authenticated (own orders)   |
| Tickets        | `/airport/tickets/` (read only)  | Authenticated (own tickets)  |

Each resource supports the standard `GET` (list), `GET /{id}/` (detail), `POST`, `PUT`, `PATCH` and `DELETE`
(except tickets, which are read only and are created through orders).

### Documentation

| Endpoint                  | Description        |
|---------------------------|--------------------|
| `/api/schema/swagger-ui/` | Swagger UI         |
| `/api/schema/redoc/`      | ReDoc              |
| `/api/schema/`            | OpenAPI schema     |
| `/admin/`                 | Django admin panel |

### Example: create an order

`POST /api/airport/orders/` (authenticated)

```json
{
  "tickets": [
    { "row": 5, "seat": 1, "flight": 1 },
    { "row": 5, "seat": 2, "flight": 1 }
  ]
}
```

The order is created for the current user. If any ticket is invalid (seat taken, the same seat repeated in the request,
flight already departed, seat out of range, flight sold out), the API returns `400 Bad Request` with a description of the
problem, the whole order is rejected and nothing is saved.

Booking is safe under concurrent requests: if two users try to book the same seat at the same time, exactly one
order is created (`201`) and the other receives `400`.

## Filtering and search

Pagination is `limit` and `offset` based (default page size is 5), for example `/api/airport/flights/?limit=10&offset=20`.

| Endpoint                     | Query parameters                                                                                          |
|------------------------------|-----------------------------------------------------------------------------------------------------------|
| `/airport/airports/`         | `name`, `closest_big_city`                                                                                |
| `/airport/routes/`           | `source`, `destination` (by airport name)                                                                 |
| `/airport/airplane-types/`   | `name`                                                                                                    |
| `/airport/airplane/`         | `name`, `airplane_type`                                                                                   |
| `/airport/crews/`            | `search` (first or last name)                                                                             |
| `/airport/flights/`          | `source`, `destination`, `airplane_name`, `departure_time` (`YYYY-MM-DD`)                                 |
| `/airport/orders/`           | `date` (`YYYY-MM-DD`, order creation date)                                                                |

Text filters are case-insensitive and match partially. Example:

```
GET /api/airport/flights/?source=boryspil&destination=barcelona&departure_time=2026-10-05
```

## Business rules and validation

**Uniqueness (enforced by database constraints)**
- Airports are unique by name and closest big city
- Only one route can exist for the same source and destination airports
- Airplane type names and airplane names are unique

**Routes**
- Source and destination airports must be different
- Distance must be greater than 0
- Only one route per source/destination pair

**Flights**
- Departure time cannot be in the past
- Arrival time must be later than departure time
- An airplane cannot be scheduled for overlapping flights (30 minute buffer between flights for maintenance)
- A crew member cannot be assigned to overlapping flights (30 minute rest window)

**Tickets and orders**
- Row and seat must exist on the airplane (`1..rows`, `1..seats_in_row`)
- A seat on a flight can be sold only once, also when two users book it simultaneously (the flight row is locked during booking)
- The same seat cannot appear twice in one order request
- Tickets cannot be bought when the flight is sold out or has already departed
- An order with several tickets is created atomically: all tickets or none
- All validation problems are returned as `400` responses with a field-level error message, never as a `500`
- Users can see only their own orders and tickets

## Features

**Authentication and users**
- JWT authentication (access, refresh, verify) with refresh token rotation
- Login by email instead of username
- User registration and profile management (including password change)
- Role-based permissions: everyone can browse, only staff can modify the airport data
- Request throttling: 100 requests per day for anonymous users, 1000 per day for authenticated users

**Airport management**
- Full CRUD for airports, routes, airplane types, airplanes, crews and flights
- Routes with a source, a destination and a distance
- Creating airplanes with airplane types, automatic seat capacity calculation (`rows x seats_in_row`)
- Uploading airplane images (unique file names, served from `/media/`)
- Assigning crew members to flights
- Overlap protection for airplanes and crews, so one plane or person cannot be in two places at once

**Flights and booking**
- Flight list with route names, airplane, crew, total and available tickets (calculated in the database; the same
  value is also returned inside order and ticket details)
- Flight detail with the full route, airplane, crew and list of taken seats, so a client can draw a seat map
- Booking several tickets in one order
- Seat range, duplicate seat (also inside one request) and sold-out checks
- Concurrency-safe booking with a database transaction and row locking (`select_for_update`)
- Personal order history with ticket and flight details, filterable by date
- Personal read-only ticket list

**Search and filtering**
- Filter flights by departure airport, destination airport, airplane and departure date
- Filter airports by name and city, routes by source and destination, airplanes by name and type
- Search crew members by first or last name
- Limit and offset pagination

**Documentation and tooling**
- Interactive API documentation at `/api/schema/swagger-ui/` and `/api/schema/redoc/`, with documented filter parameters
- Django admin panel with tickets editable inline inside orders
- Query optimization with `select_related` and `prefetch_related`
- Automated API and model tests for the airport and user apps, including duplicate seats, sold-out and past flights,
  crew scheduling conflicts, write-permission checks for every endpoint and a concurrent booking test
- Dockerized setup with PostgreSQL, persistent database and media volumes
- Sample data fixture for quick start
- Code style tooling: flake8, black, ruff

## Running tests

With Docker:

```shell
docker-compose exec airport python manage.py test
```

Locally:

```shell
python manage.py test
```

The PostgreSQL user must be allowed to create databases, because Django creates a temporary test database.

The concurrent booking test uses several database connections and requires PostgreSQL (it is not meaningful on SQLite).

## Project structure

```
airport-management-api/
├── airport/                 # airports, routes, airplanes, crews, flights, orders, tickets
│   ├── models.py
│   ├── serializers.py
│   ├── views.py
│   ├── permissions.py
│   ├── urls.py
│   ├── admin.py
│   └── tests/
├── user/                    # custom email-based user model, registration, profile
├── airport_service/         # project settings and root urls
├── airport_test_data.json   # sample data fixture
├── docker-compose.yaml
├── Dockerfile
├── requirements.txt
├── .env.sample              # template for .env (the real .env is git-ignored)
└── manage.py
```