from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Metric(BaseModel):
    value: str | None = None
    change_pct: str | None = None
    quality: str = "reliable"
    reason: str | None = None
    unit: str | None = None
    currency: str | None = None
    samples: int | None = None
    coverage: str | None = None


class Meta(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    role: str
    period_from: datetime = Field(alias="from")
    to: datetime
    timezone: str
    clickhouse: str
    definitions: dict[str, str]


class SeriesPoint(BaseModel):
    bucket: str
    clicks: int = 0
    conversions: int = 0
    cr: str | None = None
    reached: int | None = None
    reached_rate: str | None = None
    engagement: str | None = None
    mobile: str | None = None
    desktop: str | None = None


class SourceRow(BaseModel):
    key: str
    label: str
    kind: str
    clicks: int
    conversions: int
    cr: str | None = None
    epc: str | None = None
    commission: str | None = None
    currency: str | None = None
    commission_reason: str | None = None
    share: str | None = None
    roi: str | None = None
    roi_reason: str | None = None


class EntityRow(BaseModel):
    id: str | None = None
    label: str
    href: str | None = None
    clicks: int = 0
    conversions: int = 0
    cr: str | None = None
    commission: str | None = None
    currency: str | None = None
    epc: str | None = None
    ownership: str | None = None
    commission_reason: str | None = None
    reached_rate: str | None = None
    engagement: str | None = None
    bounce: str | None = None
    quality: str = "reliable"


class Efficiency(BaseModel):
    dimension: str
    metric: str
    formula: str
    rows: list[EntityRow]


class OverviewResponse(BaseModel):
    meta: Meta
    kpis: dict[str, Metric]
    timeseries: list[SeriesPoint]
    sources: list[SourceRow]
    source_total: int
    source_quality: str
    source_reason: str | None = None
    offers: list[EntityRow]
    efficiency: Efficiency


class FunnelStep(BaseModel):
    key: str
    label: str
    value: str | None = None
    rate: str | None = None
    available: bool
    quality: str
    reason: str | None = None
    definition: str


class FunnelLoss(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_label: str = Field(alias="from")
    to_label: str = Field(alias="to")
    retained: str | None = None
    lost: str | None = None
    available: bool


class StatusSlice(BaseModel):
    key: str
    label: str
    count: int


class FunnelResponse(BaseModel):
    meta: Meta
    steps: list[FunnelStep]
    losses: list[FunnelLoss]
    statuses: list[StatusSlice]


class ScrollPoint(BaseModel):
    milestone: int
    value: str | None = None
    quality: str
    reason: str | None = None


class PathEdge(BaseModel):
    source: str
    target: str
    value: int


class PageRow(BaseModel):
    page: str
    views: int
    engagement: str | None = None
    quality: str = "reliable"


class BehaviorResponse(BaseModel):
    meta: Meta
    kpis: dict[str, Metric]
    scroll: list[ScrollPoint]
    paths: list[PathEdge]
    pages: list[PageRow]


class SourcesResponse(BaseModel):
    meta: Meta
    points: list[SourceRow]
    distribution: list[SourceRow]
    rows: list[SourceRow]
    source_quality: str
    source_reason: str | None = None


class QualityResponse(BaseModel):
    meta: Meta
    kpis: dict[str, Metric]
    series: list[SeriesPoint]
    comparison: list[EntityRow]
    dimension: str


class SlowPage(BaseModel):
    page: str
    lcp: str | None = None
    weight: str | None = None
    samples: int = 0
    quality: str = "reliable"


class PerformanceResponse(BaseModel):
    meta: Meta
    kpis: dict[str, Metric]
    series: list[SeriesPoint]
    pages: list[SlowPage]


class FilterOption(BaseModel):
    id: int
    name: str


class TrafficOption(BaseModel):
    code: str
    label: str


class FiltersResponse(BaseModel):
    role: str
    offers: list[FilterOption]
    campaigns: list[FilterOption]
    links: list[FilterOption]
    partners: list[FilterOption]
    sites: list[FilterOption]
    traffic_sources: list[TrafficOption]
    devices: list[str]
