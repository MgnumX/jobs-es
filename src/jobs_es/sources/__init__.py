"""Importar los módulos registra sus fuentes en jobs_es.SOURCES."""
from . import amazon, correos, dia, infojobs, jobandtalent, jobeka, lidl, mercadona, randstad  # noqa: F401
# _adecco_disabled.py NO se importa: endpoint muerto, ver su docstring.
# ponytail: fuentes hoteleras (turijobs, fuerte, melia, barcelo, riu, palladium)
# fuera de registro — 100% hostelería/turismo, ya no encaja con enfoque PLAZA.
# iman colgado: hang >60s, reintentar cuando arregle timeout.
