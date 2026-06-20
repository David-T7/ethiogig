from django.contrib import admin, messages
from django.utils import timezone
from django.utils.html import format_html
from core import models

PIPELINE_STAGES = [
    'ai_screening',
    'kyc',
    'theoretical_test',
    'interview',
]


class VettingPipelineRecordInline(admin.TabularInline):
    model = models.VettingPipelineRecord
    extra = 0
    can_delete = True
    fields = ('stage', 'status', 'score', 'external_submission_id', 'notes', 'updated_at')
    readonly_fields = ('updated_at',)
    ordering = ('stage',)
    verbose_name = 'Pipeline stage'
    verbose_name_plural = 'Vetting pipeline stages'


class CandidateVettingProgressInline(admin.StackedInline):
    model = models.CandidateVettingProgress
    extra = 0
    max_num = 1
    can_delete = True
    fields = (
        'position_name',
        'selected_stack_slug',
        'selected_stack_name',
        'technology_results',
        'verified_technologies',
        'updated_at',
    )
    readonly_fields = ('updated_at',)


@admin.register(models.VettingPipelineRecord)
class VettingPipelineRecordAdmin(admin.ModelAdmin):
    list_display = ('resume_email', 'stage', 'status', 'score', 'updated_at')
    list_filter = ('stage', 'status')
    search_fields = ('resume__email', 'resume__full_name', 'notes')
    list_editable = ('status', 'score')
    raw_id_fields = ('resume',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': (
                'resume',
                'stage',
                'status',
                'score',
                'external_submission_id',
                'notes',
            ),
        }),
        ('Timestamps', {'fields': ('id', 'created_at', 'updated_at')}),
    )

    @admin.display(description='Candidate email', ordering='resume__email')
    def resume_email(self, obj):
        return obj.resume.email if obj.resume_id else '—'


@admin.register(models.CandidateVettingProgress)
class CandidateVettingProgressAdmin(admin.ModelAdmin):
    list_display = (
        'resume_email',
        'selected_stack_name',
        'position_name',
        'verified_count',
        'updated_at',
    )
    search_fields = ('resume__email', 'resume__full_name', 'selected_stack_slug')
    raw_id_fields = ('resume',)
    readonly_fields = ('id', 'updated_at')

    @admin.display(description='Email', ordering='resume__email')
    def resume_email(self, obj):
        return obj.resume.email if obj.resume_id else '—'

    @admin.display(description='Verified techs')
    def verified_count(self, obj):
        return len(obj.verified_technologies or [])


@admin.register(models.ApplicationOnHold)
class ApplicationOnHoldAdmin(admin.ModelAdmin):
    list_display = ('email', 'position', 'hold_until', 'is_active', 'reason_short', 'created_at')
    list_filter = ('position',)
    search_fields = ('email', 'reason', 'resume__full_name')
    raw_id_fields = ('resume', 'position')
    readonly_fields = ('id', 'created_at')
    actions = ['delete_expired_holds', 'delete_all_selected_holds']

    @admin.display(boolean=True, description='Active now')
    def is_active(self, obj):
        return bool(obj.hold_until and obj.hold_until > timezone.now())

    @admin.display(description='Reason')
    def reason_short(self, obj):
        text = (obj.reason or '').strip()
        return text[:80] + ('…' if len(text) > 80 else '') if text else '—'

    @admin.action(description='Delete expired holds (selected)')
    def delete_expired_holds(self, request, queryset):
        deleted, _ = queryset.filter(hold_until__lte=timezone.now()).delete()
        self.message_user(request, f'Deleted {deleted} expired hold(s).', messages.SUCCESS)

    @admin.action(description='Delete selected holds (active or expired)')
    def delete_all_selected_holds(self, request, queryset):
        deleted, _ = queryset.delete()
        self.message_user(request, f'Deleted {deleted} hold(s).', messages.SUCCESS)


