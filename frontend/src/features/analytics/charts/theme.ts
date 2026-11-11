import type Highcharts from 'highcharts';

export const palette = ['#4E70BE', '#586AD9', '#287F61', '#6E62A8', '#1F6A6A', '#99661E', '#B6C9DE'];

export const chartColors = {
  series: '#4E70BE',
  primary: '#586AD9',
  success: '#287F61',
  pink: '#6E62A8',
  aqua: '#1F6A6A',
  grid: '#E5EAF2',
  tick: '#68778D',
  ink: '#1C273B',
  unavailable: '#E6EDF5',
} as const;

const funnelColors = ['#4E70BE', '#586AD9', '#6E62A8', '#287F61', '#1F6A6A'];

export function funnelColor(index: number, available: boolean): string {
  return available ? funnelColors[index % funnelColors.length] : chartColors.unavailable;
}

export const refiqChartBaseOptions: Highcharts.Options = {
  credits: {
    enabled: false,
  },
  exporting: {
    enabled: false,
    chartOptions: {
      credits: {
        enabled: false,
      },
    },
  },
  title: {
    text: undefined,
  },
  chart: {
    backgroundColor: 'transparent',
    style: {
      fontFamily: 'inherit',
    },
    spacing: [8, 8, 8, 8],
    animation: {
      duration: 450,
    },
  },
  colors: [...palette],
  tooltip: {
    backgroundColor: '#FFFFFF',
    borderColor: '#E5EAF2',
    borderRadius: 8,
    shadow: false,
    style: {
      color: chartColors.ink,
      fontSize: '12px',
    },
  },
  legend: {
    itemStyle: {
      color: chartColors.ink,
      fontSize: '12px',
      fontWeight: '600',
    },
    itemHoverStyle: {
      color: chartColors.series,
    },
  },
};

export function mergeRefiqOptions(
  options: Highcharts.Options,
  height: number,
  reduceMotion: boolean,
): Highcharts.Options {
  const series = {
    ...(options.plotOptions?.series || {}),
    animation: reduceMotion ? false : { duration: 450 },
  };
  return {
    ...refiqChartBaseOptions,
    ...options,
    chart: {
      ...refiqChartBaseOptions.chart,
      ...options.chart,
      backgroundColor: 'transparent',
      height,
      reflow: true,
      animation: reduceMotion ? false : { duration: 450 },
      style: {
        fontFamily: 'inherit',
        ...options.chart?.style,
      },
    },
    title: { text: undefined },
    credits: { enabled: false },
    exporting: {
      enabled: false,
      chartOptions: { credits: { enabled: false } },
    },
    plotOptions: {
      ...refiqChartBaseOptions.plotOptions,
      ...options.plotOptions,
      series,
    },
    tooltip: {
      ...refiqChartBaseOptions.tooltip,
      ...options.tooltip,
    },
  };
}
