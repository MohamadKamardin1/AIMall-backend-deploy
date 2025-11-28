# admin_dashboard/views.py
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from unicodedata import decimal
from django.utils import timezone
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test, login_required
from django.db.models import Sum, Prefetch, Avg, Count, Q
from django.db import models
from django.http import JsonResponse
from django.core.paginator import Paginator

# MODELS
from accounts.models import SecurityQuestion, User, Customer, UserSecurityAnswer, Vendor, Driver, AdminProfile
from location.models import DeliveryZone
from products.models import Category, MeasurementUnitType, ProductAddonMapping, ProductTemplate, ProductVariant, MeasurementUnit, GlobalSetting, UnitPrice
from markets.models import Market, MarketZone
from order.models import Order, OrderItem

# ============================================
# HELPER FUNCTION
# ============================================
def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

# ============================================
# DASHBOARD
# ============================================
@login_required
@user_passes_test(is_admin)
def dashboard(request):
    """Admin Dashboard Overview"""
    # Basic statistics
    total_customers = Customer.objects.count()
    total_vendors = Vendor.objects.count()
    total_drivers = Driver.objects.count()
    total_products = ProductTemplate.objects.count()
    total_order = Order.objects.count()
    
    # Revenue calculations
    revenue_today = Order.objects.filter(
        created_at__date=timezone.now().date(),
        status__in=['completed', 'delivered']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    revenue_week = Order.objects.filter(
        created_at__gte=timezone.now()-timedelta(days=7),
        status__in=['completed', 'delivered']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    revenue_month = Order.objects.filter(
        created_at__gte=timezone.now()-timedelta(days=30),
        status__in=['completed', 'delivered']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    # Pending verifications
    pending_vendors = Vendor.objects.filter(is_verified=False).count()
    pending_drivers = Driver.objects.filter(is_verified=False).count()
    
    # Recent order
    recent_order = Order.objects.select_related('customer').order_by('-created_at')[:10]
    
    # Recent activities (you can create an ActivityLog model later)
    recent_activities = []
    
    stats = {
        'total_customers': total_customers,
        'total_vendors': total_vendors,
        'total_drivers': total_drivers,
        'total_products': total_products,
        'total_order': total_order,
        'pending_vendors': pending_vendors,
        'pending_drivers': pending_drivers,
        'revenue_today': revenue_today,
        'revenue_week': revenue_week,
        'revenue_month': revenue_month,
    }

    return render(request, 'admin_dashboard/dashboard.html', {
        'stats': stats,
        'recent_order': recent_order,
        'recent_activities': recent_activities,
    })

# ============================================
# USER MANAGEMENT
# ============================================
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from accounts.models import User, Customer, Vendor, Driver, AdminProfile

def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

@login_required
@user_passes_test(is_admin)
def manage_users(request):
    user_type = request.GET.get('type', 'all')
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')
    
    users = User.objects.select_related('customer', 'vendor', 'driver', 'admin_profile').all()
    
    # Apply filters
    if user_type != 'all':
        users = users.filter(user_type=user_type)
    
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    elif status_filter == 'verified':
        users = users.filter(is_verified=True)
    elif status_filter == 'unverified':
        users = users.filter(is_verified=False)
    
    if search_query:
        users = users.filter(
            Q(phone_number__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(customer__names__icontains=search_query) |
            Q(vendor__names__icontains=search_query) |
            Q(driver__names__icontains=search_query) |
            Q(admin_profile__names__icontains=search_query)
        )
    
    # Apply ordering (newest first)
    users = users.order_by('-date_joined')
    
    # Pagination
    paginator = Paginator(users, 25)  # Show 25 users per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Stats (calculate based on ALL users, not filtered)
    total_users = User.objects.count()
    customers_count = Customer.objects.count()
    vendors_count = Vendor.objects.count()
    drivers_count = Driver.objects.count()
    admins_count = AdminProfile.objects.count()
    
    # Get filtered counts for the current filter type
    if user_type != 'all':
        filtered_type_count = User.objects.filter(user_type=user_type).count()
    else:
        filtered_type_count = total_users
    
    context = {
        'page_obj': page_obj,
        'active_tab': user_type,
        'total_users': total_users,
        'customers_count': customers_count,
        'vendors_count': vendors_count,
        'drivers_count': drivers_count,
        'admins_count': admins_count,
        'filtered_type_count': filtered_type_count,
        'filters': {
            'type': user_type,
            'status': status_filter,
            'search': search_query,
        }
    }
    return render(request, 'admin_dashboard/users/manage_users.html', context)

# In admin_dashboard/views.py

@login_required
@user_passes_test(is_admin)
def user_detail(request, user_id):
    user = get_object_or_404(User, id=user_id)
    
    # Get user profile based on user type
    profile = None
    if user.user_type == 'customer':
        profile = getattr(user, 'customer', None)
        recent_orders = Order.objects.filter(customer=user).order_by('-created_at')[:5]
    elif user.user_type == 'vendor':
        profile = getattr(user, 'vendor', None)
        recent_orders = []
    elif user.user_type == 'driver':
        profile = getattr(user, 'driver', None)
        recent_orders = []
    elif user.user_type == 'admin':
        profile = getattr(user, 'admin_profile', None)
        recent_orders = []
    
    context = {
        'user': user,
        'profile': profile,
        'recent_orders': recent_orders,
    }
    
    return render(request, 'admin_dashboard/users/user_detail.html', context)

from accounts.models import User

@login_required
@user_passes_test(is_admin)
def delete_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        phone_number = user.phone_number
        user.delete()  # This will cascade-delete related profiles (vendor, driver, etc.)
        messages.success(request, f'User "{phone_number}" deleted successfully!')
    return redirect('admin_dashboard:manage-users')


@login_required
@user_passes_test(is_admin)
def toggle_user_status(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.is_active = not user.is_active
        user.save()
        action = "activated" if user.is_active else "deactivated"
        messages.success(request, f'User {user.phone_number} has been {action}.')
    # ✅ FIX: Use namespaced URL
    return redirect('admin_dashboard:user-detail', user_id=user_id)

@login_required
@user_passes_test(is_admin)
def update_security_answers(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        questions = request.POST.getlist('question_id')
        answers = request.POST.getlist('answer')
        for q_id, answer in zip(questions, answers):
            if answer.strip():
                UserSecurityAnswer.objects.update_or_create(
                    user=user,
                    question_id=q_id,
                    defaults={'answer': answer.strip()}
                )
        messages.success(request, 'Security answers updated!')
    return redirect('admin_dashboard:edit-user', user_id=user_id)


@login_required
@user_passes_test(is_admin)
def verify_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        user.is_verified = True
        user.save()
        messages.success(request, f'User {user.phone_number} has been verified.')
    return redirect('admin_dashboard:user-detail', user_id=user_id)



@login_required
@user_passes_test(is_admin)
def edit_user(request, user_id):
    user = get_object_or_404(User, id=user_id)
    security_questions = SecurityQuestion.objects.all()
    security_answers = UserSecurityAnswer.objects.filter(user=user)
    
    if request.method == 'POST':
        # Update user fields
        user.phone_number = request.POST.get('phone_number')
        user.email = request.POST.get('email', '')
        user.user_type = request.POST.get('user_type')
        user.is_active = request.POST.get('is_active') == 'on'
        user.is_verified = request.POST.get('is_verified') == 'on'
        user.save()
        
        # Update profile based on user type
        if user.user_type == 'customer' and hasattr(user, 'customer'):
            user.customer.names = request.POST.get('customer_names', '')
            user.customer.address = request.POST.get('customer_address', '')
            user.customer.save()
        elif user.user_type == 'vendor' and hasattr(user, 'vendor'):
            user.vendor.names = request.POST.get('vendor_names', '')
            user.vendor.business_name = request.POST.get('vendor_business_name', '')
            user.vendor.business_license = request.POST.get('vendor_business_license', '')
            user.vendor.save()
        elif user.user_type == 'driver' and hasattr(user, 'driver'):
            user.driver.names = request.POST.get('driver_names', '')
            user.driver.license_number = request.POST.get('driver_license_number', '')
            user.driver.vehicle_type = request.POST.get('driver_vehicle_type', '')
            user.driver.vehicle_plate = request.POST.get('driver_vehicle_plate', '')
            user.driver.save()
        elif user.user_type == 'admin' and hasattr(user, 'admin_profile'):
            user.admin_profile.names = request.POST.get('admin_names', '')
            user.admin_profile.department = request.POST.get('admin_department', '')
            user.admin_profile.position = request.POST.get('admin_position', '')
            user.admin_profile.save()
        
        messages.success(request, f'User {user.phone_number} updated successfully!')
        return redirect('admin_dashboard:user-detail', user_id=user.id)
    
    return render(request, 'admin_dashboard/users/edit_user.html', {
        'user': user,
        'security_questions': security_questions,
        'security_answers': security_answers,
    })

# Update Security Answers
@login_required
@user_passes_test(is_admin)
def update_security_answers(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        questions = request.POST.getlist('question_id')
        answers = request.POST.getlist('answer')
        for q_id, answer in zip(questions, answers):
            if answer.strip():
                UserSecurityAnswer.objects.update_or_create(
                    user=user,
                    question_id=q_id,
                    defaults={'answer': answer.strip()}
                )
        messages.success(request, 'Security answers updated!')
    return redirect('admin_dashboard:edit-user', user_id=user_id)

# Reset Password
@login_required
@user_passes_test(is_admin)
def reset_user_password(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        new_pass = request.POST.get('new_password')
        confirm_pass = request.POST.get('confirm_password')
        if new_pass == confirm_pass and len(new_pass) >= 8:
            user.set_password(new_pass)
            user.save()
            messages.success(request, f'Password reset for {user.phone_number}')
        else:
            messages.error(request, 'Passwords must match and be at least 8 characters')
    return redirect('admin_dashboard:edit-user', user_id=user_id)


# ============================================
# VENDOR MANAGEMENT
# ============================================
@login_required
@user_passes_test(is_admin)
def manage_vendors(request):
    """Manage vendors with verification status"""
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')
    
    vendors = Vendor.objects.select_related('user').all()
    
    # Apply filters
    if status_filter == 'verified':
        vendors = vendors.filter(is_verified=True)
    elif status_filter == 'pending':
        vendors = vendors.filter(is_verified=False)
    elif status_filter == 'active':
        vendors = vendors.filter(user__is_active=True)
    elif status_filter == 'inactive':
        vendors = vendors.filter(user__is_active=False)
    
    if search_query:
        vendors = vendors.filter(
            Q(names__icontains=search_query) |
            Q(business_name__icontains=search_query) |
            Q(business_license__icontains=search_query) |
            Q(user__phone_number__icontains=search_query)
        )
    
    # Statistics
    total_vendors = vendors.count()
    verified_vendors = vendors.filter(is_verified=True).count()
    pending_vendors = vendors.filter(is_verified=False).count()
    active_vendors = vendors.filter(user__is_active=True).count()
    
    context = {
        'vendors': vendors,
        'total_vendors': total_vendors,
        'verified_vendors': verified_vendors,
        'pending_vendors': pending_vendors,
        'active_vendors': active_vendors,
        'filters': {
            'status': status_filter,
            'search': search_query,
        }
    }
    
    return render(request, 'admin_dashboard/vendors/manage_vendors.html', context)
# Add to admin_dashboard/views.py
import secrets
@login_required
@user_passes_test(is_admin)
def add_vendor(request):
    if request.method == 'POST':
        try:
            # User data
            phone = request.POST.get('phone_number').strip()
            email = request.POST.get('email', '').strip()
            names = request.POST.get('names').strip()
            business_name = request.POST.get('business_name').strip()
            business_license = request.POST.get('business_license', '').strip()
            location = request.POST.get('location', '').strip()

            # Validate unique phone
            if User.objects.filter(phone_number=phone).exists():
                messages.error(request, "A user with this phone number already exists.")
                return render(request, 'admin_dashboard/vendors/add_vendor.html', {'data': request.POST})

            # Create User
            user = User.objects.create_user(
                phone_number=phone,
                email=email,
                password = secrets.token_urlsafe(12),
                user_type='vendor',
                is_active=True,
                is_verified=False
            )

            # Create Vendor Profile
            Vendor.objects.create(
                user=user,
                names=names,
                business_name=business_name,
                business_license=business_license,
                location=location
            )

            messages.success(request, f'Vendor "{business_name}" created successfully!')
            return redirect('admin_dashboard:manage-vendors')

        except Exception as e:
            messages.error(request, f'Error creating vendor: {str(e)}')
            return render(request, 'admin_dashboard/vendors/add_vendor.html', {'data': request.POST})

    return render(request, 'admin_dashboard/vendors/add_vendor.html')

# Add to views.py
import csv
from django.http import HttpResponse

@login_required
@user_passes_test(is_admin)
def export_vendors_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="vendors.csv"'

    writer = csv.writer(response)
    writer.writerow(['Business Name', 'Owner', 'Phone', 'Email', 'License', 'Verified', 'Active', 'Joined'])

    vendors = Vendor.objects.select_related('user').all()
    for v in vendors:
        writer.writerow([
            v.business_name,
            v.names,
            v.user.phone_number,
            v.user.email or '',
            v.business_license or '',
            'Yes' if v.is_verified else 'No',
            'Yes' if v.user.is_active else 'No',
            v.user.date_joined.strftime('%Y-%m-%d %H:%M')
        ])

    return response


# Add to views.py

@login_required
@user_passes_test(is_admin)
def bulk_vendor_action(request):
    if request.method == 'POST':
        vendor_ids = request.POST.getlist('vendor_ids')
        action = request.POST.get('action')

        if not vendor_ids:
            messages.warning(request, 'No vendors selected.')
            return redirect('admin_dashboard:manage-vendors')

        vendors = Vendor.objects.filter(user_id__in=vendor_ids)

        if action == 'verify':
            vendors.update(is_verified=True, verified_at=timezone.now())
            messages.success(request, f'{vendors.count()} vendors verified.')
        elif action == 'suspend':
            User.objects.filter(id__in=vendor_ids).update(is_active=False)
            messages.success(request, f'{vendors.count()} vendors suspended.')
        elif action == 'activate':
            User.objects.filter(id__in=vendor_ids).update(is_active=True)
            messages.success(request, f'{vendors.count()} vendors activated.')

    return redirect('admin_dashboard:manage-vendors')


@login_required
@user_passes_test(is_admin)
def vendor_detail(request, vendor_id):
    """Vendor detail view"""
    vendor = get_object_or_404(Vendor.objects.select_related('user'), user_id=vendor_id)
    
    # Get vendor products
    products = ProductVariant.objects.filter(vendor=vendor).select_related('product_template')
    
    # Get vendor order
    order = Order.objects.filter(items__product_variant__vendor=vendor).distinct().order_by('-created_at')[:10]
    
    context = {
        'vendor': vendor,
        'products': products,
        'order': order,
    }
    
    return render(request, 'admin_dashboard/vendors/vendor_detail.html', context)
# Replace all redirect() calls with namespaced versions

@login_required
@user_passes_test(is_admin)
def verify_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendor, user_id=vendor_id)
    if request.method == 'POST':
        vendor.is_verified = True
        vendor.verified_at = timezone.now()
        vendor.save()
        messages.success(request, f'Vendor {vendor.business_name} has been verified.')
    return redirect('admin_dashboard:vendor-detail', vendor_id=vendor_id)

@login_required
@user_passes_test(is_admin)
def suspend_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendor, user_id=vendor_id)
    if request.method == 'POST':
        vendor.user.is_active = False
        vendor.user.save()
        messages.success(request, f'Vendor {vendor.business_name} has been suspended.')
    return redirect('admin_dashboard:vendor-detail', vendor_id=vendor_id)

@login_required
@user_passes_test(is_admin)
def activate_vendor(request, vendor_id):
    vendor = get_object_or_404(Vendor, user_id=vendor_id)
    if request.method == 'POST':
        vendor.user.is_active = True
        vendor.user.save()
        messages.success(request, f'Vendor {vendor.business_name} has been activated.')
    return redirect('admin_dashboard:vendor-detail', vendor_id=vendor_id)


# ============================================
# DRIVER MANAGEMENT
# ============================================
from accounts.models import Driver

@login_required
@user_passes_test(is_admin)
def manage_drivers(request):
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')
    
    drivers = Driver.objects.select_related('user').all()
    
    # Apply filters
    if status_filter == 'verified':
        drivers = drivers.filter(is_verified=True)
    elif status_filter == 'pending':
        drivers = drivers.filter(is_verified=False)
    elif status_filter == 'active':
        drivers = drivers.filter(user__is_active=True)
    elif status_filter == 'inactive':
        drivers = drivers.filter(user__is_active=False)
    elif status_filter == 'available':
        drivers = drivers.filter(is_available=True)
    elif status_filter == 'unavailable':
        drivers = drivers.filter(is_available=False)
    
    if search_query:
        drivers = drivers.filter(
            Q(names__icontains=search_query) |
            Q(license_number__icontains=search_query) |
            Q(vehicle_plate__icontains=search_query) |
            Q(user__phone_number__icontains=search_query)
        )
    
    total_drivers = drivers.count()
    verified_drivers = drivers.filter(is_verified=True).count()
    pending_drivers = drivers.filter(is_verified=False).count()
    available_drivers = drivers.filter(is_available=True).count()
    
    context = {
        'drivers': drivers,
        'total_drivers': total_drivers,
        'verified_drivers': verified_drivers,
        'pending_drivers': pending_drivers,
        'available_drivers': available_drivers,
        'filters': {
            'status': status_filter,
            'search': search_query,
        }
    }
    return render(request, 'admin_dashboard/drivers/manage_drivers.html', context)

@login_required
@user_passes_test(is_admin)
def add_driver(request):
    if request.method == 'POST':
        try:
            phone = request.POST.get('phone_number')
            email = request.POST.get('email', '')
            names = request.POST.get('names')
            license_number = request.POST.get('license_number')
            vehicle_type = request.POST.get('vehicle_type')
            vehicle_plate = request.POST.get('vehicle_plate')
            is_active = request.POST.get('is_active') == 'on'
            is_available = request.POST.get('is_available') == 'on'
            
            # Create user
            user = User.objects.create_user(
                phone_number=phone,
                email=email,
                user_type='driver',
                is_active=is_active,
                is_verified=False
            )
            user.set_password('driver123')  # Set default password
            user.save()
            
            # Create driver profile
            Driver.objects.create(
                user=user,
                names=names,
                license_number=license_number,
                vehicle_type=vehicle_type,
                vehicle_plate=vehicle_plate,
                is_available=is_available
            )
            messages.success(request, f'Driver "{names}" created successfully!')
            return redirect('admin_dashboard:manage-drivers')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return render(request, 'admin_dashboard/drivers/add_driver.html')

@login_required
@user_passes_test(is_admin)
def edit_driver(request, driver_id):
    driver = get_object_or_404(Driver, user_id=driver_id)
    if request.method == 'POST':
        try:
            driver.names = request.POST.get('names')
            driver.license_number = request.POST.get('license_number')
            driver.vehicle_type = request.POST.get('vehicle_type')
            driver.vehicle_plate = request.POST.get('vehicle_plate')
            driver.is_available = request.POST.get('is_available') == 'on'
            driver.user.is_active = request.POST.get('is_active') == 'on'
            driver.user.save()
            driver.save()
            messages.success(request, f'Driver "{driver.names}" updated!')
            return redirect('admin_dashboard:driver-detail', driver_id=driver.user.id)
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return render(request, 'admin_dashboard/drivers/edit_driver.html', {'driver': driver})

@login_required
@user_passes_test(is_admin)
def driver_detail(request, driver_id):
    driver = get_object_or_404(Driver.objects.select_related('user'), user_id=driver_id)
    orders = Order.objects.filter(driver=driver.user).order_by('-created_at')[:10]
    return render(request, 'admin_dashboard/drivers/driver_detail.html', {
        'driver': driver,
        'orders': orders
    })

@login_required
@user_passes_test(is_admin)
def verify_driver(request, driver_id):
    driver = get_object_or_404(Driver, user_id=driver_id)
    if request.method == 'POST':
        driver.is_verified = True
        driver.verified_at = timezone.now()
        driver.save()
        messages.success(request, f'Driver {driver.names} has been verified.')
    return redirect('admin_dashboard:driver-detail', driver_id=driver.user.id)

@login_required
@user_passes_test(is_admin)
def toggle_driver_availability(request, driver_id):
    driver = get_object_or_404(Driver, user_id=driver_id)
    if request.method == 'POST':
        driver.is_available = not driver.is_available
        driver.save()
        status = "available" if driver.is_available else "unavailable"
        messages.success(request, f'Driver {driver.names} is now {status}.')
    return redirect('admin_dashboard:driver-detail', driver_id=driver.user.id)

@login_required
@user_passes_test(is_admin)
def delete_driver(request, driver_id):
    driver = get_object_or_404(Driver, user_id=driver_id)
    if request.method == 'POST':
        name = driver.names
        driver.user.delete()  # This will cascade delete driver profile
        messages.success(request, f'Driver "{name}" deleted successfully!')
    return redirect('admin_dashboard:manage-drivers')

# Export Drivers CSV
@login_required
@user_passes_test(is_admin)
def export_drivers_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="drivers.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Phone', 'License', 'Plate', 'Verified', 'Active', 'Available'])
    drivers = Driver.objects.select_related('user').all()
    for d in drivers:
        writer.writerow([
            d.names,
            d.user.phone_number,
            d.license_number,
            d.vehicle_plate,
            'Yes' if d.is_verified else 'No',
            'Yes' if d.user.is_active else 'No',
            'Yes' if d.is_available else 'No'
        ])
    return response

# Bulk Driver Actions
@login_required
@user_passes_test(is_admin)
def bulk_driver_action(request):
    if request.method == 'POST':
        driver_ids = request.POST.getlist('driver_ids')
        action = request.POST.get('action')
        if not driver_ids:
            messages.warning(request, 'No drivers selected.')
            return redirect('admin_dashboard:manage-drivers')
        
        drivers = Driver.objects.filter(user_id__in=driver_ids)
        user_ids = [d.user_id for d in drivers]
        
        if action == 'verify':
            drivers.update(is_verified=True, verified_at=timezone.now())
            messages.success(request, f'{len(drivers)} drivers verified.')
        elif action == 'unverify':
            drivers.update(is_verified=False, verified_at=None)
            messages.success(request, f'{len(drivers)} drivers unverified.')
        elif action == 'activate':
            User.objects.filter(id__in=user_ids).update(is_active=True)
            messages.success(request, f'{len(drivers)} drivers activated.')
        elif action == 'deactivate':
            User.objects.filter(id__in=user_ids).update(is_active=False)
            messages.success(request, f'{len(drivers)} drivers deactivated.')
        elif action == 'set-available':
            drivers.update(is_available=True)
            messages.success(request, f'{len(drivers)} drivers set as available.')
        elif action == 'set-unavailable':
            drivers.update(is_available=False)
            messages.success(request, f'{len(drivers)} drivers set as unavailable.')
    
    return redirect('admin_dashboard:manage-drivers')


# ============================================
# PRODUCT MANAGEMENT
# ============================================
@login_required
@user_passes_test(is_admin)
def manage_products(request):
    """Manage products with filtering"""
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('q', '')
    
    products = ProductTemplate.objects.select_related('category').prefetch_related('variants').all()
    
    # Apply filters
    if category_filter:
        products = products.filter(category_id=category_filter)
    
    if status_filter == 'active':
        products = products.filter(is_active=True)
    elif status_filter == 'inactive':
        products = products.filter(is_active=False)
    elif status_filter == 'verified':
        products = products.filter(is_verified=True)
    elif status_filter == 'unverified':
        products = products.filter(is_verified=False)
    
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(search_keywords__icontains=search_query)
        )
    
    # Statistics
    total_products = products.count()
    active_products = products.filter(is_active=True).count()
    verified_products = products.filter(is_verified=True).count()
    unverified_products = total_products - verified_products  # ✅ Do this in Python
    
    # Categories for filter
    categories = Category.objects.filter(is_active=True)
    
    context = {
        'products': products,
        'categories': categories,
        'total_products': total_products,
        'active_products': active_products,
        'verified_products': verified_products,
        'unverified_products': unverified_products,
        'filters': {
            'category': category_filter,
            'status': status_filter,
            'search': search_query,
        }
    }
    
    return render(request, 'admin_dashboard/products/manage_products.html', context)

# admin_dashboard/views.py
import json
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from products.models import (
    Category, 
    MeasurementUnitType, 
    MeasurementUnit, 
    ProductTemplate
)
from accounts.models import User

# Helper function (assumed to exist)
def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

from products.forms import ProductTemplateForm
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Prefetch
from products.forms import ProductTemplateForm
from products.models import (
    Category, 
    MeasurementUnitType, 
    MeasurementUnit, 
    ProductTemplate
)

# Helper
def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

# ============= ADD PRODUCT =============
@login_required
@user_passes_test(is_admin)
def add_product_template(request):
    if request.method == 'POST':
        form = ProductTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            # Set extra fields that aren't in the form
            product = form.save(commit=False)
            product.created_by = request.user
            product.is_verified = False
            product.save()  # ✅ Saves main_image to Cloudinary
            form.save_m2m()  # ✅ Required for ManyToMany (available_units)
            messages.success(request, f'Product "{product.name}" created successfully!')
            return redirect('admin_dashboard:manage-products')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProductTemplateForm()

    # Prepare data for dynamic unit UI in Add form
    unit_types = MeasurementUnitType.objects.filter(is_active=True)
    unit_groups_serializable = []
    for ut in unit_types:
        units = list(ut.units.filter(is_active=True).values('id', 'name', 'symbol'))
        unit_groups_serializable.append({
            'unit_type': {'id': str(ut.id), 'name': ut.name},
            'units': units
        })
    unit_groups_json = json.dumps(unit_groups_serializable, cls=DjangoJSONEncoder)
    selected_unit_ids = form.data.getlist('available_units') if form.is_bound else []

    return render(request, 'admin_dashboard/products/add_product.html', {
        'form': form,
        'unit_groups_json': unit_groups_json,
        'selected_unit_ids': selected_unit_ids,
    })

# ============= EDIT PRODUCT =============
@login_required
@user_passes_test(is_admin)
def edit_product_template(request, product_id):
    product = get_object_or_404(ProductTemplate, id=product_id)

    if request.method == 'POST':
        form = ProductTemplateForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            # ⚠️ DO NOT USE commit=False HERE!
            product = form.save()  # ✅ This handles Cloudinary upload automatically
            messages.success(request, f'Product "{product.name}" updated successfully!')
            return redirect('admin_dashboard:product-detail', product_id=product.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = ProductTemplateForm(instance=product)

    # Prepare data for server-side unit rendering in Edit form
    unit_types = MeasurementUnitType.objects.filter(is_active=True).prefetch_related(
        Prefetch('units', queryset=MeasurementUnit.objects.filter(is_active=True))
    )
    unit_groups = []
    for ut in unit_types:
        unit_groups.append({'unit_type': ut, 'units': ut.units.all()})

    return render(request, 'admin_dashboard/products/edit_product.html', {
        'product': product,
        'form': form,
        'unit_groups': unit_groups,
    })
@login_required
@user_passes_test(is_admin)
def manage_product_variants(request, product_id):
    product = get_object_or_404(ProductTemplate, id=product_id)
    variants = product.variants.select_related('vendor', 'market_zone').prefetch_related('unit_prices__unit').all()

    # For each variant, build {unit_id: price}
    for variant in variants:
        variant.unit_price_dict = {
            str(up.unit.id): up.selling_price  # ✅ Use 'selling_price'
            for up in variant.unit_prices.all()
        }

    return render(request, 'admin_dashboard/products/manage_variants.html', {
        'product': product,
        'variants': variants,
    })


# admin_dashboard/views.py
from products.models import ProductVariant
# admin_dashboard/views.py
from products.models import ProductAddon
@login_required
@user_passes_test(is_admin)
def add_product_variant(request, product_id):
    product = get_object_or_404(ProductTemplate, id=product_id)
    
    if request.method == 'POST':
        try:
            vendor_id = request.POST.get('vendor')
            market_zone_id = request.POST.get('market_zone')
            custom_profit = request.POST.get('custom_profit_percentage') or None
            quality_grade = request.POST.get('quality_grade') or ''
            is_active = request.POST.get('is_active') == 'on'

            vendor = Vendor.objects.get(user_id=vendor_id)
            market_zone = MarketZone.objects.get(id=market_zone_id)

            # Create variant (NO base_cost_price)
            variant = ProductVariant.objects.create(
                product_template=product,
                vendor=vendor,
                market_zone=market_zone,
                custom_profit_percentage=custom_profit,
                quality_grade=quality_grade,
                is_active=is_active,
                is_approved=True
            )

            # Save unit costs → selling_price auto-calculated
            for unit in product.available_units.all():
                cost_key = f"cost_price_{unit.id}"
                if cost_key in request.POST:
                    cost_price = Decimal(request.POST.get(cost_key))
                    # Auto-calculate selling_price
                    profit_pct = variant.effective_profit_percentage
                    selling_price = cost_price + (cost_price * profit_pct / Decimal('100'))
                    
                    UnitPrice.objects.update_or_create(
                        product_variant=variant,
                        unit=unit,
                        defaults={
                            'cost_price': cost_price,
                            'selling_price': selling_price,
                            'is_active': True
                        }
                    )

            messages.success(request, f'Variant for {vendor.business_name} created!')
            return redirect('admin_dashboard:manage-product-variants', product_id=product.id)

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')

    # GET
    vendors = Vendor.objects.filter(is_verified=True, user__is_active=True)
    market_zones = MarketZone.objects.filter(is_active=True)
    return render(request, 'admin_dashboard/products/add_variant.html', {
        'product': product,
        'vendors': vendors,
        'market_zones': market_zones,
    })



from decimal import Decimal, InvalidOperation

@login_required
@user_passes_test(is_admin)
def edit_product_variant(request, variant_id):
    variant = get_object_or_404(ProductVariant, id=variant_id)
    
    if request.method == 'POST':
        try:
            # Update non-price fields
            variant.custom_profit_percentage = request.POST.get('custom_profit_percentage') or None
            variant.quality_grade = request.POST.get('quality_grade') or ''
            variant.is_active = request.POST.get('is_active') == 'on'
            variant.save()

            # Update unit costs and auto-calculate selling prices
            for unit in variant.product_template.available_units.all():
                cost_key = f"cost_price_{unit.id}"
                if cost_key in request.POST:
                    cost_price_str = request.POST.get(cost_key)
                    if cost_price_str:
                        cost_price = Decimal(str(cost_price_str).strip())
                        # Auto-calculate selling_price
                        profit_pct = variant.effective_profit_percentage
                        selling_price = cost_price + (cost_price * profit_pct / Decimal('100'))
                        
                        UnitPrice.objects.update_or_create(
                            product_variant=variant,
                            unit=unit,
                            defaults={
                                'cost_price': cost_price,
                                'selling_price': selling_price,
                                'is_active': True
                            }
                        )
                    else:
                        # Skip if no cost price provided
                        continue

            messages.success(request, f'Variant updated successfully!')
            return redirect('admin_dashboard:manage-product-variants', product_id=variant.product_template.id)

        except (ValueError, TypeError, InvalidOperation, Exception) as e:
            messages.error(request, f'Error: {str(e)}')

    # GET request
    market_zones = MarketZone.objects.filter(is_active=True)
    addons = ProductAddon.objects.filter(is_active=True)
    
    # Load current unit prices
    unit_prices = {}
    for up in variant.unit_prices.all():
        unit_prices[str(up.unit.id)] = {
            'cost_price': up.cost_price,
            'selling_price': up.selling_price
        }
    selected_addons = [a.id for a in variant.available_addons.all()]

    return render(request, 'admin_dashboard/products/edit_variant.html', {
        'variant': variant,
        'market_zones': market_zones,
        'all_addons': addons,
        'unit_prices': unit_prices,
        'selected_addons': selected_addons,
    })

@login_required
@user_passes_test(is_admin)
def bulk_product_action(request):
    if request.method == 'POST':
        product_ids = request.POST.getlist('product_ids')
        action = request.POST.get('action')

        if not product_ids:
            messages.warning(request, 'No products selected.')
            return redirect('admin_dashboard:manage-products')

        products = ProductTemplate.objects.filter(id__in=product_ids)

        if action == 'verify':
            products.update(is_verified=True)
            messages.success(request, f'{products.count()} products verified.')
        elif action == 'unverify':
            products.update(is_verified=False)
            messages.success(request, f'{products.count()} products unverified.')
        elif action == 'activate':
            products.update(is_active=True)
            messages.success(request, f'{products.count()} products activated.')
        elif action == 'deactivate':
            products.update(is_active=False)
            messages.success(request, f'{products.count()} products deactivated.')

    return redirect('admin_dashboard:manage-products')

import csv
from django.http import HttpResponse

@login_required
@user_passes_test(is_admin)
def export_products_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="products.csv"'

    writer = csv.writer(response)
    writer.writerow(['Name', 'Category', 'Primary Unit', 'Verified', 'Active', 'Created'])

    products = ProductTemplate.objects.select_related('category', 'primary_unit_type').all()
    for p in products:
        writer.writerow([
            p.name,
            p.category.name,
            p.primary_unit_type.name,
            'Yes' if p.is_verified else 'No',
            'Yes' if p.is_active else 'No',
            p.created_at.strftime('%Y-%m-%d')
        ])

    return response


@login_required
@user_passes_test(is_admin)
def product_detail(request, product_id):
    """Product detail view"""
    product = get_object_or_404(
        ProductTemplate.objects.select_related('category', 'primary_unit_type')
        .prefetch_related('variants__vendor', 'variants__market_zone'),
        id=product_id
    )
    
    context = {
        'product': product,
    }
    
    return render(request, 'admin_dashboard/products/product_detail.html', context)

@login_required
@user_passes_test(is_admin)
def verify_product(request, product_id):
    """Verify product template"""
    product = get_object_or_404(ProductTemplate, id=product_id)
    
    if request.method == 'POST':
        product.is_verified = True
        product.save()
        messages.success(request, f'Product {product.name} has been verified.')
    
    # In verify_product and toggle_product_status
    return redirect('admin_dashboard:product-detail', product_id=product_id)

@login_required
@user_passes_test(is_admin)
def toggle_product_status(request, product_id):
    """Toggle product active status"""
    product = get_object_or_404(ProductTemplate, id=product_id)
    
    if request.method == 'POST':
        product.is_active = not product.is_active
        product.save()
        
        status = "activated" if product.is_active else "deactivated"
        messages.success(request, f'Product {product.name} has been {status}.')
    
    # In verify_product and toggle_product_status
    return redirect('admin_dashboard:product-detail', product_id=product_id)






from products.models import Category

@login_required
@user_passes_test(is_admin)
def manage_categories(request):
    """List all categories with filtering"""
    status_filter = request.GET.get('status', 'all')
    parent_filter = request.GET.get('parent', '')
    
    categories = Category.objects.all()
    
    # Apply filters
    if status_filter == 'active':
        categories = categories.filter(is_active=True)
    elif status_filter == 'inactive':
        categories = categories.filter(is_active=False)
    
    if parent_filter:
        if parent_filter == 'top-level':
            categories = categories.filter(parent__isnull=True)
        else:
            categories = categories.filter(parent_id=parent_filter)
    
    # Stats
    total_categories = categories.count()
    active_categories = categories.filter(is_active=True).count()
    top_level_categories = Category.objects.filter(parent__isnull=True).count()
    
    # Parent options for filter
    parent_options = Category.objects.filter(parent__isnull=True)
    
    context = {
        'categories': categories,
        'parent_options': parent_options,
        'total_categories': total_categories,
        'active_categories': active_categories,
        'top_level_categories': top_level_categories,
        'filters': {
            'status': status_filter,
            'parent': parent_filter,
        }
    }
    return render(request, 'admin_dashboard/categories/manage_categories.html', context)

@login_required
@user_passes_test(is_admin)
def add_category(request):
    """Add new category"""
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            parent_id = request.POST.get('parent') or None
            profit_percentage = request.POST.get('profit_percentage', 10.00)
            
            category = Category(
                name=name,
                description=description,
                profit_percentage=profit_percentage
            )
            
            if parent_id:
                parent = Category.objects.get(id=parent_id)
                category.parent = parent
            
            if 'image' in request.FILES:
                category.image = request.FILES['image']
            
            category.save()
            messages.success(request, f'Category "{name}" created successfully!')
            return redirect('admin_dashboard:manage-categories')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    parent_categories = Category.objects.filter(parent__isnull=True)
    return render(request, 'admin_dashboard/categories/add_category.html', {
        'parent_categories': parent_categories
    })

@login_required
@user_passes_test(is_admin)
def edit_category(request, category_id):
    """Edit existing category"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        try:
            category.name = request.POST.get('name')
            category.description = request.POST.get('description', '')
            category.profit_percentage = request.POST.get('profit_percentage', 10.00)
            
            parent_id = request.POST.get('parent') or None
            if parent_id:
                parent = Category.objects.get(id=parent_id)
                category.parent = parent
            else:
                category.parent = None
            
            if 'image' in request.FILES:
                category.image = request.FILES['image']
            
            category.save()
            messages.success(request, f'Category "{category.name}" updated successfully!')
            return redirect('admin_dashboard:manage-categories')
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    parent_categories = Category.objects.filter(parent__isnull=True).exclude(id=category_id)
    return render(request, 'admin_dashboard/categories/edit_category.html', {
        'category': category,
        'parent_categories': parent_categories
    })

@login_required
@user_passes_test(is_admin)
def delete_category(request, category_id):
    """Delete category"""
    category = get_object_or_404(Category, id=category_id)
    
    if request.method == 'POST':
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" deleted successfully!')
    
    return redirect('admin_dashboard:manage-categories')



# ============================================
# ORDER MANAGEMENT
# ============================================
@login_required
@user_passes_test(is_admin)
def manage_order(request):
    """Manage order with filtering"""
    status_filter = request.GET.get('status', 'all')
    payment_filter = request.GET.get('payment', 'all')
    date_range = request.GET.get('date_range', '')
    search_query = request.GET.get('q', '')
    
    order = Order.objects.select_related('customer').all().order_by('-created_at')
    
    # Apply filters
    if status_filter != 'all':
        order = order.filter(status=status_filter)
    
    if payment_filter != 'all':
        order = order.filter(payment_method=payment_filter)
    
    if search_query:
        order = order.filter(
            Q(order_number__icontains=search_query) |
            Q(customer__phone_number__icontains=search_query) |
            Q(customer__customer__names__icontains=search_query)
        )
    
    # Date range filter
    if date_range:
        today = timezone.now().date()
        if date_range == 'today':
            order = order.filter(created_at__date=today)
        elif date_range == 'week':
            week_ago = today - timedelta(days=7)
            order = order.filter(created_at__date__gte=week_ago)
        elif date_range == 'month':
            month_ago = today - timedelta(days=30)
            order = order.filter(created_at__date__gte=month_ago)
    
    # Statistics
    total_order = order.count()
    pending_order = order.filter(status='pending').count()
    completed_order = order.filter(status='completed').count()
    total_revenue = order.filter(status='completed').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    context = {
        'order': order,
        'total_order': total_order,
        'pending_order': pending_order,
        'completed_order': completed_order,
        'total_revenue': total_revenue,
        'filters': {
            'status': status_filter,
            'payment': payment_filter,
            'date_range': date_range,
            'search': search_query,
        }
    }
    
    return render(request, 'admin_dashboard/order/manage_order.html', context)

@login_required
@user_passes_test(is_admin)
def order_detail(request, order_id):
    """Order detail view"""
    order = get_object_or_404(
        Order.objects.select_related('customer', 'driver')
        .prefetch_related('items__product_variant'),
        id=order_id
    )
    
    context = {
        'order': order,
    }
    
    return render(request, 'admin_dashboard/order/order_detail.html', context)

@login_required
@user_passes_test(is_admin)
def update_order_status(request, order_id):
    """Update order status"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status:
            order.status = new_status
            order.save()
            messages.success(request, f'Order status updated to {new_status}.')
    
    return redirect('order-detail', order_id=order_id)

# # admin_dashboard/views.py (Market Management Section)
@login_required
@user_passes_test(is_admin)
def manage_markets(request):
    markets = Market.objects.prefetch_related('zones', 'delivery_zones').all()
    
    for market in markets:
        market.active_zones_count = market.zones.filter(is_active=True).count()
        market.active_delivery_zones_count = market.delivery_zones.filter(is_active=True).count()  # 👈 Add this
    
    total_markets = markets.count()
    active_markets = markets.filter(is_active=True).count()
    total_zones = MarketZone.objects.count()
    total_delivery_zones = DeliveryZone.objects.count()
    
    context = {
        'markets': markets,
        'total_markets': total_markets,
        'active_markets': active_markets,
        'total_zones': total_zones,
        'total_delivery_zones': total_delivery_zones,
    }
    return render(request, 'admin_dashboard/markets/manage_markets.html', context)


@login_required
@user_passes_test(is_admin)
def add_market(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            Market.objects.create(name=name, description=description)
            messages.success(request, 'Market added successfully!')
            return redirect('admin_dashboard:manage-markets')  # ✅ Namespaced
        except Exception as e:
            messages.error(request, f'Error adding market: {str(e)}')
    return render(request, 'admin_dashboard/markets/add_market.html')

@login_required
@user_passes_test(is_admin)
def edit_market(request, market_id):
    market = get_object_or_404(Market, id=market_id)
    if request.method == 'POST':
        try:
            market.name = request.POST.get('name')
            market.description = request.POST.get('description', '')
            market.save()
            messages.success(request, 'Market updated successfully!')
            return redirect('admin_dashboard:manage-markets')  # ✅
        except Exception as e:
            messages.error(request, f'Error updating market: {str(e)}')
    return render(request, 'admin_dashboard/markets/edit_market.html', {'market': market})

@login_required
@user_passes_test(is_admin)
def delete_market(request, market_id):
    market = get_object_or_404(Market, id=market_id)
    if request.method == 'POST':
        market_name = market.name
        market.delete()
        messages.success(request, f'Market "{market_name}" deleted successfully!')
        return redirect('admin_dashboard:manage-markets')  # ✅
    return redirect('admin_dashboard:manage-markets')

# Add to admin_dashboard/views.py

@login_required
@user_passes_test(is_admin)
def manage_market_zones(request, market_id):
    market = get_object_or_404(Market, id=market_id)
    zones = market.zones.all()
    active_zones = zones.filter(is_active=True)
    inactive_zones = zones.filter(is_active=False)

    return render(request, 'admin_dashboard/markets/manage_zones.html', {
        'market': market,
        'zones': zones,
        'active_zones_count': active_zones.count(),
        # Optional: pass full lists if needed
        # 'active_zones': active_zones,
        # 'inactive_zones': inactive_zones,
    })

@login_required
@user_passes_test(is_admin)
def add_market_zone(request, market_id):
    market = get_object_or_404(Market, id=market_id)
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            zone_type = request.POST.get('zone_type', '')
            MarketZone.objects.create(
                market=market,
                name=name,
                description=description,
                zone_type=zone_type,
                is_active=True
            )
            messages.success(request, f'Zone "{name}" added to {market.name}!')
            return redirect('admin_dashboard:manage-market-zones', market_id=market.id)
        except Exception as e:
            messages.error(request, f'Error adding zone: {str(e)}')
    return render(request, 'admin_dashboard/markets/add_zone.html', {'market': market})

@login_required
@user_passes_test(is_admin)
def edit_market_zone(request, zone_id):
    zone = get_object_or_404(MarketZone, id=zone_id)
    if request.method == 'POST':
        try:
            zone.name = request.POST.get('name')
            zone.description = request.POST.get('description', '')
            zone.zone_type = request.POST.get('zone_type', '')
            zone.is_active = request.POST.get('is_active') == 'on'
            zone.save()
            messages.success(request, f'Zone "{zone.name}" updated!')
            return redirect('admin_dashboard:manage-market-zones', market_id=zone.market.id)
        except Exception as e:
            messages.error(request, f'Error updating zone: {str(e)}')
    return render(request, 'admin_dashboard/markets/edit_zone.html', {'zone': zone})

@login_required
@user_passes_test(is_admin)
def delete_market_zone(request, zone_id):
    zone = get_object_or_404(MarketZone, id=zone_id)
    market_id = zone.market.id
    if request.method == 'POST':
        zone_name = zone.name
        zone.delete()
        messages.success(request, f'Zone "{zone_name}" deleted!')
    return redirect('admin_dashboard:manage-market-zones', market_id=market_id)



# Add to views.py
# Delivery Zone Management
@login_required
@user_passes_test(is_admin)
def manage_delivery_zones(request, market_id):
    market = get_object_or_404(Market, id=market_id)
    zones = market.delivery_zones.all().order_by('-created_at')
    return render(request, 'admin_dashboard/locations/manage_delivery_zones.html', {
        'market': market,
        'zones': zones
    })

@login_required
@user_passes_test(is_admin)
def add_delivery_zone(request, market_id):
    market = get_object_or_404(Market, id=market_id)
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            base_fee = Decimal(request.POST.get('base_delivery_fee', '0'))
            is_manual = request.POST.get('is_manual_pricing') == 'on'
            manual_fee = request.POST.get('manual_delivery_fee') or None
            
            zone = DeliveryZone(
                market=market,
                name=name,
                description=description,
                base_delivery_fee=base_fee,
                is_manual_pricing=is_manual,
                is_active=True
            )
            if manual_fee:
                zone.manual_delivery_fee = Decimal(manual_fee)
            zone.save()
            
            messages.success(request, f'Delivery zone "{name}" created successfully!')
            return redirect('admin_dashboard:manage-delivery-zones', market_id=market.id)
        except (InvalidOperation, ValueError, Exception) as e:
            messages.error(request, f'Error creating zone: {str(e)}')
    
    return render(request, 'admin_dashboard/locations/add_delivery_zone.html', {'market': market})

@login_required
@user_passes_test(is_admin)
def edit_delivery_zone(request, zone_id):
    zone = get_object_or_404(DeliveryZone, id=zone_id)
    if request.method == 'POST':
        try:
            zone.name = request.POST.get('name')
            zone.description = request.POST.get('description', '')
            zone.base_delivery_fee = Decimal(request.POST.get('base_delivery_fee', '0'))
            zone.is_manual_pricing = request.POST.get('is_manual_pricing') == 'on'
            manual_fee = request.POST.get('manual_delivery_fee') or None
            zone.manual_delivery_fee = Decimal(manual_fee) if manual_fee else None
            zone.is_active = request.POST.get('is_active') == 'on'
            
            # Optional: Add boundary coordinates
            zone.min_latitude = request.POST.get('min_latitude') or None
            zone.max_latitude = request.POST.get('max_latitude') or None
            zone.min_longitude = request.POST.get('min_longitude') or None
            zone.max_longitude = request.POST.get('max_longitude') or None
            
            zone.save()
            messages.success(request, f'Delivery zone "{zone.name}" updated!')
            return redirect('admin_dashboard:manage-delivery-zones', market_id=zone.market.id)
        except (InvalidOperation, ValueError, Exception) as e:
            messages.error(request, f'Error updating zone: {str(e)}')
    
    return render(request, 'admin_dashboard/locations/edit_delivery_zone.html', {'zone': zone})

@login_required
@user_passes_test(is_admin)
def delete_delivery_zone(request, zone_id):
    zone = get_object_or_404(DeliveryZone, id=zone_id)
    market_id = zone.market.id
    if request.method == 'POST':
        zone_name = zone.name
        zone.delete()
        messages.success(request, f'Delivery zone "{zone_name}" deleted!')
    return redirect('admin_dashboard:manage-delivery-zones', market_id=market_id)

# ============================================
# SETTINGS & SYSTEM MANAGEMENT
# ============================================
@login_required
@user_passes_test(is_admin)
def system_settings(request):
    """System settings management"""
    settings = GlobalSetting.objects.all()
    
    if request.method == 'POST':
        # Handle settings update
        for setting in settings:
            new_value = request.POST.get(f'setting_{setting.id}')
            if new_value is not None:
                setting.value = new_value
                setting.save()
        
        messages.success(request, 'Settings updated successfully!')
        return redirect('system-settings')
    
    context = {
        'settings': settings,
    }
    
    return render(request, 'admin_dashboard/settings/system_settings.html', context)

# @login_required
# @user_passes_test(is_admin)
# def measurement_units(request):
#     """Manage measurement units"""
#     units = MeasurementUnit.objects.select_related('unit_type').all()
    
#     context = {
#         'units': units,
#     }
    
#     return render(request, 'admin_dashboard/settings/measurement_units.html', context)

















@login_required
@user_passes_test(is_admin)
def manage_unit_types(request):
    unit_types = MeasurementUnitType.objects.all()
    active_types_count = unit_types.filter(is_active=True).count()  # ← ADD THIS
    return render(request, 'admin_dashboard/units/manage_unit_types.html', {
        'unit_types': unit_types,
        'active_types_count': active_types_count,  # ← PASS TO TEMPLATE
    })

@login_required
@user_passes_test(is_admin)
def add_unit_type(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            description = request.POST.get('description', '')
            base_unit_name = request.POST.get('base_unit_name')
            
            MeasurementUnitType.objects.create(
                name=name,
                description=description,
                base_unit_name=base_unit_name
            )
            messages.success(request, f'Unit type "{name}" created!')
            return redirect('admin_dashboard:manage-unit-types')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return render(request, 'admin_dashboard/units/add_unit_type.html')

@login_required
@user_passes_test(is_admin)
def edit_unit_type(request, type_id):
    unit_type = get_object_or_404(MeasurementUnitType, id=type_id)
    if request.method == 'POST':
        try:
            unit_type.name = request.POST.get('name')
            unit_type.description = request.POST.get('description', '')
            unit_type.base_unit_name = request.POST.get('base_unit_name')
            unit_type.save()
            messages.success(request, f'Unit type updated!')
            return redirect('admin_dashboard:manage-unit-types')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return render(request, 'admin_dashboard/units/edit_unit_type.html', {
        'unit_type': unit_type
    })

@login_required
@user_passes_test(is_admin)
def delete_unit_type(request, type_id):
    unit_type = get_object_or_404(MeasurementUnitType, id=type_id)
    if request.method == 'POST':
        name = unit_type.name
        unit_type.delete()
        messages.success(request, f'Unit type "{name}" deleted!')
    return redirect('admin_dashboard:manage-unit-types')

# Measurement Units
@login_required
@user_passes_test(is_admin)
def manage_units(request):
    units = MeasurementUnit.objects.select_related('unit_type').all()
    unit_types = MeasurementUnitType.objects.all()
    
    # Filtering
    type_filter = request.GET.get('unit_type')
    if type_filter:
        units = units.filter(unit_type_id=type_filter)
    
    # ✅ Pre-calculate active count
    active_units_count = units.filter(is_active=True).count()
    
    return render(request, 'admin_dashboard/units/manage_units.html', {
        'units': units,
        'unit_types': unit_types,
        'active_units_count': active_units_count,  # ← Pass to template
        'filters': {'unit_type': type_filter}
    })

@login_required
@user_passes_test(is_admin)
def add_unit(request):
    unit_types = MeasurementUnitType.objects.all()
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            symbol = request.POST.get('symbol')
            unit_type_id = request.POST.get('unit_type')
            conversion_factor = Decimal(request.POST.get('conversion_factor'))
            is_base_unit = request.POST.get('is_base_unit') == 'on'
            
            MeasurementUnit.objects.create(
                name=name,
                symbol=symbol,
                unit_type_id=unit_type_id,
                conversion_factor=conversion_factor,
                is_base_unit=is_base_unit
            )
            messages.success(request, f'Unit "{name}" created!')
            return redirect('admin_dashboard:measurement-units')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return render(request, 'admin_dashboard/units/add_unit.html', {
        'unit_types': unit_types
    })

@login_required
@user_passes_test(is_admin)
def edit_unit(request, unit_id):
    unit = get_object_or_404(MeasurementUnit, id=unit_id)
    unit_types = MeasurementUnitType.objects.all()
    if request.method == 'POST':
        try:
            unit.name = request.POST.get('name')
            unit.symbol = request.POST.get('symbol')
            unit.unit_type_id = request.POST.get('unit_type')
            unit.conversion_factor = Decimal(request.POST.get('conversion_factor'))
            unit.is_base_unit = request.POST.get('is_base_unit') == 'on'
            unit.save()
            messages.success(request, f'Unit updated!')
            return redirect('admin_dashboard:measurement-units')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return render(request, 'admin_dashboard/units/edit_unit.html', {
        'unit': unit,
        'unit_types': unit_types
    })

@login_required
@user_passes_test(is_admin)
def delete_unit(request, unit_id):
    unit = get_object_or_404(MeasurementUnit, id=unit_id)
    if request.method == 'POST':
        name = unit.name
        unit.delete()
        messages.success(request, f'Unit "{name}" deleted!')
    return redirect('admin_dashboard:measurement-units')