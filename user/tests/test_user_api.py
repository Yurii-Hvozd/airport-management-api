from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

CREATE_USER_URL = reverse("user:create")
MANAGE_USER_URL = reverse("user:manage")


class PublicUserApiTests(APITestCase):
    def setUp(self):
        self.user_data = {
            "email": "test@example.com",
            "password": "password123",
            "username": "testuser",
        }

    def test_create_user_success(self):
        response = self.client.post(CREATE_USER_URL, self.user_data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user_exists = (
            get_user_model().objects.filter(email=self.user_data["email"]).exists()
        )
        self.assertTrue(user_exists)

    def test_anonymous_cannot_access_manage_profile(self):
        response = self.client.get(MANAGE_USER_URL)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateUserApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="user@example.com",
            password="securepassword123",
        )
        self.client.force_authenticate(user=self.user)

    def test_retrieve_profile_success(self):
        response = self.client.get(MANAGE_USER_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

    def test_update_profile_success(self):
        payload = {"email": "user@exampleexample.com"}
        response = self.client.patch(MANAGE_USER_URL, payload)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, payload["email"])
