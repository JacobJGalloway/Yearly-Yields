import { Component, DestroyRef, ElementRef, OnInit, ViewChild, inject } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatButtonToggleModule } from '@angular/material/button-toggle';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSelectModule } from '@angular/material/select';
import { NgxEchartsDirective } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { forkJoin } from 'rxjs';

import { Store } from '@ngrx/store';
import { Crop, CropCycle, CropService } from '../../../core/services/crop.service';
import { DashboardService, ChatMessage, WeeklySummary } from '../../../core/services/dashboard.service';
import { FieldService, GrowingArea } from '../../../core/services/field.service';
import { SensorReading } from '../../../core/services/reading.service';
import { selectUserRole } from '../../../store/auth/auth.selectors';

const CHART_COLORS = [
  '#4e79a7', // steel blue
  '#C9A227', // harvest gold (brand)
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
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
    MatSelectModule,
    NgxEchartsDirective,
  ],
  templateUrl: './overview.html',
  styleUrl: './overview.scss',
})
export class OverviewComponent implements OnInit {
  @ViewChild('chatLog') private chatLogRef!: ElementRef<HTMLDivElement>;

  private cropService = inject(CropService);
  private fieldService = inject(FieldService);
  private dashboardService = inject(DashboardService);
  private store = inject(Store);
  private destroyRef = inject(DestroyRef);

  chatInput = '';
  chatOpen = false;
  chatLoading = false;
  chatHistory: ChatMessage[] = [];

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
    this.store.select(selectUserRole).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(role => {
      this.sensorGroupBy = role === 'farmer' ? 'area' : 'station';
    });

    // Phase 1: fast metadata needed by all charts
    forkJoin({
      areas: this.fieldService.list(),
      crops: this.cropService.listCrops(),
    }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: ({ areas, crops }) => {
        this.allAreas = areas;
        this.allCrops = crops;
        this._areaMap = new Map(areas.map(a => [a.id, a.name]));
        this._areaStationMap = new Map(areas.map(a => [a.id, a.nws_station_id ?? 'Unknown']));
        this._cropMap = new Map(crops.map(c => [c.id, c.name]));

        // Phase 2: chart queries fire in parallel — each renders independently
        this.dashboardService.getCurrentSeasonCycles()
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({
            next: cycles => {
              this._currentSeasonCycles = cycles;
              this.cycleLoading = false;
              this.cycleProgressOptions = this.buildCropCycleProgressOptions(cycles);
            },
            error: () => { this.cycleLoading = false; },
          });

        this.dashboardService.getRecentReadings()
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({
            next: readings => {
              this._readings = readings;
              this.sensorTrendOptions = this.buildSensorTrendOptions();
              this.sensorLoading = false;
            },
            error: () => { this.sensorLoading = false; },
          });

        this.dashboardService.getWeeklySummaries()
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({
            next: summaries => {
              this.weeklySummaryOptions = this.buildWeeklySummaryOptions(summaries);
              this.weeklyLoading = false;
            },
            error: () => { this.weeklyLoading = false; },
          });

        this.dashboardService.getAllCycles()
          .pipe(takeUntilDestroyed(this.destroyRef))
          .subscribe({
            next: allCycles => {
              this.yoyYieldOptions = this.buildYoYYieldOptions(allCycles);
              this.yoyLoading = false;
            },
            error: () => { this.yoyLoading = false; },
          });
      },
      error: err => {
        console.error('Dashboard metadata load failed', err);
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

  sendMessage(): void {
    const msg = this.chatInput.trim();
    if (!msg || this.chatLoading) return;

    this.chatInput = '';
    this.chatOpen = true;
    const historyBeforeSend = [...this.chatHistory];
    this.chatHistory = [...this.chatHistory, { role: 'user', content: msg }];
    this.chatLoading = true;
    setTimeout(() => this.scrollChatToBottom(), 50);

    this.dashboardService.sendChatMessage(msg, historyBeforeSend).subscribe({
      next: res => {
        this.chatHistory = [...this.chatHistory, { role: 'assistant', content: res.response }];
        this.chatLoading = false;
        setTimeout(() => this.scrollChatToBottom(), 50);
      },
      error: () => {
        this.chatHistory = [
          ...this.chatHistory,
          { role: 'assistant', content: 'Something went wrong. Please try again.' },
        ];
        this.chatLoading = false;
      },
    });
  }

  closeChat(): void {
    this.chatOpen = false;
  }

  private scrollChatToBottom(): void {
    const el = this.chatLogRef?.nativeElement;
    if (el) el.scrollTop = el.scrollHeight;
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
        const byDate = new Map<string, number[]>();
        for (const r of stationReadings) {
          const dk = r.read_at.slice(0, 10);
          if (!byDate.has(dk)) byDate.set(dk, []);
          byDate.get(dk)!.push(r.temperature);
        }
        const data = [...byDate.entries()]
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([dk, temps]) => [
            `${dk}T12:00:00.000Z`,
            +(temps.reduce((a, b) => a + b, 0) / temps.length).toFixed(2),
          ]);

        series.push({
          name: station,
          type: 'line',
          smooth: true,
          symbol: 'none',
          color: CHART_COLORS[colorIdx++ % CHART_COLORS.length],
          data,
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
          const d = new Date(pts[0]?.axisValue ?? pts[0]?.data?.[0] ?? '').toLocaleDateString();
          return `${d}<br>` + pts.map((x: any) => `${x.marker}${x.seriesName}: ${(+x.value[1]).toFixed(1)}°F`).join('<br>');
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
      Harvest: '#C9A227',
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
        subtext: '°F  /  %',
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
          color: '#C9A227',
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
        const match = harvested.find(c => c.season_year === yr && c.crop_id === cropId);
        return match?.actual_yield ?? 0;
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
