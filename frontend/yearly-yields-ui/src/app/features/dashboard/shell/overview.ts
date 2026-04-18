import { Component, ElementRef, OnInit, ViewChild, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { NgxEchartsDirective } from 'ngx-echarts';
import type { EChartsOption } from 'echarts';
import { forkJoin } from 'rxjs';

import { CropCycle, CropService } from '../../../core/services/crop.service';
import { DashboardService, ChatMessage, WeeklySummary } from '../../../core/services/dashboard.service';
import { FieldService } from '../../../core/services/field.service';
import { SensorReading } from '../../../core/services/reading.service';

const CHART_COLORS = ['#2e7d32', '#43a047', '#66bb6a', '#a5d6a7', '#1b5e20', '#81c784', '#388e3c'];

@Component({
  selector: 'app-overview',
  standalone: true,
  imports: [
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
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

  chatInput = '';
  chatOpen = false;
  chatLoading = false;
  chatHistory: ChatMessage[] = [];

  sensorTrendOptions: EChartsOption = {};
  yieldProgressOptions: EChartsOption = {};
  weeklySummaryOptions: EChartsOption = {};
  yoyYieldOptions: EChartsOption = {};

  ngOnInit(): void {
    forkJoin({
      areas: this.fieldService.list(),
      crops: this.cropService.listCrops(),
      currentCycles: this.dashboardService.getCurrentSeasonCycles(),
      readings: this.dashboardService.getRecentReadings(),
      allCycles: this.dashboardService.getAllCycles(),
      weeklySummaries: this.dashboardService.getWeeklySummaries(),
    }).subscribe({
      next: ({ areas, crops, currentCycles, readings, allCycles, weeklySummaries }) => {
        const areaMap = new Map(areas.map(a => [a.id, a.name]));
        const cropMap = new Map(crops.map(c => [c.id, c.name]));
        this.sensorTrendOptions = this.buildSensorTrendOptions(readings, areaMap);
        this.yieldProgressOptions = this.buildYieldProgressOptions(currentCycles, areaMap, cropMap);
        this.weeklySummaryOptions = this.buildWeeklySummaryOptions(weeklySummaries);
        this.yoyYieldOptions = this.buildYoYYieldOptions(allCycles, cropMap);
      },
      error: err => console.error('Dashboard load failed', err),
    });
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

  private buildSensorTrendOptions(
    readings: SensorReading[],
    areaMap: Map<string, string>,
  ): EChartsOption {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - 30);
    const recent = readings.filter(r => new Date(r.read_at) >= cutoff);

    if (!recent.length) return this.emptyChart('Sensor Readings — Last 30 Days');

    const byArea = new Map<string, SensorReading[]>();
    for (const r of recent) {
      if (!byArea.has(r.growing_area_id)) byArea.set(r.growing_area_id, []);
      byArea.get(r.growing_area_id)!.push(r);
    }

    const series: any[] = [];
    let colorIdx = 0;
    for (const [areaId, areaReadings] of byArea) {
      const sorted = [...areaReadings].sort(
        (a, b) => new Date(a.read_at).getTime() - new Date(b.read_at).getTime(),
      );
      const step = Math.max(1, Math.floor(sorted.length / 200));
      const sampled = sorted.filter((_, i) => i % step === 0);
      const name = areaMap.get(areaId) ?? areaId.slice(0, 8);
      series.push({
        name,
        type: 'line',
        smooth: true,
        symbol: 'none',
        color: CHART_COLORS[colorIdx++ % CHART_COLORS.length],
        data: sampled.map(r => [r.read_at, r.temperature]),
      });
    }

    return {
      title: { text: 'Sensor Readings — Last 30 Days', left: 16, top: 8, textStyle: { fontSize: 14 } },
      tooltip: {
        trigger: 'axis',
        formatter: (params: any) => {
          const pts = Array.isArray(params) ? params : [params];
          const d = new Date(pts[0]?.axisValue ?? '').toLocaleDateString();
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

  private buildYieldProgressOptions(
    cycles: CropCycle[],
    areaMap: Map<string, string>,
    cropMap: Map<string, string>,
  ): EChartsOption {
    const withTarget = cycles.filter(c => c.target_yield != null);
    if (!withTarget.length) return this.emptyChart('Current Season Yield Progress');

    const labels = withTarget.map(c => {
      const area = areaMap.get(c.growing_area_id) ?? 'Unknown';
      const crop = c.crop_id ? (cropMap.get(c.crop_id) ?? '') : '';
      return crop ? `${area} (${crop})` : area;
    });

    return {
      title: { text: 'Current Season Yield Progress', left: 16, top: 8, textStyle: { fontSize: 14 } },
      tooltip: {
        trigger: 'axis',
        axisPointer: { type: 'shadow' },
        formatter: (params: any) => {
          const pts = Array.isArray(params) ? params : [params];
          return pts.map((x: any) => `${x.marker}${x.seriesName}: ${x.value ?? 0}`).join('<br>');
        },
      },
      legend: { bottom: 0 },
      grid: { top: 48, bottom: 40, left: 220, right: 60 },
      xAxis: { type: 'value', name: withTarget[0]?.yield_unit ?? 'units' },
      yAxis: { type: 'category', data: labels, axisLabel: { width: 200, overflow: 'truncate' as const } },
      series: [
        {
          name: 'Target',
          type: 'bar',
          barGap: '-100%',
          itemStyle: { color: 'rgba(46,125,50,0.15)', borderColor: '#2e7d32', borderWidth: 1 },
          data: withTarget.map(c => c.target_yield),
        },
        {
          name: 'Actual',
          type: 'bar',
          itemStyle: { color: '#43a047' },
          data: withTarget.map(c => c.actual_yield ?? 0),
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
      title: { text: 'Weekly Sensor Averages', left: 16, top: 8, textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      legend: { bottom: 0 },
      grid: { top: 48, bottom: 40, left: 60, right: 60 },
      xAxis: { type: 'category', data: labels, axisLabel: { rotate: 45, fontSize: 10 } },
      yAxis: [
        { type: 'value', name: '°F', nameLocation: 'end', axisLabel: { formatter: '{value}°' } },
        { type: 'value', name: '%', nameLocation: 'end', axisLabel: { formatter: '{value}%' } },
      ],
      series: [
        {
          name: 'Avg Temp',
          type: 'line',
          areaStyle: { opacity: 0.2 },
          smooth: true,
          symbol: 'none',
          color: '#2e7d32',
          yAxisIndex: 0,
          data: avgTemp,
        },
        {
          name: 'Avg Humidity',
          type: 'line',
          areaStyle: { opacity: 0.15 },
          smooth: true,
          symbol: 'none',
          color: '#43a047',
          yAxisIndex: 1,
          data: avgHumidity,
        },
      ],
    };
  }

  private buildYoYYieldOptions(
    cycles: CropCycle[],
    cropMap: Map<string, string>,
  ): EChartsOption {
    const harvested = cycles.filter(c => c.status === 'harvested' && c.actual_yield != null);
    if (!harvested.length) return this.emptyChart('Year-Over-Year Actual Yields');

    const years = [...new Set(harvested.map(c => c.season_year))].sort();
    const cropIds = [...new Set(harvested.map(c => c.crop_id).filter(Boolean) as string[])];

    const series = cropIds.map((cropId, i) => ({
      name: cropMap.get(cropId) ?? cropId.slice(0, 8),
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
