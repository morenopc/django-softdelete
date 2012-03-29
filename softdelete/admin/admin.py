from django.http import HttpResponseRedirect
from django.contrib import admin
from softdelete.models import *
from softdelete.admin.forms import *

class SoftDeleteObjectInline(admin.TabularInline):
    class Meta:
        exclude = ('deleted_at',)

    def __init__(self, parent, site, *args, **kwargs):
        super(SoftDeleteObjectInline, self).__init__(parent, site, *args, **kwargs)
        if parent.deleted:
            self.extra = 0
            self.max_num = 0

    def queryset(self, request):
        qs = self.model._default_manager.all_with_deleted()
        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

class SoftDeleteObjectAdmin(admin.ModelAdmin):
    form = SoftDeleteObjectAdminForm
    actions = ['delete_selected', 'soft_undelete']

    def delete_selected(self, request, queryset):
        queryset.delete()
    delete_selected.short_description = 'Soft delete selected objects'

    def soft_undelete(self, request, queryset):
        queryset.undelete()
    soft_undelete.short_description = 'Undelete selected objects'

    def response_change(self, request, obj, *args, **kwargs):
        if request.POST.has_key('undelete'):
            return HttpResponseRedirect('../')
        return super(SoftDeleteObjectAdmin, self).response_change(request, obj, *args, **kwargs)

    def queryset(self, request):
        try:
            qs = self.model._default_manager.all_with_deleted()
        except Exception:
            qs = self.model._default_manager.all()

        ordering = self.ordering or ()
        if ordering:
            qs = qs.order_by(*ordering)
        return qs
