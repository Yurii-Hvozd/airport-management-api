from rest_framework import viewsets

from airport.models import Airport, Route, Airplane, AirplaneType, Crew, Flight, Order, Ticket
from airport.serializers import AirportSerializer, RouteSerializer, AirplaneSerializer, AirplaneTypeSerializer, \
    CrewSerializer, FlightSerializer, OrderSerializer, TicketSerializer, RouteListSerializer, RouteDetailSerializer, \
    FlightListSerializer, FlightDetailSerializer, AirplaneListSerializer, TicketDetailSerializer, OrderDetailSerializer
from rest_framework import viewsets, mixins

class AirportViewSet(viewsets.ModelViewSet):
    queryset = Airport.objects.all()
    serializer_class = AirportSerializer

class RouteViewSet(viewsets.ModelViewSet):
    queryset = Route.objects.all()
    serializer_class = RouteSerializer

    def get_queryset(self):
        queryset = self.queryset
        if self.action in ("list", "retrieve"):
            return queryset.select_related("source", "destination")
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return RouteListSerializer
        elif self.action == "retrieve":
            return RouteDetailSerializer
        return RouteSerializer


class AirplaneTypeViewSet(viewsets.ModelViewSet):
    queryset = AirplaneType.objects.all()
    serializer_class = AirplaneTypeSerializer


class AirplaneViewSet(viewsets.ModelViewSet):
    queryset = Airplane.objects.all()
    serializer_class = AirplaneSerializer

    def get_queryset(self):
        queryset = self.queryset
        if self.action in ("list", "retrieve"):
            return queryset.select_related("airplane_type")
        return queryset


    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return AirplaneListSerializer
        return AirplaneSerializer


class CrewViewSet(viewsets.ModelViewSet):
    queryset = Crew.objects.all()
    serializer_class = CrewSerializer



class FlightViewSet(viewsets.ModelViewSet):
    queryset = Flight.objects.all()

    def get_serializer_class(self):

        if self.action == "list":
            return FlightListSerializer
        elif self.action == "retrieve":
            return FlightDetailSerializer
        return FlightSerializer

    def get_queryset(self):
        queryset = self.queryset
        if self.action in ("list", "retrieve"):
            return queryset.select_related("route__source", "route__destination", "airplane__airplane_type").prefetch_related("crew")
        return queryset

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer


    def get_queryset(self):
        queryset = self.queryset.filter(user=self.request.user)

        if self.action in ("list", "retrieve"):
            return queryset.select_related("user").prefetch_related(
                "tickets__flight__route__source",
                "tickets__flight__route__destination",
                "tickets__flight__airplane",
                "tickets__flight__crew",
            )
        return queryset

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return OrderSerializer
        elif self.action == "retrieve":
            return OrderDetailSerializer
        return OrderSerializer

class TicketViewSet(    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet):
    queryset = Ticket.objects.all()
    serializer_class = TicketSerializer

    def get_serializer_class(self):
        if self.action == "list":
            return TicketSerializer
        elif self.action == "retrieve":
            return TicketDetailSerializer
        return TicketSerializer

    def get_queryset(self):
        queryset = self.queryset.filter(order__user=self.request.user)

        if self.action in ("list", "retrieve"):
            return queryset.select_related(
                "flight__airplane",
                "order__user",
                "flight__route__source",
                "flight__route__destination"
            ).prefetch_related("flight__crew")

        return queryset