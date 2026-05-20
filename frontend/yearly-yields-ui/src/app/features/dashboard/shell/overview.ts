import { ChangeDetectorRef, Component, DestroyRef, OnInit, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { MatTooltipModule } from '@angular/material/tooltip';
import { NgxEchartsDirective } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { forkJoin, skip, switchMap } from 'rxjs';

import { Store } from '@ngrx/store';
import { Crop, CropCycle, CropService } from '../../../core/services/crop.service';
import { DashboardService, ChatResponse, WeeklySummary } from '../../../core/services/dashboard.service';
import { FieldService, GrowingArea } from '../../../core/services/field.service';
import { SensorReading } from '../../../core/services/reading.service';
import { selectUserRole } from '../../../store/auth/auth.selectors';
import { BRAND } from '../../../core/brand';

const CHART_COLORS = [
  '#4e79a7', // steel blue
  '#b07d0e', // deep amber — readable on both parchment and white
  '#e15759', // red
  '#76b7b2', // teal
  '#9467bd', // purple
  '#f28e2b', // orange
  '#59a14f', // green
  '#17becf', // cyan
  '#b07aa1', // mauve
  '#ff9da7', // pink
];

@Component({
  selector: 'app-overview',
  standalone: true,
  imports: [
    FormsModule,
    MatButtonModule,
    MatButtonToggleModule,
    MatCardModule,
    MatChipsModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    MatTooltipModule,
    NgxEchartsDirective,
  ],
  templateUrl: './overview.html',
  styleUrl: './overview.scss',
})
export class OverviewComponent implements OnInit {
  private cropService = inject(CropService);
  private fieldService = inject(FieldService);
  protected dashboardService = inject(DashboardService);
  private store = inject(Store);
  private destroyRef = inject(DestroyRef);
  private cdr = inject(ChangeDetectorRef);

  chatInput = '';
  chatOpen = false;
  chatLoading = false;
  chatResponse: ChatResponse | null = null;

  get chatResponseOptions(): EChartsOption | null {
    return this.chatResponse?.type === 'chart' ? this._buildChatChartOptions(this.chatResponse) : null;
  }

  sensorLoading = true;
  cycleLoading = true;
  weeklyLoading = true;
  yoyLoading = true;

  sensorTrendOptions: EChartsOption = {};
  cycleProgressOptions: EChartsOption = {};
  weeklySummaryOptions: EChartsOption = {};
  yoyYieldOptions: EChartsOption = {};

  sensorGroupBy: 'area' | 'station' = 'station'; // overridden by role in ngOnInit
  selectedAreaIds: string[] = [];
  allAreas: GrowingArea[] = [];

  allCrops: Crop[] = [];

  private _readings: SensorReading[] = [];
  private _currentSeasonCycles: CropCycle[] = [];
  private _areaMap = new Map<string, string>();
  private _areaStationMap = new Map<string, string>();
  private _cropMap = new Map<string, string>();

  get openFieldAreas(): GrowingArea[] {
    return this.allAreas.filter(a => a.area_type === 'open_field');
  }

  get greenhouseAreas(): GrowingArea[] {
    return this.allAreas.filter(a => a.area_type === 'dwc_greenhouse');
  }

  ngOnInit(): void {
    this.dashboardService.chatOpen$.pipe(skip(1), takeUntilDestroyed(this.destroyRef)).subscribe(v => { this.chatOpen = v; this.cdr.detectChanges(); });
    this.dashboardService.chatLoading$.pipe(skip(1), takeUntilDestroyed(this.destroyRef)).subscribe(v => { this.chatLoading = v; this.cdr.detectChanges(); });
    this.dashboardService.chatResponse$.pipe(skip(1), takeUntilDestroyed(this.destroyRef)).subscribe(v => { this.chatResponse = v; this.cdr.detectChanges(); });

    this.store.select(selectUserRole).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(role => {
      this.sensorGroupBy = role === 'farmer' ? 'area' : 'station';
    });

    forkJoin({
      areas: this.fieldService.list(),
      crops: this.cropService.listCrops(),
    }).pipe(
      switchMap(({ areas, crops }) => {
        this.allAreas = areas;
        this.allCrops = crops;
        this._areaMap = new Map(areas.map(a => [a.id, a.name]));
        this._areaStationMap = new Map(areas.map(a => [a.id, a.nws_station_id ?? 'Unknown']));
        this._cropMap = new Map(crops.map(c => [c.id, c.name]));

        return forkJoin({
          cycles:    this.dashboardService.getCurrentSeasonCycles(),
          readings:  this.dashboardService.getRecentReadings(),
          summaries: this.dashboardService.getWeeklySummaries(),
          allCycles: this.dashboardService.getAllCycles(),
        });
      }),
    ).subscribe({
      next: ({ cycles, readings, summaries, allCycles }) => {
        this._currentSeasonCycles = cycles;
        this.cycleProgressOptions = this.buildCropCycleProgressOptions(cycles);
        this.cycleLoading = false;

        this._readings = readings;
        this.sensorTrendOptions = this.buildSensorTrendOptions();
        this.sensorLoading = false;

        this.weeklySummaryOptions = this.buildWeeklySummaryOptions(summaries);
        this.weeklyLoading = false;

        this.yoyYieldOptions = this.buildYoYYieldOptions(allCycles);
        this.yoyLoading = false;
      },
      error: err => {
        console.error('Dashboard load failed', err);
        this.sensorLoading = false;
        this.cycleLoading = false;
        this.weeklyLoading = false;
        this.yoyLoading = false;
      },
    });
  }

  onGroupByChange(): void {
    this.selectedAreaIds = [];
    this.sensorTrendOptions = this.buildSensorTrendOptions();
  }

  rebuildSensorChart(): void {
    this.sensorTrendOptions = this.buildSensorTrendOptions();
  }

  rebuildCycleChart(): void {
    this.cycleProgressOptions = this.buildCropCycleProgressOptions(this._currentSeasonCycles);
  }

  sendMessage(override?: string): void {
    const msg = (override ?? this.chatInput).trim();
    if (!msg || this.chatLoading) return;
    this.chatInput = '';
    this.dashboardService.sendChat(msg);
  }

  closeChat(): void {
    this.dashboardService.closeChat();
  }

  private _buildChatChartOptions(res: ChatResponse): EChartsOption {
    if (!res.x_labels || !res.series) return {};

    const isLine = res.chart_type === 'line_multi';

    return {
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { left: 48, right: 16, top: 16, bottom: 48, containLabel: true },
      xAxis: { type: 'category', data: res.x_labels },
      yAxis: {
        type: 'value',
        name: res.y_axis_label ?? '',
        nameLocation: 'middle',
        nameGap: 40,
      },
      series: res.series.map((s, i) => ({
        name: s.name,
        type: isLine ? 'line' : 'bar',
        data: s.data,
        color: CHART_COLORS[i % CHART_COLORS.length],
        ...(isLine ? { smooth: true, symbolSize: 5 } : {}),
        ...(res.chart_type === 'bar_stacked' ? { stack: 'total' } : {}),
      })),
    };
  }

  private buildSensorTrendOptions(): EChartsOption {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 30);
    const recent = this._readings.filter(r => new Date(r.read_at) >= cutoff);

    if (!recent.length) return this.emptyChart('Sensor Readings — Last 30 Days');

    const series: any[] = [];
    let colorIdx = 0;

    if (this.sensorGroupBy === 'station') {
      const byStation = new Map<string, SensorReading[]>();
      for (const r of recent) {
        const station = this._areaStationMap.get(r.growing_area_id) ?? 'Unknown';
        if (!byStation.has(station)) byStation.set(station, []);
        byStation.get(station)!.push(r);
      }

      for (const [station, stationReadings] of byStation) {
        const sorted = [...stationReadings]
          .filter(r => r.temperature != null)
          .sort((a, b) => new Date(a.read_at).getTime() - new Date(b.read_at).getTime());
        const step = Math.max(1, Math.floor(sorted.length / 200));
        const sampled = sorted.filter((_, i) => i % step === 0);
        if (!sampled.length) continue;
        series.push({
          name: station,
          type: 'line',
          smooth: true,
          symbol: 'none',
          color: CHART_COLORS[colorIdx++ % CHART_COLORS.length],
          data: sampled.map(r => [r.read_at, r.temperature]),
        });
      }
    } else {
      const filterIds = this.selectedAreaIds.length ? new Set(this.selectedAreaIds) : null;
      const byArea = new Map<string, SensorReading[]>();
      for (const r of recent) {
        if (filterIds && !filterIds.has(r.growing_area_id)) continue;
        if (!byArea.has(r.growing_area_id)) byArea.set(r.growing_area_id, []);
        byArea.get(r.growing_area_id)!.push(r);
      }

      for (const [areaId, areaReadings] of byArea) {
        const sorted = [...areaReadings].sort(
          (a, b) => new Date(a.read_at).getTime() - new Date(b.read_at).getTime(),
        );
        const step = Math.max(1, Math.floor(sorted.length / 200));
        const sampled = sorted.filter((_, i) => i % step === 0);
        series.push({
          name: this._areaMap.get(areaId) ?? areaId.slice(0, 8),
          type: 'line',
          smooth: true,
          symbol: 'none',
          emphasis: { focus: 'series' },
          color: CHART_COLORS[colorIdx++ % CHART_COLORS.length],
          data: sampled.map(r => [r.read_at, r.temperature]),
        });
      }
    }

    const isAreaMode = this.sensorGroupBy === 'area';
    return {
      title: { text: 'Sensor Readings — Last 30 Days', left: 16, top: 8, textStyle: { fontSize: 14 } },
      tooltip: {
        trigger: isAreaMode ? 'item' : 'axis',
        formatter: (params: any) => {
          const pts = Array.isArray(params) ? params : [params];
          if (!pts.length) return '';
          const ts = pts[0]?.axisValue ?? pts[0]?.value?.[0] ?? pts[0]?.data?.[0];
          const d = ts != null ? new Date(ts).toLocaleDateString() : '';
          return (d ? `${d}<br>` : '') + pts
            .filter((x: any) => x.value?.[1] != null)
            .map((x: any) => `${x.marker}${x.seriesName}: ${(+x.value[1]).toFixed(1)}°F`)
            .join('<br>');
        },
      },
      legend: { bottom: 0, type: 'scroll' },
      grid: { top: 48, bottom: 48, left: 60, right: 24 },
      xAxis: { type: 'time', axisLabel: { formatter: (v: number) => new Date(v).toLocaleDateString() } },
      yAxis: { type: 'value', name: '°F', nameLocation: 'end', axisLabel: { formatter: '{value}°' } },
      series,
    };
  }

  private buildCropCycleProgressOptions(cycles: CropCycle[]): EChartsOption {
    const active = cycles.filter(c => c.status === 'active' && c.crop_id);
    if (!active.length) return this.emptyChart('Crop Cycle Progress');

    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const PHASE_COLORS: Record<string, string> = {
      Seeding: '#59a14f',
      Growing: '#4e79a7',
      Harvest: BRAND.harvestGold,
    };

    const cropById = new Map<string, Crop>(this.allCrops.map(c => [c.id, c]));

    const rows = active.map(c => {
      const crop = cropById.get(c.crop_id!);
      const seedingDays = crop?.seeding_days ?? 10;
      const growingDays = crop?.growing_days ?? 60;
      const harvestDays = crop?.harvest_days ?? 20;
      const totalDays = seedingDays + growingDays + harvestDays;

      const planted = new Date(c.planted_at);
      planted.setHours(0, 0, 0, 0);
      const elapsed = Math.min(
        Math.max(0, Math.floor((today.getTime() - planted.getTime()) / 86_400_000)),
        totalDays,
      );
      const remaining = totalDays - elapsed;

      let phase = 'Seeding';
      if (elapsed > seedingDays + growingDays) phase = 'Harvest';
      else if (elapsed > seedingDays) phase = 'Growing';

      const areaName = this._areaMap.get(c.growing_area_id) ?? 'Unknown';
      const cropName = crop?.name ?? '';
      const label = cropName ? `${areaName} (${cropName})` : areaName;

      return { label, elapsed, remaining, totalDays, phase, cycle: c };
    });

    const maxDays = Math.max(...rows.map(r => r.totalDays));

    return {
      title: { text: 'Crop Cycle Progress', left: 16, top: 8, textStyle: { fontSize: 14 } },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (_params: any) => {
          const params = Array.isArray(_params) ? _params : [_params];
          const idx = params[0]?.dataIndex;
          if (idx == null) return '';
          const row = rows[idx];
          const lines = [
            `<b>${row.label}</b>`,
            `Phase: ${row.phase}`,
            `Day ${row.elapsed} of ${row.totalDays}`,
          ];
          if (row.cycle.actual_yield != null) {
            lines.push(`Yield so far: ${row.cycle.actual_yield} ${row.cycle.yield_unit}`);
          }
          return lines.join('<br>');
        },
      },
      legend: { show: false },
      grid: { top: 40, bottom: 24, left: 220, right: 60 },
      xAxis: { type: 'value', max: maxDays, name: 'days', nameLocation: 'end' },
      yAxis: { type: 'category', data: rows.map(r => r.label), axisLabel: { width: 200, overflow: 'truncate' as const } },
      series: [
        {
          name: 'Elapsed',
          type: 'bar',
          stack: 'cycle',
          data: rows.map(r => ({
            value: r.elapsed,
            itemStyle: { color: PHASE_COLORS[r.phase] },
          })),
          label: {
            show: true,
            position: 'inside',
            formatter: (p: any) => rows[p.dataIndex]?.phase ?? '',
            color: '#fff',
            fontSize: 11,
          },
        },
        {
          name: 'Remaining',
          type: 'bar',
          stack: 'cycle',
          itemStyle: { color: 'rgba(150,150,150,0.15)', borderColor: 'rgba(150,150,150,0.25)', borderWidth: 1 },
          data: rows.map(r => r.remaining),
          label: { show: false },
        },
      ],
    };
  }

  private buildWeeklySummaryOptions(summaries: WeeklySummary[]): EChartsOption {
    if (!summaries.length) return this.emptyChart('Weekly Sensor Averages');

    const byWeek = new Map<string, { temps: number[]; humidities: number[] }>();
    for (const s of summaries) {
      if (!byWeek.has(s.week_label)) byWeek.set(s.week_label, { temps: [], humidities: [] });
      const bucket = byWeek.get(s.week_label)!;
      if (s.avg_temp_f != null) bucket.temps.push(s.avg_temp_f);
      if (s.avg_humidity_pct != null) bucket.humidities.push(s.avg_humidity_pct);
    }

    const labels = [...byWeek.keys()];
    const avg = (arr: number[]) => arr.length ? +(arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(1) : null;
    const avgTemp = labels.map(l => avg(byWeek.get(l)!.temps));
    const avgHumidity = labels.map(l => avg(byWeek.get(l)!.humidities));

    return {
      title: {
        text: 'Weekly Sensor Averages',
        subtext: 'All stations averaged  ·  °F  /  %',
        left: 16,
        top: 8,
        textStyle: { fontSize: 14 },
        subtextStyle: { fontSize: 11, color: '#757575' },
      },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const pts = Array.isArray(params) ? params : [params];
          const week = pts[0]?.axisValue ?? '';
          const lines = pts.map((x: any) => {
            const unit = x.seriesName === 'Avg Temp' ? '°F' : '%';
            return `${x.marker}<b>${x.seriesName}:</b> ${x.value ?? '—'}${unit}`;
          });
          return `<b>${week}</b><br>${lines.join('<br>')}`;
        },
      },
      grid: { top: 64, bottom: 24, left: 60, right: 60 },
      xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: [
        { type: 'value', axisLabel: { formatter: '{value}°' } },
        { type: 'value', axisLabel: { formatter: '{value}%' } },
      ],
      series: [
        {
          name: 'Avg Temp',
          type: 'line',
          areaStyle: { opacity: 0.2 },
          smooth: true,
          symbolSize: 6,
          color: '#4e79a7',
          yAxisIndex: 0,
          data: avgTemp,
        },
        {
          name: 'Avg Humidity',
          type: 'line',
          areaStyle: { opacity: 0.15 },
          smooth: true,
          symbolSize: 6,
          color: BRAND.harvestGold,
          yAxisIndex: 1,
          data: avgHumidity,
        },
      ],
    };
  }

  private buildYoYYieldOptions(cycles: CropCycle[]): EChartsOption {
    const harvested = cycles.filter(c => c.status === 'harvested' && c.actual_yield != null);
    if (!harvested.length) return this.emptyChart('Year-Over-Year Actual Yields');

    const years = [...new Set(harvested.map(c => c.season_year))].sort();
    const cropIds = [...new Set(harvested.map(c => c.crop_id).filter(Boolean) as string[])];

    const series = cropIds.map((cropId, i) => ({
      name: this._cropMap.get(cropId) ?? cropId.slice(0, 8),
      type: 'bar' as const,
      color: CHART_COLORS[i % CHART_COLORS.length],
      data: years.map(yr => {
        const matches = harvested.filter(c => c.season_year === yr && c.crop_id === cropId);
        return matches.reduce((sum, c) => sum + (c.actual_yield ?? 0), 0);
      }),
    }));

    return {
      title: { text: 'Year-Over-Year Actual Yields', left: 16, top: 8, textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { bottom: 0 },
      grid: { top: 48, bottom: 40, left: 60, right: 24 },
      xAxis: { type: 'category', data: years.map(String) },
      yAxis: { type: 'value', name: 'yield' },
      series,
    };
  }

  private emptyChart(title: string): EChartsOption {
    return {
      title: { text: title, left: 16, top: 8, textStyle: { fontSize: 14 } },
      graphic: [{
        type: 'text',
        left: 'center',
        top: 'middle',
        style: { text: 'No data yet', fontSize: 14, fill: '#9e9e9e' },
      }],
    };
  }
}