@admin.register(models.ScreeningConfig)
class ScreeningConfigAdmin(admin.ModelAdmin):
    list_display = (
        'passing_score_threshold',
        'disable_application_holds',
        'skip_ai_screening_for_testing',
        'skip_kyc_for_testing',
        'disable_surveillance_for_testing',
        'updated_at',
    )
    fields = (
        'passing_score_threshold',
        'disable_application_holds',
        'skip_ai_screening_for_testing',
        'skip_kyc_for_testing',
        'disable_surveillance_for_testing',
    )
    readonly_fields = ('updated_at',)

    def has_add_permission(self, request):
        if models.ScreeningConfig.objects.exists():
            return False
        return super().has_add_permission(request)

    def changelist_view(self, request, extra_context=None):
        if not models.ScreeningConfig.objects.exists():
            models.ScreeningConfig.objects.create()
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(models.Resume)
class ResumeAdmin(admin.ModelAdmin):
    list_display = (
        'full_name',
        'email',
        'applied_position',
        'is_email_verified',
        'pipeline_summary',
        'uploaded_at',
    )
    list_filter = ('is_email_verified', 'applied_position')
    search_fields = ('full_name', 'email')
    readonly_fields = ('id', 'uploaded_at', 'pipeline_summary_detail')
    raw_id_fields = ('applied_position',)
    inlines = [VettingPipelineRecordInline, CandidateVettingProgressInline]
    fieldsets = (
        (None, {
            'fields': (
                'full_name',
                'email',
                'applied_position',
                'is_email_verified',
                'resume_file',
            ),
        }),
        ('Pipeline overview', {
            'fields': ('pipeline_summary_detail',),
            'description': 'Edit individual stages below. Use actions to create missing stages.',
        }),
        ('Security', {
            'classes': ('collapse',),
            'fields': ('password', 'verification_token'),
        }),
        ('Meta', {'fields': ('id', 'uploaded_at')}),
    )
    actions = [
        'ensure_all_pipeline_stages',
        'set_pipeline_invited_from_current',
        'clear_application_holds_for_email',
        'clear_holds_and_reset_on_hold_stages',
    ]

    @admin.display(description='Pipeline')
    def pipeline_summary(self, obj):
        records = {r.stage: r.status for r in obj.pipeline_records.all()}
        if not records:
            return format_html('<span style="color:#999">No stages</span>')
        parts = [f'{stage[:3]}:{records.get(stage, "—")}' for stage in PIPELINE_STAGES]
        return ' | '.join(parts)

    @admin.display(description='Current pipeline status')
    def pipeline_summary_detail(self, obj):
        if not obj.pk:
            return 'Save the resume first, then use “Ensure all pipeline stages”.'
        lines = []
        for stage in PIPELINE_STAGES:
            record = obj.pipeline_records.filter(stage=stage).first()
            if record:
                lines.append(f'{record.get_stage_display()}: {record.get_status_display()} (score: {record.score or "—"})')
            else:
                lines.append(f'{dict(models.VettingPipelineRecord.STAGE_CHOICES).get(stage, stage)}: not created')
        return format_html('<br>'.join(lines))

    @admin.action(description='Ensure all pipeline stages exist (pending if missing)')
    def ensure_all_pipeline_stages(self, request, queryset):
        created = 0
        for resume in queryset:
            for stage in PIPELINE_STAGES:
                _, was_created = models.VettingPipelineRecord.objects.get_or_create(
                    resume=resume,
                    stage=stage,
                    defaults={'status': 'pending'},
                )
                if was_created:
                    created += 1
        self.message_user(
            request,
            f'Created {created} missing pipeline record(s).',
            messages.SUCCESS,
        )

    @admin.action(description='Set next non-passed stage to Invited (skip passed)')
    def set_pipeline_invited_from_current(self, request, queryset):
        updated = 0
        for resume in queryset:
            for stage in PIPELINE_STAGES:
                record = models.VettingPipelineRecord.objects.filter(
                    resume=resume, stage=stage,
                ).first()
                if record and record.status == 'passed':
                    continue
                if record:
                    if record.status in ('pending', 'failed', 'on_hold'):
                        record.status = 'invited'
                        record.save(update_fields=['status', 'updated_at'])
                        updated += 1
                else:
                    models.VettingPipelineRecord.objects.create(
                        resume=resume, stage=stage, status='invited',
                    )
                    updated += 1
                break
        self.message_user(
            request,
            f'Updated {updated} stage(s) to invited.',
            messages.SUCCESS,
        )

    @admin.action(description='Remove active holds for selected candidates')
    def clear_application_holds_for_email(self, request, queryset):
        emails = list(queryset.values_list('email', flat=True))
        deleted, _ = models.ApplicationOnHold.objects.filter(
            email__in=emails,
            hold_until__gt=timezone.now(),
        ).delete()
        self.message_user(
            request,
            f'Removed {deleted} active hold(s) for {len(emails)} candidate(s).',
            messages.SUCCESS,
        )

    @admin.action(description='Remove holds + set on-hold pipeline stages back to In progress')
    def clear_holds_and_reset_on_hold_stages(self, request, queryset):
        emails = list(queryset.values_list('email', flat=True))
        deleted, _ = models.ApplicationOnHold.objects.filter(email__in=emails).delete()
        reset = models.VettingPipelineRecord.objects.filter(
            resume__email__in=emails,
            status='on_hold',
        ).update(status='in_progress')
        self.message_user(
            request,
            f'Removed {deleted} hold record(s) and reset {reset} pipeline stage(s) from on hold.',
            messages.SUCCESS,
        )


class StackSkillInline(admin.TabularInline):
    model = models.StackSkill
    extra = 0
    ordering = ('sort_order',)


@admin.register(models.VettingStack)
class VettingStackAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    search_fields = ('name', 'slug')
    inlines = [StackSkillInline]


@admin.register(models.VettingSkill)
class VettingSkillAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'slug', 'technology', 'content_version', 'content_owner', 'review_practicals', 'is_active',
    )
    search_fields = ('name', 'slug')
    list_filter = ('is_active', 'review_practicals')
    raw_id_fields = ('technology',)


class ServiceVettingStackInline(admin.TabularInline):
    model = models.ServiceVettingStack
    extra = 0


@admin.register(models.SkillCertificate)
class SkillCertificateAdmin(admin.ModelAdmin):
    list_display = ('resume', 'skill', 'stack', 'verified_at', 'expires_at', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('resume__email', 'skill__name')
    raw_id_fields = ('resume', 'freelancer', 'skill', 'stack')


admin.site.register(models.ScreeningResult)
