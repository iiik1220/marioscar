from django.contrib import admin
from .models import (
    CarModel, CarImage, CarUnit, Client, Reservation, Payment,
    FinanceEntry, MaintenanceRecord, AccidentRecord, SparePartRecord
)

admin.site.register(CarModel)
admin.site.register(CarImage)
admin.site.register(CarUnit)
admin.site.register(Client)
admin.site.register(Reservation)
admin.site.register(Payment)
admin.site.register(FinanceEntry)
admin.site.register(MaintenanceRecord)
admin.site.register(AccidentRecord)
admin.site.register(SparePartRecord)