"""Guardarraíles de parse_salary: casos reales que antes explotaban el ranking de €/h."""
import pytest

from jobs_es.normalize import MAX_HOURLY, parse_salary, period_hourly


@pytest.mark.parametrize("text,expect", [
    # mezcla anual/mensual: "12,90 €/h (SBA: 22.700€ / 2.070€ brutos/mes)" → 12,90, no 70,8
    ("Salario inicial: 12,90€/h brutos (SBA: 22.700€ aprox. / 2.070€ brutos/mes por ETT en 11 pagas)",
     12.9),
    # mezcla mes/hora: "2.092,80 €/mes. 13,08 €/hora" → 13,08, no 52,9
    ("Retribución 2.092,80 euros brutos al mes. 13,08 bruto/hora",
     13.08),
    # controles sanos
    ("Salario: 1.500€ brutos/mes", 1500 / 175),
    ("Retribución 25.000€ brutos/año", 25000 / 2100),
    ("10,40€ por hora", 10.4),
    # "Plus: 75 €" con 'horario' colando la unidad → no es salario → None
    ("Horario: 1ª servicio media jornada 6:00 a 18:00 h. Plus: 75 € por servicio",
     None),
    # comisión inflada (>MAX_HOURLY) → None
    ("6.000€ brutos/mes más comisiones", None),
])
def test_parse_salary_guards(text, expect):
    v, txt = parse_salary(text)
    assert v == pytest.approx(expect), f"texto={text!r} → {v} (esperado {expect}, match={txt!r})"


def test_max_hourly_nonzero():
    assert 0 < MAX_HOURLY <= 80


@pytest.mark.parametrize("sal,period,expect", [
    ("12.50", "hour", 12.5),
    ("1250", "month", 1250 / 175),
    ("26000", "year", 26000 / 2100),
    ("500", "week", 12.5),
    ("26000", None, None),   # periodo desconocido: no adivinar
    ("99999", "hour", None),  # techo
])
def test_period_hourly(sal, period, expect):
    assert period_hourly(sal, period) == pytest.approx(expect)