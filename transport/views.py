from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Route, Vehicle, TransportAssignment
from core.models import Student, StudentProfile
from django.db.models import Count

@login_required
def transport_dashboard(request):
    routes = Route.objects.annotate(student_count=Count('assignments'))
    vehicles = Vehicle.objects.annotate(student_count=Count('assignments'))
    assignments = TransportAssignment.objects.select_related('student', 'route', 'vehicle').order_by('-created_at')
    
    # Stats
    total_routes = routes.count()
    total_vehicles = vehicles.count()
    total_assigned = assignments.count()
    
    return render(request, 'transport/dashboard.html', {
        'routes': routes,
        'vehicles': vehicles,
        'assignments': assignments,
        'total_routes': total_routes,
        'total_vehicles': total_vehicles,
        'total_assigned': total_assigned,
        'students_without_transport': Student.objects.exclude(transport_assignment__is_active=True).order_by('first_name')
    })

@login_required
def add_route(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        fee = request.POST.get('monthly_fee', 0)
        
        Route.objects.create(name=name, description=description, monthly_fee=fee)
        messages.success(request, f"Route '{name}' added successfully.")
    return redirect('transport:dashboard')

@login_required
def add_vehicle(request):
    if request.method == 'POST':
        plate = request.POST.get('plate_number')
        model = request.POST.get('model')
        capacity = request.POST.get('capacity')
        driver = request.POST.get('driver_name')
        phone = request.POST.get('driver_phone')
        
        Vehicle.objects.create(plate_number=plate, model=model, capacity=capacity, driver_name=driver, driver_phone=phone)
        messages.success(request, f"Vehicle '{plate}' added successfully.")
    return redirect('transport:dashboard')

@login_required
def assign_transport(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        route_id = request.POST.get('route_id')
        vehicle_id = request.POST.get('vehicle_id')
        pickup = request.POST.get('pickup_point')
        custom_fee = request.POST.get('custom_fee')
        
        student = get_object_or_404(Student, id=student_id)
        route = get_object_or_404(Route, id=route_id)
        vehicle = get_object_or_404(Vehicle, id=vehicle_id) if vehicle_id else None
        
        TransportAssignment.objects.update_or_create(
            student=student,
            defaults={
                'route': route,
                'vehicle': vehicle,
                'pickup_point': pickup,
                'custom_fee': custom_fee if custom_fee else None,
                'is_active': True
            }
        )
        messages.success(request, f"Transport assigned for {student.first_name}.")
    return redirect('transport:dashboard')

@login_required
def delete_assignment(request, assignment_id):
    assignment = get_object_or_404(TransportAssignment, id=assignment_id)
    student_name = assignment.student.first_name
    assignment.delete()
    messages.success(request, f"Transport assignment for {student_name} removed.")
    return redirect('transport:dashboard')
