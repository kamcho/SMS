from django.contrib import admin
from .models import FeeStructure, Invoice, Payment

@admin.register(FeeStructure)
class FeeStructureAdmin(admin.ModelAdmin):
    list_display = ('term', 'academic_year', 'amount', 'created_at')
    list_filter = ('term', 'academic_year')
    search_fields = ('term__name',)

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('student', 'fee_structure', 'amount', 'created_at')
    list_filter = ('fee_structure__term', 'fee_structure__academic_year')
    search_fields = ('student__first_name', 'student__last_name', 'student__adm_no')
    readonly_fields = ('amount', 'is_billed')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('student', 'amount', 'previous_balance', 'current_balance', 'method', 'reference', 'date_paid')
    list_filter = ('method', 'date_paid')
    search_fields = ('student__first_name', 'student__last_name', 'student__adm_no', 'reference')
    readonly_fields = ('previous_balance', 'current_balance', 'recorded_by')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)
