# location/models.py
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class DeliveryTimeSlot(models.Model):
    """Delivery time slots (morning and afternoon)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, help_text="e.g., Morning Delivery, Afternoon Delivery")
    cut_off_time = models.TimeField(help_text="Order cut-off time for this slot")
    delivery_start_time = models.TimeField(help_text="When delivery starts for this slot")
    delivery_end_time = models.TimeField(help_text="When delivery ends for this slot")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'delivery_time_slots'
        ordering = ['cut_off_time']
    
    def __str__(self):
        return f"{self.name} (Cut-off: {self.cut_off_time})"

class DeliveryZone(models.Model):
    """Delivery zones with pricing"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    market = models.ForeignKey('markets.Market', on_delete=models.CASCADE, related_name='delivery_zones')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    # Pricing
    base_delivery_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Base delivery fee for this zone"
    )
    
    # Location boundaries (for automatic distance calculation)
    min_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    max_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    min_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    max_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Manual override
    is_manual_pricing = models.BooleanField(
        default=False,
        help_text="If True, use manual pricing instead of distance calculation"
    )
    manual_delivery_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        null=True, 
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Manual delivery fee (overrides calculation)"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'delivery_zones'
        unique_together = ['market', 'name']
        ordering = ['market', 'name']
    
    def __str__(self):
        return f"{self.market.name} - {self.name}"
    
    def calculate_delivery_fee(self, customer_lat, customer_lng):
        """Calculate delivery fee based on distance or manual pricing"""
        if self.is_manual_pricing and self.manual_delivery_fee:
            return self.manual_delivery_fee
        
        # Calculate distance-based fee
        if customer_lat and customer_lng and self.market.latitude and self.market.longitude:
            distance = self._calculate_distance(
                float(customer_lat), float(customer_lng),
                float(self.market.latitude), float(self.market.longitude)
            )
            # Simple pricing: base fee + distance rate
            distance_rate = Decimal('0.5')  # TZS per km
            calculated_fee = self.base_delivery_fee + (distance * distance_rate)
            return max(self.base_delivery_fee, calculated_fee)
        
        return self.base_delivery_fee
    
    def _calculate_distance(self, lat1, lng1, lat2, lng2):
        """Calculate distance between two points using Haversine formula"""
        from math import radians, sin, cos, sqrt, atan2
        
        R = 6371  # Earth radius in km
        
        lat1_rad = radians(lat1)
        lon1_rad = radians(lng1)
        lat2_rad = radians(lat2)
        lon2_rad = radians(lng2)
        
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        a = sin(dlat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c
        
        return Decimal(distance)

class CustomerAddress(models.Model):
    """Customer delivery addresses"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='addresses')
    market = models.ForeignKey('markets.Market', on_delete=models.CASCADE, related_name='customer_addresses')
    delivery_zone = models.ForeignKey(DeliveryZone, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Address details
    label = models.CharField(max_length=100, help_text="e.g., Home, Work, Office")
    street_address = models.TextField()
    landmark = models.CharField(max_length=255, blank=True, help_text="Nearby landmark")
    
    # Location coordinates
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Contact info
    recipient_name = models.CharField(max_length=255)
    recipient_phone = models.CharField(max_length=13)
    additional_notes = models.TextField(blank=True)
    
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customer_addresses'
        ordering = ['-is_default', 'label']
    
    def __str__(self):
        return f"{self.customer.phone_number} - {self.label}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default address per customer
        if self.is_default:
            CustomerAddress.objects.filter(
                customer=self.customer, 
                is_default=True
            ).update(is_default=False)
        super().save(*args, **kwargs)