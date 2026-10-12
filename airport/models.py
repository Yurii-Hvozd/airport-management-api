import pathlib
import uuid

from django.template.defaultfilters import slugify
from django.utils import timezone
from datetime import timedelta
from django.core.validators import MinValueValidator
from django.db import models
from django.core.exceptions import ValidationError

from django.conf import settings


class Airport(models.Model):
    name = models.CharField(max_length=200)
    closest_big_city = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.name} ({self.closest_big_city})"

class Route(models.Model):
    source = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='routes_from')
    destination = models.ForeignKey(Airport, on_delete=models.CASCADE, related_name='routes_to')
    distance = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.source.name} -> {self.destination.name}"

    def clean(self):
        if self.source == self.destination:
            raise ValidationError({
                "destination": "Source and destination airports cannot be the same."
            })
        if self.distance <= 0:
            raise ValidationError({
                "distance": "Distance must be greater than 0."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class AirplaneType(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


def bus_image_path(instance, filename) -> pathlib.Path:
    suffix = pathlib.Path(filename).suffix
    airplane_name = instance.name
    safe_info = slugify(airplane_name)
    new_filename = f"{safe_info}-{uuid.uuid4()}{suffix}"
    return pathlib.Path("upload/airplane/") / pathlib.Path(new_filename)


class Airplane(models.Model):
    name = models.CharField(max_length=200)
    rows = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    seats_in_row = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    airplane_type = models.ForeignKey(AirplaneType, on_delete=models.CASCADE)
    image = models.ImageField(upload_to=bus_image_path, null=True, blank=True)

    @property
    def capacity(self):
        return self.seats_in_row * self.rows

    def __str__(self):
        return f"{self.name} ({self.airplane_type.name})"


class Crew(models.Model):
    first_name = models.CharField(max_length=200, )
    last_name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Flight(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='flights')
    airplane = models.ForeignKey(Airplane, on_delete=models.CASCADE, related_name='flights')
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    crew = models.ManyToManyField(Crew, related_name='flights')

    def clean(self):
        super().clean()

        now = timezone.now()

        if self.departure_time and self.departure_time < now:
            raise ValidationError({"departure_time": "Flight departure time cannot be in the past."})

        if self.departure_time and self.arrival_time:
            if self.arrival_time <= self.departure_time:
                raise ValidationError({"arrival_time": "Arrival time must be later than departure time."})

            if self.airplane:
                buffer = timedelta(minutes=30)

                overlapping_flights = Flight.objects.filter(
                    airplane=self.airplane,
                    departure_time__lt=self.arrival_time + buffer,
                    arrival_time__gt=self.departure_time - buffer
                )

                if self.pk:
                    overlapping_flights = overlapping_flights.exclude(pk=self.pk)

                if overlapping_flights.exists():
                    raise ValidationError({
                        "airplane": "This airplane is already in flight or undergoing 30-minute maintenance during this time."
                    })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Flight {self.id}: {self.route} ({self.departure_time.strftime('%Y-%m-%d %H:%M')})"

class Order(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')

    def __str__(self):
        return f"Order {self.id} by {self.user.email} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"

    class Meta:
        ordering = ["-id"]


class Ticket(models.Model):
    row = models.IntegerField(validators=[MinValueValidator(1)])
    seat = models.IntegerField(validators=[MinValueValidator(1)])
    flight = models.ForeignKey(Flight, on_delete=models.CASCADE, related_name='tickets')
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='tickets')

    class Meta:
        unique_together = ("flight", "row", "seat")
        ordering = ["row", "seat"]


    @staticmethod
    def validate_ticket(row, seat, airplane, error_to_raise):
        if not (1 <= row <= airplane.rows):
            raise error_to_raise({"row": f"Row number must be in range [1, {airplane.rows}]."})
        if not (1 <= seat <= airplane.seats_in_row):
            raise error_to_raise({"seat": f"Seat number must be in range [1, {airplane.seats_in_row}]."})

    def clean(self):
        super().clean()

        if self.flight and hasattr(self.flight, 'airplane'):
            airplane = self.flight.airplane

            Ticket.validate_ticket(
                self.row,
                self.seat,
                airplane,
                ValidationError
            )

            existing_tickets_count = self.flight.tickets.exclude(pk=self.pk).count()
            if existing_tickets_count >= airplane.capacity:
                raise ValidationError({"flight": "All seats for this flight are already sold out."})

            if self.flight.departure_time < timezone.now():
                raise ValidationError({"flight": "Cannot purchase a ticket for a flight that has already departed."})


    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


    def __str__(self):
        return f"Ticket {self.id}: Flight {self.flight_id} (Row: {self.row}, Seat: {self.seat})"



