from datetime import timedelta
from copy import copy
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from airport.models import Airport, Route, AirplaneType, Airplane, Crew, Flight, Order, Ticket



class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ("id", "name", "closest_big_city")


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ("id", "source", "destination", "distance")

    def validate(self, attrs):
        # Отримуємо значення з attrs (це словник з валідованими даними, які прийшли від користувача)
        source = attrs.get("source")
        destination = attrs.get("destination")
        distance = attrs.get("distance")

        # 1. Перевірка на збіг аеропортів
        if source and destination and source == destination:
            raise serializers.ValidationError({
                "destination": "Source and destination airports cannot be the same."
            })

        # 2. Перевірка дистанції маршруту
        if distance is not None and distance <= 0:
            raise serializers.ValidationError({
                "distance": "Distance must be greater than 0."
            })

        return attrs


    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["source"] = instance.source.name
        data["destination"] = instance.destination.name
        return data


class RouteListSerializer(serializers.ModelSerializer):
    source = serializers.CharField(source="source.name", read_only=True)
    destination = serializers.CharField(source="destination.name", read_only=True)

    class Meta:
        model = Route
        fields = ("id", "source", "destination", "distance")

class RouteDetailSerializer(serializers.ModelSerializer):
    source = AirportSerializer()
    destination = AirportSerializer()

    class Meta:
        model = Route
        fields = ("id", "source", "destination", "distance")

class AirplaneTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AirplaneType
        fields = ("id", "name")


class AirplaneSerializer(serializers.ModelSerializer):

    class Meta:
        model = Airplane
        fields = ("id", "name", "rows", "seats_in_row", "airplane_type", "capacity")
        read_only_fields = ("capacity",)

class AirplaneListSerializer(serializers.ModelSerializer):

    airplane_type = serializers.SlugRelatedField(read_only=True, slug_field="name")
    class Meta:
        model = Airplane
        fields = ("id", "name", "rows", "seats_in_row", "airplane_type", "capacity")




class CrewSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Crew
        fields = ("id", "first_name", "last_name", "full_name")

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"


class FlightSerializer(serializers.ModelSerializer):
    route = serializers.PrimaryKeyRelatedField(
        queryset=Route.objects.select_related("source", "destination")
    )

    airplane = serializers.PrimaryKeyRelatedField(
        queryset=Airplane.objects.select_related(
            "airplane_type"
        )
    )

    class Meta:
        model = Flight
        fields = ("id", "route", "airplane", "departure_time", "arrival_time", "crew")

    def validate(self, attrs):
        instance_exists = self.instance is not None

        departure_time = attrs.get(
            "departure_time",
            self.instance.departure_time if instance_exists else None,
        )
        arrival_time = attrs.get(
            "arrival_time",
            self.instance.arrival_time if instance_exists else None,
        )


        if "crew" in attrs:
            crew_list = attrs.get("crew", [])
        elif instance_exists:
            crew_list = list(self.instance.crew.all())
        else:
            crew_list = []


        attrs_copy = attrs.copy()
        attrs_copy.pop("crew", None)

        if instance_exists:



            test_instance = copy(self.instance)
            for field, value in attrs_copy.items():
                setattr(test_instance, field, value)
        else:
            test_instance = Flight(**attrs_copy)

        try:
            test_instance.clean()
        except ValidationError as e:
            raise serializers.ValidationError(
                e.message_dict
                if hasattr(e, "message_dict")
                else {"non_field_errors": str(e)}
            )

        buffer = timedelta(minutes=30)

        if departure_time and arrival_time and crew_list:
            overlapping_flights = Flight.objects.filter(
                departure_time__lt=arrival_time + buffer,
                arrival_time__gt=departure_time - buffer,
            )

            if instance_exists:
                overlapping_flights = overlapping_flights.exclude(
                    pk=self.instance.pk
                )

            conflicting_flights = overlapping_flights.filter(
                crew__in=crew_list
            ).distinct()

            if conflicting_flights.exists():
                raise serializers.ValidationError(
                    {
                        "crew": "One or more crew members are already scheduled for another flight or are in their 30-minute rest window during this time."
                    }
                )

        return attrs


class FlightListSerializer(serializers.ModelSerializer):
    route_source = serializers.CharField(source="route.source.name", read_only=True)
    route_destination = serializers.CharField(source="route.destination.name", read_only=True)
    airplane_name = serializers.CharField(source="airplane.name", read_only=True)
    crew = serializers.StringRelatedField(many=True, read_only=True)
    tickets_total = serializers.IntegerField(source="airplane.capacity")
    tickets_available = serializers.IntegerField(read_only=True)


    class Meta:
        model = Flight
        fields = ("id", "route_source", "route_destination", "airplane_name", "departure_time", "arrival_time", "tickets_total", "tickets_available", "crew")


class TicketSeatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("row", "seat")


class FlightDetailSerializer(serializers.ModelSerializer):
    route = RouteDetailSerializer()
    airplane = AirplaneSerializer()
    crew = CrewSerializer(many=True)
    taken_seats = TicketSeatsSerializer(
        source="tickets",
        many=True,
        read_only=True
    )

    class Meta:
        model = Flight
        fields = ("id", "route", "airplane", "departure_time", "arrival_time", "crew", "taken_seats")


class CompactFlightSerializer(serializers.ModelSerializer):
    from_destination = serializers.CharField(source="route.source.name", read_only=True)
    to_destination = serializers.CharField(source="route.destination.name", read_only=True)

    class Meta:
        model = Flight
        fields = ("id", "from_destination", "to_destination", "departure_time")


class TicketSerializer(serializers.ModelSerializer):
    flight = CompactFlightSerializer(read_only=True)
    passenger_name = serializers.CharField(source="order.user.get_full_name", read_only=True)

    class Meta:
        model = Ticket
        fields = ("id", "passenger_name", "row", "seat", "flight")
        read_only_fields = ("order", )




class TicketDetailSerializer(serializers.ModelSerializer):
    flight = FlightListSerializer()
    order_id = serializers.IntegerField(source="order.id", read_only=True)
    passenger_name = serializers.CharField(source="order.user.get_full_name", read_only=True)

    class Meta:
        model = Ticket
        fields = ("id", "order_id", "passenger_name", "row", "seat", "flight")
        read_only_fields = ("order", )



class OrderTicketListSerializer(serializers.ModelSerializer):
    flight = CompactFlightSerializer(read_only=True)

    class Meta:
        model = Ticket
        fields = ("id", "row", "seat", "flight")


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("row", "seat", "flight")
        validators = [
            UniqueTogetherValidator(
                queryset=Ticket.objects.all(),
                fields=("flight", "row", "seat"),
            )
        ]

    def validate(self, attrs):
        flight = attrs["flight"]
        airplane = flight.airplane


        if not (1 <= attrs["row"] <= airplane.rows):
            raise serializers.ValidationError({
                "row": f"Row number must be in range [1, {airplane.rows}]."
            })


        if not (1 <= attrs["seat"] <= airplane.seats_in_row):
            raise serializers.ValidationError({
                "seat": f"Seat number must be in range [1, {airplane.seats_in_row}]."
            })


        current_ticket_pk = self.instance.pk if self.instance else None


        existing_tickets_count = flight.tickets.exclude(pk=current_ticket_pk).count()
        if existing_tickets_count >= airplane.capacity:
            raise serializers.ValidationError({
                "flight": "All seats for this flight are already sold out."
            })


        if flight.departure_time < timezone.now():
            raise serializers.ValidationError({
                "flight": "Cannot purchase a ticket for a flight that has already departed."
            })

        return attrs


class OrderSerializer(serializers.ModelSerializer):
    passenger_name = serializers.CharField(source="user.get_full_name", read_only=True)
    tickets = TicketCreateSerializer(many=True, read_only=False, allow_empty=False)

    class Meta:
        model = Order
        fields = ("id", "passenger_name" ,"created_at", "tickets")


    @transaction.atomic
    def create(self, validated_data):
        tickets_data = validated_data.pop("tickets", [])
        order = Order.objects.create(**validated_data)
        try:
            for ticket_data in tickets_data:
                Ticket.objects.create(order=order, **ticket_data)
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)

        return order


class TicketListSerializer(serializers.ModelSerializer):
    flight = CompactFlightSerializer(read_only=True)
    class Meta:
        model = Ticket
        fields = ("id", "row", "seat", "flight")

class OrderListSerializer(serializers.ModelSerializer):
    passenger_name = serializers.CharField(source="user.get_full_name", read_only=True)
    tickets = TicketListSerializer(many=True, read_only=True)
    class Meta:
        model = Order
        fields = ("id", "passenger_name", "created_at", "tickets")


class OrderTicketDetailSerializer(serializers.ModelSerializer):
    flight = FlightListSerializer()

    class Meta:
        model = Ticket
        fields = ("id", "row", "seat", "flight")



class OrderDetailSerializer(serializers.ModelSerializer):

    passenger_name = serializers.CharField(source="user.get_full_name", read_only=True)

    tickets = OrderTicketDetailSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ("id", "passenger_name", "created_at", "tickets")


