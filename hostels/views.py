from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Block, Room, Bed, Allocation
from core.models import Student

@login_required
def hostel_dashboard(request):
    blocks = Block.objects.prefetch_related('rooms__beds').all()
    allocations = Allocation.objects.select_related('student', 'bed__room__block').all()
    
    context = {
        'blocks': blocks,
        'allocations': allocations,
    }
    return render(request, 'hostels/dashboard.html', context)

@login_required
def setup_hostel(request):
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add_block':
            Block.objects.create(
                name=request.POST.get('name'),
                gender_type=request.POST.get('gender_type')
            )
            messages.success(request, 'Block added successfully.')
        elif action == 'add_room':
            block_id = request.POST.get('block_id')
            room = Room.objects.create(
                block_id=block_id,
                room_number=request.POST.get('room_number'),
                capacity=request.POST.get('capacity')
            )
            # Auto-create beds
            for i in range(room.capacity):
                Bed.objects.create(room=room, bed_number=str(i+1))
            messages.success(request, 'Room and Beds added successfully.')
        return redirect('hostels:setup')

    blocks = Block.objects.all()
    return render(request, 'hostels/setup.html', {'blocks': blocks})

@login_required
def allocate_bed(request):
    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        bed_id = request.POST.get('bed_id')
        
        student = get_object_or_404(Student, id=student_id)
        bed = get_object_or_404(Bed, id=bed_id)
        
        if bed.is_occupied:
            messages.error(request, 'Bed is already occupied.')
            return redirect('hostels:allocate')
            
        if hasattr(student, 'hostel_allocation'):
            messages.error(request, 'Student already has a bed allocated.')
            return redirect('hostels:allocate')
            
        Allocation.objects.create(student=student, bed=bed, allocated_by=request.user)
        bed.is_occupied = True
        bed.save()
        messages.success(request, f'Bed allocated to {student}.')
        return redirect('hostels:dashboard')

    students = Student.objects.filter(hostel_allocation__isnull=True, is_boarder=True)
    beds = Bed.objects.filter(is_occupied=False).select_related('room__block')
    return render(request, 'hostels/allocate.html', {'students': students, 'beds': beds})
