from django.db import transaction
from rest_framework import serializers, viewsets

from airport.models import Airport, Route, AirplaneType, Airplane, Crew, Flight, Order, Ticket
from user.serializers import UserSerializer


class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = ("id", "name", "closest_big_city")


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = ("id", "source", "destination", "distance")

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

    

class FlightListSerializer(serializers.ModelSerializer):
    route_source = serializers.CharField(source="route.source.name", read_only=True)
    route_destination = serializers.CharField(source="route.destination.name", read_only=True)
    airplane_name = serializers.CharField(source="airplane.name", read_only=True)
    crew = serializers.StringRelatedField(many=True, read_only=True)


    class Meta:
        model = Flight
        fields = ("id", "route_source", "route_destination", "airplane_name", "departure_time", "arrival_time", "crew")


class FlightDetailSerializer(serializers.ModelSerializer):
    route = RouteDetailSerializer()
    airplane = AirplaneSerializer()
    crew = CrewSerializer(many=True)

    class Meta:
        model = Flight
        fields = ("id", "route", "airplane", "departure_time", "arrival_time", "crew")


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
    flight = CompactFlightSerializer(read_only=True) # Вкладаємо компактний рейс

    class Meta:
        model = Ticket
        fields = ("id", "row", "seat", "flight")


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("row", "seat", "flight")

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
        for ticket_data in tickets_data:
            Ticket.objects.create(order=order, **ticket_data)
        return order



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


