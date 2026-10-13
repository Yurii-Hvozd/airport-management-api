from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from airport.models import Airplane, AirplaneType, Airport, Flight, Order, Route
from airport.serializers import AirportSerializer

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
