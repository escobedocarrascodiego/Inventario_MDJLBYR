from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from .models import Bien, ParametroSistema


@admin.register(ParametroSistema)
class ParametroSistemaAdmin(admin.ModelAdmin):
    list_display = ('anio_fiscal', 'valor_uit', 'divisor_umbral_depreciacion', 'es_activo')
    list_filter = ('es_activo',)
    ordering = ('-anio_fiscal',)
    list_editable = ('es_activo',)


@admin.register(Bien)
class BienAdmin(admin.ModelAdmin):
    list_display = ('codigo_patrimonial', 'descripcion', 'valor_adquisicion', 'valor_neto_actualizado', 'estado')
    readonly_fields = ('valor_neto',)
    actions = ('calcular_valor_historico',)

    class CalcularValorHistoricoForm(forms.Form):
        fecha_corte = forms.DateField(
            required=True,
            widget=forms.DateInput(attrs={'type': 'date'})
        )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'calcular-valor-historico/',
                self.admin_site.admin_view(self.calcular_valor_historico_view),
                name='inventario_bien_calcular_valor_historico',
            ),
        ]
        return custom_urls + urls

    def calcular_valor_historico(self, request, queryset):
        ids = ",".join(str(pk) for pk in queryset.values_list('pk', flat=True))
        url = reverse('admin:inventario_bien_calcular_valor_historico')
        return redirect(f"{url}?ids={ids}")
    calcular_valor_historico.short_description = "Calcular Valor Histórico"

    def calcular_valor_historico_view(self, request):
        ids = request.POST.get('ids', '') or request.GET.get('ids', '')
        id_list = [pk for pk in ids.split(',') if pk.isdigit()]
        queryset = Bien.objects.filter(pk__in=id_list)

        form = self.CalcularValorHistoricoForm(request.POST or None)
        resultados = []
        fecha_corte = None

        if request.method == 'POST' and form.is_valid():
            fecha_corte = form.cleaned_data['fecha_corte']
            config = ParametroSistema.get_config_for_year(fecha_corte.year)
            if config and config.anio_fiscal != fecha_corte.year:
                messages.warning(
                    request,
                    f"No se encontró configuración para {fecha_corte.year}. "
                    f"Se usó la más antigua registrada ({config.anio_fiscal})."
                )
            elif not config:
                messages.warning(
                    request,
                    "No hay parámetros registrados. Se usarán valores por defecto."
                )

            for bien in queryset:
                valor_historico = bien.valor_neto_en(fecha_corte)
                resultados.append({
                    'bien': bien,
                    'valor_historico': valor_historico,
                })

        context = dict(
            self.admin_site.each_context(request),
            form=form,
            resultados=resultados,
            fecha_corte=fecha_corte,
            opts=self.model._meta,
            queryset=queryset,
            ids=ids,
        )
        return TemplateResponse(
            request,
            'admin/inventario/bien/calcular_valor_historico.html',
            context
        )
