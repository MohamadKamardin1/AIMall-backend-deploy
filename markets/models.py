from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class Market(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    address = models.TextField(blank=True)
    contact_phone = models.CharField(max_length=13, blank=True)
    is_active = models.BooleanField(default=True)
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    market_days = models.CharField(max_length=100, blank=True, help_text="e.g., Monday-Friday, Daily")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'markets'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.location}"

class MarketZone(models.Model):
    """Different zones within a market (e.g., Sokoni la Matunda, Sokoni la Samaki)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    market = models.ForeignKey(Market, on_delete=models.CASCADE, related_name='zones')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    zone_type = models.CharField(max_length=100, blank=True, help_text="e.g., Fruits, Vegetables, Fish, Meat")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'market_zones'
        unique_together = ['market', 'name']
        ordering = ['market', 'name']
    
    def __str__(self):
        return f"{self.market.name} - {self.name}"