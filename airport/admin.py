from django.contrib import admin

from airport.models import (
    Airplane,
    AirplaneType,
    Airport,
    Crew,
    Flight,
    Order,
    Route,
    Ticket,
)


class TicketInline(admin.TabularInline):
    model = Ticket
    extra = 1


class OrderAdmin(admin.ModelAdmin):
    inlines = (TicketInline,)


admin.site.register(Airport)
admin.site.register(Route)
admin.site.register(Crew)
admin.site.register(Flight)
admin.site.register(Ticket)
admin.site.register(Airplane)
admin.site.register(AirplaneType)
admin.site.register(Order, OrderAdmin)
