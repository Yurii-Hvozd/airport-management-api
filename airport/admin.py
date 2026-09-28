from django.contrib import admin

from airport.models import Airport, Flight, Ticket, Airplane, AirplaneType, Order, Route, Crew

admin.site.register(Airport)
admin.site.register(Route)
admin.site.register(Crew)
admin.site.register(Flight)
admin.site.register(Ticket)
admin.site.register(Airplane)
admin.site.register(AirplaneType)
admin.site.register(Order)
