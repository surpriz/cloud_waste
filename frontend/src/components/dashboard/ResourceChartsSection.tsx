"use client";

import { useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { ChevronDown, ChevronUp, PieChart as PieChartIcon } from "lucide-react";
import type { OrphanResource, OrphanResourceStats } from "@/types";
import {
  prepareTypeDistributionData,
  prepareRegionDistributionData,
  calculateCostByType,
  calculateConfidenceLevelDistribution,
  formatCurrency,
  formatPercentage,
  CHART_COLORS,
} from "@/lib/chartHelpers";

interface ResourceChartsSectionProps {
  resources: OrphanResource[];
  stats: OrphanResourceStats | null;
  onFilterByType?: (type: string) => void;
  onFilterByRegion?: (region: string) => void;
}

export function ResourceChartsSection({
  resources,
  stats,
  onFilterByType,
  onFilterByRegion,
}: ResourceChartsSectionProps) {
  const [isExpanded, setIsExpanded] = useState(true);

  // Prepare chart data
  const typeDistribution = prepareTypeDistributionData(stats);
  const regionDistribution = prepareRegionDistributionData(stats);
  const costByType = calculateCostByType(resources);
  const confidenceDistribution = calculateConfidenceLevelDistribution(resources);

  if (!stats || resources.length === 0) {
    return null;
  }

  return (
    <div className="rounded-lg border bg-white shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between border-b p-4">
        <div className="flex items-center gap-2">
          <PieChartIcon className="h-5 w-5 text-blue-600" />
          <h2 className="text-lg font-semibold text-gray-900">Visual Overview</h2>
          <span className="text-sm text-gray-500">
            ({resources.length} resources analyzed)
          </span>
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors"
        >
          {isExpanded ? (
            <>
              <ChevronUp className="h-4 w-4" />
              Hide Charts
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" />
              Show Charts
            </>
          )}
        </button>
      </div>

      {/* Charts Grid */}
      {isExpanded && (
        <div className="grid gap-6 p-6 md:grid-cols-2">
          {/* Resource Type Distribution - Pie Chart */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
            <h3 className="mb-4 text-center text-sm font-semibold text-gray-700">
              Distribution by Resource Type
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={typeDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) =>
                    `${name} (${(percent * 100).toFixed(0)}%)`
                  }
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {typeDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ payload }) => {
                    if (payload && payload.length > 0 && payload[0]?.payload) {
                      const data = payload[0].payload;
                      return (
                        <div className="rounded-lg border bg-white p-3 shadow-lg">
                          <p className="font-semibold text-gray-900">{data.name}</p>
                          <p className="text-sm text-gray-600">
                            Count: {data.value}
                          </p>
                          <p className="text-sm text-gray-600">
                            {formatPercentage(
                              data.value,
                              typeDistribution.reduce((sum, item) => sum + item.value, 0)
                            )}
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>

          {/* Top 10 Costs by Type - Bar Chart */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
            <h3 className="mb-4 text-center text-sm font-semibold text-gray-700">
              Top 10 Costs by Resource Type
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={costByType} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" />
                <YAxis dataKey="type" type="category" width={150} />
                <Tooltip
                  content={({ payload }) => {
                    if (payload && payload.length > 0 && payload[0]?.payload) {
                      const data = payload[0].payload;
                      return (
                        <div className="rounded-lg border bg-white p-3 shadow-lg">
                          <p className="font-semibold text-gray-900">{data.type}</p>
                          <p className="text-sm text-gray-600">
                            Monthly Cost: {formatCurrency(data.cost)}
                          </p>
                          <p className="text-sm text-gray-600">
                            Annual Cost: {formatCurrency(data.cost * 12)}
                          </p>
                          <p className="text-sm text-gray-600">
                            Count: {data.count} resources
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="cost" fill={CHART_COLORS.warning} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Region Distribution - Bar Chart */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
            <h3 className="mb-4 text-center text-sm font-semibold text-gray-700">
              Distribution by Region
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={regionDistribution}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
                <YAxis />
                <Tooltip
                  content={({ payload }) => {
                    if (payload && payload.length > 0 && payload[0]?.payload) {
                      const data = payload[0].payload;
                      return (
                        <div className="rounded-lg border bg-white p-3 shadow-lg">
                          <p className="font-semibold text-gray-900">{data.name}</p>
                          <p className="text-sm text-gray-600">
                            Count: {data.value} resources
                          </p>
                          <p className="text-sm text-gray-600">
                            {formatPercentage(
                              data.value,
                              regionDistribution.reduce((sum, item) => sum + item.value, 0)
                            )}
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="value" fill={CHART_COLORS.info} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Confidence Level Distribution - Donut Chart */}
          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
            <h3 className="mb-4 text-center text-sm font-semibold text-gray-700">
              Distribution by Confidence Level
            </h3>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={confidenceDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) =>
                    `${name} (${(percent * 100).toFixed(0)}%)`
                  }
                  outerRadius={80}
                  innerRadius={50}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {confidenceDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ payload }) => {
                    if (payload && payload.length > 0 && payload[0]?.payload) {
                      const data = payload[0].payload;
                      return (
                        <div className="rounded-lg border bg-white p-3 shadow-lg">
                          <p className="font-semibold text-gray-900">
                            {data.name} Confidence
                          </p>
                          <p className="text-sm text-gray-600">
                            Count: {data.value} resources
                          </p>
                          <p className="text-sm text-gray-600">
                            {formatPercentage(
                              data.value,
                              confidenceDistribution.reduce(
                                (sum, item) => sum + item.value,
                                0
                              )
                            )}
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Collapsed state hint */}
      {!isExpanded && (
        <div className="p-4 text-center text-sm text-gray-500">
          Click "Show Charts" to visualize resource distribution and costs
        </div>
      )}
    </div>
  );
}
