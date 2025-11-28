# order/models.py
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class Order(models.Model):
    ORDER_STATUS = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready for Pickup'),
        ('assigned', 'Assigned to Driver'),
        ('picked_up', 'Picked Up'),
        ('on_the_way', 'On the Way'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('failed', 'Delivery Failed'),
    ]
    
    PAYMENT_METHODS = [
        ('cash_on_delivery', 'Cash on Delivery'),
        ('mobile_money', 'Mobile Money'),
        ('card', 'Credit/Debit Card'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_number = models.CharField(max_length=20, unique=True)
    customer = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='order')
    
    # Delivery Information
    delivery_address = models.ForeignKey('location.CustomerAddress', on_delete=models.CASCADE, related_name='order')
    delivery_time_slot = models.ForeignKey('location.DeliveryTimeSlot', on_delete=models.SET_NULL, null=True)
    scheduled_delivery_date = models.DateField()
    scheduled_delivery_time = models.CharField(max_length=100)
    
    # Driver Information
    driver = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='delivery_order')
    
    # Order Details
    items_total = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(0)])
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Payment Information
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash_on_delivery')
    is_paid = models.BooleanField(default=False)
    payment_reference = models.CharField(max_length=255, blank=True)
    
    # Status Tracking
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default='pending')
    cancellation_reason = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'order'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Order #{self.order_number} - {self.customer.phone_number}"
    
    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)
    
    def _generate_order_number(self):
        from django.utils import timezone
        timestamp = timezone.now().strftime('%Y%m%d')
        last_order = Order.objects.filter(
            order_number__startswith=f'ORD{timestamp}'
        ).order_by('-order_number').first()
        
        if last_order:
            last_num = int(last_order.order_number[-4:])
            new_num = last_num + 1
        else:
            new_num = 1
        
        return f"ORD{timestamp}{new_num:04d}"
    
    def calculate_totals(self):
        """Calculate order totals"""
        items_total = sum(item.total_price for item in self.items.all())
        self.items_total = items_total
        self.total_amount = items_total + self.delivery_fee + self.service_fee - self.discount_amount

class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey('products.ProductVariant', on_delete=models.CASCADE)
    measurement_unit = models.ForeignKey('products.MeasurementUnit', on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(0.001)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Addons
    selected_addons = models.ManyToManyField('products.ProductAddon', blank=True)
    addons_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Special instructions
    special_instructions = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_items'
    
    def __str__(self):
        return f"{self.quantity} x {self.product_variant.product_template.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = (self.unit_price * self.quantity) + self.addons_total
        super().save(*args, **kwargs)

class ordertatusUpdate(models.Model):
    """Track order status changes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_updates')
    old_status = models.CharField(max_length=20, choices=Order.ORDER_STATUS)
    new_status = models.CharField(max_length=20, choices=Order.ORDER_STATUS)
    updated_by = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'order_status_updates'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.order.order_number} - {self.old_status} → {self.new_status}"

class Cart(models.Model):
    """Shopping cart for customers"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='cart')
    market = models.ForeignKey('markets.Market', on_delete=models.CASCADE, null=True, blank=True)
    delivery_address = models.ForeignKey('location.CustomerAddress', on_delete=models.SET_NULL, null=True, blank=True)
    delivery_time_slot = models.ForeignKey('location.DeliveryTimeSlot', on_delete=models.SET_NULL, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'carts'
    
    def __str__(self):
        return f"Cart - {self.customer.phone_number}"
    
    @property
    def items_count(self):
        return self.items.count()
    
    @property
    def subtotal(self):
        return sum(item.total_price for item in self.items.all())
    
    @property
    def delivery_fee(self):
        if self.delivery_address and self.delivery_address.delivery_zone:
            return self.delivery_address.delivery_zone.calculate_delivery_fee(
                self.delivery_address.latitude,
                self.delivery_address.longitude
            )
        return Decimal('0.00')
    
    @property
    def total(self):
        return self.subtotal + self.delivery_fee

class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey('products.ProductVariant', on_delete=models.CASCADE)
    measurement_unit = models.ForeignKey('products.MeasurementUnit', on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(0.001)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    total_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Addons
    selected_addons = models.ManyToManyField('products.ProductAddon', blank=True)
    addons_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Special instructions
    special_instructions = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'cart_items'
        unique_together = ['cart', 'product_variant', 'measurement_unit']
    
    def __str__(self):
        return f"{self.quantity} x {self.product_variant.product_template.name}"
    
    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = (self.unit_price * self.quantity) + self.addons_total
        super().save(*args, **kwargs)