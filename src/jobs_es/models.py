import hashlib
from dataclasses import dataclass, asdict


@dataclass
class Job:
    source: str          # turijobs | jobandtalent | amazon | adecco
    url: str
    title: str
    company: str = ""
    city: str = ""
    province: str = ""
    sector: str = ""     # hosteleria | logistica | comercio | temporada | otros
    salary_text: str = ""
    hourly: float | None = None   # €/h normalizado (None si desconocido)
    housing: bool = False         # alojamiento incluido
    food: bool = False            # comida incluida
    direct: bool = False          # True = aplica directo al empleador (sin ETT)
    urgent: bool = False          # incorporación inmediata / urgente
    posted_at: str = ""           # ISO o texto original
    text: str = ""                # snippet descripción para clasificar/auditar

    @property
    def id(self) -> str:
        try:
            from .normalize import canonical_url
            url = canonical_url(self.url)
        except Exception:
            url = self.url
        return hashlib.sha1(f"{self.source}|{url}".encode()).hexdigest()[:16]

    def row(self) -> dict:
        d = asdict(self)
        try:
            from .normalize import canonical_url
            d["canonical_url"] = canonical_url(self.url)
            d["url"] = d["canonical_url"]
        except Exception:
            d["canonical_url"] = self.url
        d["id"] = self.id
        d.pop("text", None)  # no persistir el snippet completo
        return d

    def to_json(self) -> dict:
        return {
            "title": self.title.strip(),
            "url": self.url,
            "company": self.company,
            "city": self.city,
            "province": self.province,
            "sector": self.sector or "otros",
            "salary": self.salary_text or "",
            "hourly": round(self.hourly, 2) if self.hourly else None,
            "housing": int(self.housing),
            "food": int(self.food),
            "direct": int(self.direct),
            "source": self.source,
            "posted": self.posted_at[:10] if self.posted_at else "",
        }
