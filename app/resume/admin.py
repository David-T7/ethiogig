from django.contrib import admin
from core import models
# Register your models here.
admin.site.register(models.Resume)
admin.site.register(models.ScreeningResult)
admin.site.register(models.ScreeningConfig)