from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from .models import Market, MarketZone

class MarketZoneInline(admin.TabularInline):
    model = MarketZone
    extra = 1
    fields = ['name', 'zone_type', 'is_active']

@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'is_active']
    search_fields = ['name', 'location']
    inlines = [MarketZoneInline]
    
    # CORRECTED: Simple actions list
    actions = ['activate_markets', 'deactivate_markets']
    
    def activate_markets(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} markets.', messages.SUCCESS)
    activate_markets.short_description = "Activate selected markets"
    
    def deactivate_markets(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} markets.', messages.WARNING)
    deactivate_markets.short_description = "Deactivate selected markets"

@admin.register(MarketZone)
class MarketZoneAdmin(admin.ModelAdmin):
    list_display = ['name', 'market', 'zone_type', 'is_active']
    search_fields = ['name', 'market__name']
    
    # CORRECTED: Simple actions list
    actions = ['activate_zones', 'deactivate_zones']
    
    def activate_zones(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Activated {updated} zones.', messages.SUCCESS)
    activate_zones.short_description = "Activate selected zones"
    
    def deactivate_zones(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Deactivated {updated} zones.', messages.WARNING)
    deactivate_zones.short_description = "Deactivate selected zones"