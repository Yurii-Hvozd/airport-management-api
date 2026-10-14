from airport.serializers import AirportSerializer

import threading
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from airport.models import (Airplane, AirplaneType, Airport, Crew, Flight,
                            Order, Route, Ticket)

AIRPORT_URL = reverse("airport:airport-list")
FLIGHT_URL = reverse("airport:flight-list")
ORDER_URL = reverse("airport:order-list")


class UnauthenticatedAirportApiTests(APITestCase):
    def setUp(self):
        self.airport = Airport.objects.create(
            name="Boryspil International", closest_big_city="Kyiv"
        )

    def test_auth_not_required_for_list_airports(self):
        response = self.client.get(AIRPORT_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auth_required_to_create_airport(self):
        payload = {"name": "Lviv Airport", "closest_big_city": "Lviv"}
        response = self.client.post(AIRPORT_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminAirportApiTests(APITestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            email="admin_airport@test.com", password="adminpassword123"
        )
        self.client.force_authenticate(user=self.admin_user)

        self.airport1 = Airport.objects.create(name="Boryspil", closest_big_city="Kyiv")
        self.airport2 = Airport.objects.create(
            name="Lviv Airport", closest_big_city="Lviv"
        )

    def test_admin_can_create_airport(self):
        payload = {"name": "Odesa Airport", "closest_big_city": "Odesa"}
        response = self.client.post(AIRPORT_URL, payload)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Airport.objects.filter(name="Odesa Airport").exists())

    def test_filter_airports_by_name(self):
        response = self.client.get(AIRPORT_URL, {"name": "Boryspil"})

        results = response.data.get("results", response.data)

        serializer1 = AirportSerializer(self.airport1)
        serializer2 = AirportSerializer(self.airport2)

        self.assertIn(serializer1.data, results)
        self.assertNotIn(serializer2.data, results)


class FlightApiTests(APITestCase):
    def setUp(self):
        self.airplane_type = AirplaneType.objects.create(name="Boeing")
        self.airplane = Airplane.objects.create(
            name="737-800", rows=2, seats_in_row=5, airplane_type=self.airplane_type
        )
        self.airport_from = Airport.objects.create(
            name="Kyiv Airport", closest_big_city="Kyiv"
        )
        self.airport_to = Airport.objects.create(
            name="Lviv Airport", closest_big_city="Lviv"
        )
        self.route = Route.objects.create(
            source=self.airport_from, destination=self.airport_to, distance=500
        )

        self.flight = Flight.objects.create(
            route=self.route,
            airplane=self.airplane,
            departure_time="2026-12-25T12:00:00Z",
            arrival_time="2026-12-25T14:00:00Z",
        )

    def test_tickets_available_calculation(self):
        response = self.client.get(FLIGHT_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        if isinstance(response.data, dict) and "results" in response.data:
            flights_list = response.data["results"]
        else:
            flights_list = response.data

        self.assertEqual(flights_list[0]["tickets_available"], 10)


class AirplaneImageUploadTests(APITestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            email="admin_image@test.com", password="password"
        )
        self.client.force_authenticate(user=self.admin_user)
        self.airplane_type = AirplaneType.objects.create(name="Airbus")
        self.airplane = Airplane.objects.create(
            name="A320", rows=10, seats_in_row=6, airplane_type=self.airplane_type
        )
        self.upload_url = reverse(
            "airport:airplane-upload-image", args=[self.airplane.id]
        )

    def test_upload_image_bad_request_with_invalid_data(self):
        response = self.client.post(
            self.upload_url, data={"image": "not_an_image"}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OrderApiTests(APITestCase):
    def setUp(self):
        self.user1 = get_user_model().objects.create_user(
            email="user1@test.com", password="password123"
        )
        self.user2 = get_user_model().objects.create_user(
            email="user2@test.com", password="password123"
        )

        self.order1 = Order.objects.create(user=self.user1)
        self.order2 = Order.objects.create(user=self.user2)

        # Створюємо рейс, щоб передати його для валідації квитків
        self.airplane_type = AirplaneType.objects.create(name="Boeing")
        self.airplane = Airplane.objects.create(
            name="737", rows=10, seats_in_row=5, airplane_type=self.airplane_type
        )
        self.airport_from = Airport.objects.create(name="Kyiv", closest_big_city="Kyiv")
        self.airport_to = Airport.objects.create(name="Lviv", closest_big_city="Lviv")
        self.route = Route.objects.create(
            source=self.airport_from, destination=self.airport_to, distance=500
        )
        self.flight = Flight.objects.create(
            route=self.route,
            airplane=self.airplane,
            departure_time="2026-12-25T12:00:00Z",
            arrival_time="2026-12-25T14:00:00Z",
        )

    def test_user_can_see_only_their_own_orders(self):
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(ORDER_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        if isinstance(response.data, dict) and "results" in response.data:
            orders_list = response.data["results"]
        else:
            orders_list = response.data

        if isinstance(orders_list, list):
            self.assertEqual(len(orders_list), 1)
            self.assertEqual(orders_list[0]["id"], self.order1.id)
        else:
            self.assertEqual(orders_list["id"], self.order1.id)

    def test_create_order_automatically_sets_user(self):
        self.client.force_authenticate(user=self.user1)
        payload = {"tickets": [{"row": 1, "seat": 1, "flight": self.flight.id}]}

        response = self.client.post(ORDER_URL, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        latest_order = Order.objects.latest("id")
        self.assertEqual(latest_order.user, self.user1)

def make_flight(rows=1, seats_in_row=2, hours_ahead=24, name="Plane-1", crew=None):
    atype, _ = AirplaneType.objects.get_or_create(name="Boeing")
    plane = Airplane.objects.create(
        name=name, rows=rows, seats_in_row=seats_in_row, airplane_type=atype
    )
    a, _ = Airport.objects.get_or_create(name="A", closest_big_city="CityA")
    b, _ = Airport.objects.get_or_create(name="B", closest_big_city="CityB")
    route, _ = Route.objects.get_or_create(source=a, destination=b, defaults={"distance": 100})
    start = timezone.now() + timedelta(hours=hours_ahead)
    flight = Flight.objects.create(
        route=route, airplane=plane, departure_time=start,
        arrival_time=start + timedelta(hours=2),
    )
    if crew:
        flight.crew.set(crew)
    return flight


def order_payload(flight, *seats):
    return {"tickets": [{"flight": flight.id, "row": r, "seat": s} for r, s in seats]}


class BookingValidationTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(email="u@test.com", password="pass12345")
        self.client.force_authenticate(self.user)
        self.flight = make_flight()           # 1 ряд x 2 місця

    def test_duplicate_seats_in_one_payload_return_400(self):
        r = self.client.post(ORDER_URL, order_payload(self.flight, (1, 1), (1, 1)), format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Ticket.objects.count(), 0)

    def test_already_taken_seat_returns_400(self):
        order = Order.objects.create(user=self.user)
        Ticket.objects.create(order=order, flight=self.flight, row=1, seat=1)
        r = self.client.post(ORDER_URL, order_payload(self.flight, (1, 1)), format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_full_flight_returns_400(self):
        order = Order.objects.create(user=self.user)
        for seat in (1, 2):
            Ticket.objects.create(order=order, flight=self.flight, row=1, seat=seat)
        r = self.client.post(ORDER_URL, order_payload(self.flight, (1, 1)), format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Ticket.objects.count(), 2)

    def test_seat_out_of_range_returns_400(self):
        r = self.client.post(ORDER_URL, order_payload(self.flight, (1, 3)), format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_past_flight_returns_400(self):
        Flight.objects.filter(pk=self.flight.pk).update(
            departure_time=timezone.now() - timedelta(hours=1)
        )  # через .update(), бо Flight.save() не дозволяє минулі дати
        r = self.client.post(ORDER_URL, order_payload(self.flight, (1, 1)), format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_failed_order_leaves_no_partial_data(self):
        # перший квиток валідний, другий — поза діапазоном → весь заказ відкотити
        r = self.client.post(ORDER_URL, order_payload(self.flight, (1, 1), (9, 9)), format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)


class TicketsAvailableEverywhereTests(APITestCase):
    def test_tickets_available_present_in_order_and_ticket_details(self):
        user = get_user_model().objects.create_user(email="u@test.com", password="pass12345")
        self.client.force_authenticate(user)
        flight = make_flight(rows=2, seats_in_row=5)           # 10 місць
        self.client.post(ORDER_URL, order_payload(flight, (1, 1), (1, 2)), format="json")

        order_id = Order.objects.get().id
        r = self.client.get(reverse("airport:order-detail", args=[order_id]))
        self.assertEqual(r.data["tickets"][0]["flight"]["tickets_available"], 8)

        ticket_id = Ticket.objects.first().id
        r = self.client.get(reverse("airport:ticket-detail", args=[ticket_id]))
        self.assertEqual(r.data["flight"]["tickets_available"], 8)


class CrewSchedulingTests(APITestCase):
    def test_crew_member_cannot_be_on_overlapping_flights(self):
        admin = get_user_model().objects.create_superuser(email="a@test.com", password="pass12345")
        self.client.force_authenticate(admin)
        crew = Crew.objects.create(first_name="John", last_name="Doe")
        first = make_flight(name="P1", crew=[crew])
        other_plane = Airplane.objects.create(
            name="P2", rows=1, seats_in_row=1, airplane_type=first.airplane.airplane_type
        )
        payload = {
            "route": first.route.id, "airplane": other_plane.id,
            "departure_time": first.departure_time.isoformat(),
            "arrival_time": first.arrival_time.isoformat(),
            "crew": [crew.id],
        }
        r = self.client.post(FLIGHT_URL, payload, format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("crew", r.data)


class WritePermissionTests(APITestCase):
    LIST_ENDPOINTS = ["airport-list", "route-list", "airplanetype-list",
                      "airplane-list", "crew-list", "flight-list"]

    def setUp(self):
        self.user = get_user_model().objects.create_user(email="u@test.com", password="pass12345")
        self.flight = make_flight()

    def _check(self, expected):
        urls = [(reverse(f"airport:{n}"), ["post"]) for n in self.LIST_ENDPOINTS]
        details = [reverse(f"airport:{n.replace('-list', '-detail')}", args=[1])
                   for n in self.LIST_ENDPOINTS]
        urls += [(u, ["put", "patch", "delete"]) for u in details]
        urls.append((reverse("airport:airplane-upload-image", args=[self.flight.airplane.id]), ["post"]))
        for url, methods in urls:
            for m in methods:
                with self.subTest(url=url, method=m):
                    self.assertEqual(getattr(self.client, m)(url, {}, format="json").status_code, expected)

    def test_anonymous_gets_401_on_all_write_endpoints(self):
        self._check(status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_gets_403_on_all_write_endpoints(self):
        self.client.force_authenticate(self.user)
        self._check(status.HTTP_403_FORBIDDEN)


class ConcurrentBookingTests(TransactionTestCase):
    """TransactionTestCase потрібен, бо потоки мають бачити закомічені дані.
    Працює на PostgreSQL (як у проєкті)."""

    def test_two_parallel_bookings_of_same_seat_only_one_wins(self):
        User = get_user_model()
        users = [User.objects.create_user(email=f"u{i}@test.com", password="pass12345") for i in range(2)]
        flight = make_flight()
        barrier, results = threading.Barrier(2), []

        def book(user):
            try:
                client = APIClient()
                client.force_authenticate(user)
                barrier.wait()                      # стартуємо одночасно
                r = client.post(ORDER_URL, order_payload(flight, (1, 1)), format="json")
                results.append(r.status_code)
            finally:
                connection.close()                  # кожен потік має своє з'єднання

        threads = [threading.Thread(target=book, args=(u,)) for u in users]
        [t.start() for t in threads]
        [t.join() for t in threads]

        self.assertEqual(sorted(results), [201, 400])
        self.assertEqual(Ticket.objects.filter(flight=flight, row=1, seat=1).count(), 1)