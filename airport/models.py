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
    distance = models.IntegerField()

    def __str__(self):
        return f"{self.source.name} -> {self.destination.name}"

class AirplaneType(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Airplane(models.Model):
    name = models.CharField(max_length=200)
    rows = models.IntegerField()
    seats_in_row = models.IntegerField()
    airplane_type = models.ForeignKey(AirplaneType, on_delete=models.CASCADE)

    @property
    def capacity(self):
        return self.seats_in_row * self.rows

    def __str__(self):
        return f"{self.name} ({self.airplane_type.name})"


class Crew(models.Model):
    first_name = models.CharField(max_length=200)
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

        if self.departure_time and self.arrival_time:
            if self.arrival_time <= self.departure_time:
                raise ValidationError({
                    'arrival_time': "Arrival time must be later than departure time."
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



class Ticket(models.Model):
    row = models.IntegerField()
    seat = models.IntegerField()
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
        if self.flight and hasattr(self.flight, 'airplane'):
            Ticket.validate_ticket(
                self.row,
                self.seat,
                self.flight.airplane,
                ValidationError)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Ticket {self.id}: Flight {self.flight_id} (Row: {self.row}, Seat: {self.seat})"



