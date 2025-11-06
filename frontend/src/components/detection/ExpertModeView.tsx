"use client";

import { Save, RotateCcw } from "lucide-react";

interface DetectionRule {
  resource_type: string;
  current_rules: {
    enabled: boolean;
    min_age_days?: number;
    min_stopped_days?: number;
    confidence_threshold_days?: number;
    confidence_critical_days?: number;
    confidence_high_days?: number;
    confidence_medium_days?: number;
    min_idle_days?: number;
    [key: string]: any;
  };
  default_rules: {
    enabled: boolean;
    min_age_days?: number;
    min_stopped_days?: number;
    confidence_threshold_days?: number;
    confidence_critical_days?: number;
    confidence_high_days?: number;
    confidence_medium_days?: number;
    min_idle_days?: number;
    description?: string;
    [key: string]: any;
  };
  description: string;
}

interface ExpertModeViewProps {
  detectionRules: DetectionRule[];
  selectedProvider: "aws" | "azure" | "gcp" | "microsoft365" | "all";
  selectedCategory: string;
  searchQuery: string;
  getResourceIcon: (resourceType: string) => any;
  getResourceLabel: (resourceType: string) => string;
  getResourceProvider: (resourceType: string) => string;
  getResourceCategory: (resourceType: string, provider: "aws" | "azure" | "gcp" | "microsoft365") => string;
  updateRule: (resourceType: string) => Promise<void>;
  resetRule: (resourceType: string) => Promise<void>;
  handleRuleChange: (resourceType: string, field: string, value: any) => void;
}

export function ExpertModeView({
  detectionRules,
  selectedProvider,
  selectedCategory,
  searchQuery,
  getResourceIcon,
  getResourceLabel,
  getResourceProvider,
  getResourceCategory,
  updateRule,
  resetRule,
  handleRuleChange,
}: ExpertModeViewProps) {
  // Apply multi-criteria filtering
  const filteredRules = detectionRules.filter((rule) => {
    // Filter 1: Provider
    if (selectedProvider !== "all") {
      const provider = getResourceProvider(rule.resource_type);
      if (provider !== selectedProvider) return false;
    }

    // Filter 2: Category
    if (selectedCategory !== "all" && selectedProvider !== "all") {
      const category = getResourceCategory(rule.resource_type, selectedProvider as "aws" | "azure" | "gcp" | "microsoft365");
      if (category !== selectedCategory) return false;
    }

    // Filter 3: Search query
    if (searchQuery) {
      const label = getResourceLabel(rule.resource_type).toLowerCase();
      const resourceType = rule.resource_type.toLowerCase();
      const query = searchQuery.toLowerCase();
      if (!label.includes(query) && !resourceType.includes(query)) return false;
    }

    return true;
  });

  return (
    <>
      {/* Resource Counter */}
      {(selectedProvider !== "all" || selectedCategory !== "all" || searchQuery) && (
        <div className="rounded-lg bg-blue-50 border-2 border-blue-200 p-4 mb-4">
          <p className="text-sm font-semibold text-blue-900">
            📊 Showing <span className="text-blue-600">{filteredRules.length}</span> resource{filteredRules.length !== 1 ? "s" : ""}
            {detectionRules.length !== filteredRules.length && (
              <span className="text-gray-600"> (filtered from {detectionRules.length} total)</span>
            )}
          </p>
        </div>
      )}

      {filteredRules.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <p className="text-lg font-semibold mb-2">No resources found</p>
          <p className="text-sm">Try adjusting your filters or search query</p>
        </div>
      ) : (
        filteredRules.map((rule) => {
          const Icon = getResourceIcon(rule.resource_type);
          const label = getResourceLabel(rule.resource_type);
          const isCustomized = JSON.stringify(rule.current_rules) !== JSON.stringify(rule.default_rules);
          const provider = getResourceProvider(rule.resource_type);

          return (
            <div
              key={rule.resource_type}
              className={`rounded-2xl bg-white p-4 md:p-6 shadow-lg border-2 transition-all mb-4 ${
                isCustomized ? "border-orange-300 bg-orange-50/30" : "border-gray-200"
              }`}
            >
              <div className="flex flex-col lg:flex-row items-start justify-between gap-4 mb-6">
                <div className="flex items-start gap-3 md:gap-4 flex-1">
                  <div className="rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 p-2 md:p-3 flex-shrink-0">
                    <Icon className="h-5 w-5 md:h-6 md:w-6 text-white" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-lg md:text-xl font-bold text-gray-900 flex flex-wrap items-center gap-2">
                      <span>{label}</span>
                      <span className={`text-xs px-2 py-1 rounded-full font-semibold ${
                        provider === "gcp"
                          ? "bg-red-100 text-red-800"
                          : provider === "azure"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-orange-100 text-orange-800"
                      }`}>
                        {provider === "gcp" ? "🔴 GCP" : provider === "azure" ? "🔵 AZURE" : "🟠 AWS"}
                      </span>
                      {isCustomized && (
                        <span className="text-xs bg-purple-200 text-purple-800 px-2 py-1 rounded-full font-semibold">
                          CUSTOM
                        </span>
                      )}
                    </h3>
                    <p className="text-sm text-gray-600 mt-1">{rule.description}</p>
                  </div>
                </div>

                <div className="flex w-full lg:w-auto gap-2">
                  <button
                    onClick={() => updateRule(rule.resource_type)}
                    className="flex-1 lg:flex-none flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
                  >
                    <Save className="h-4 w-4" />
                    <span>Save</span>
                  </button>
                  {isCustomized && (
                    <button
                      onClick={() => resetRule(rule.resource_type)}
                      className="flex items-center justify-center gap-2 rounded-lg border-2 border-gray-300 px-3 md:px-4 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-100 transition-colors"
                      title="Reset to defaults"
                    >
                      <RotateCcw className="h-4 w-4" />
                      <span className="sr-only">Reset</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Enable/Disable Toggle */}
              <div className="mb-6 flex items-center justify-between rounded-xl bg-gray-50 p-4">
                <div>
                  <h4 className="font-semibold text-gray-900">Detection Enabled</h4>
                  <p className="text-sm text-gray-600">Enable or disable detection for this resource type</p>
                </div>
                <label className="relative inline-flex cursor-pointer items-center">
                  <input
                    type="checkbox"
                    className="peer sr-only"
                    checked={rule.current_rules.enabled}
                    onChange={(e) =>
                      handleRuleChange(rule.resource_type, "enabled", e.target.checked)
                    }
                  />
                  <div className="peer h-6 w-11 rounded-full bg-gray-300 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:bg-green-600 peer-checked:after:translate-x-full"></div>
                </label>
              </div>

              {/* Age Threshold */}
              {(rule.current_rules.min_age_days !== undefined || rule.current_rules.min_stopped_days !== undefined) && (
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-gray-900">
                      {rule.resource_type.startsWith('ec2_instance') ? 'Minimum Age (Stopped Instances)' : 'Minimum Age'}: {rule.current_rules.min_age_days ?? rule.current_rules.min_stopped_days} days
                    </h4>
                    <span className="text-sm text-gray-500">
                      Default: {rule.default_rules.min_age_days ?? rule.default_rules.min_stopped_days} days
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="90"
                    step="1"
                    value={rule.current_rules.min_age_days ?? rule.current_rules.min_stopped_days ?? 0}
                    onChange={(e) =>
                      handleRuleChange(
                        rule.resource_type,
                        rule.current_rules.min_age_days !== undefined ? "min_age_days" : "min_stopped_days",
                        parseInt(e.target.value)
                      )
                    }
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>0 days (detect immediately)</span>
                    <span>90 days</span>
                  </div>
                </div>
              )}

              {/* Confidence Level Thresholds */}
              {(rule.current_rules.confidence_critical_days !== undefined ||
                rule.current_rules.confidence_high_days !== undefined ||
                rule.current_rules.confidence_medium_days !== undefined) && (
                <div className="mb-4">
                  <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                    🎯 Confidence Level Thresholds
                  </h4>
                  <div className="space-y-4 p-4 bg-gradient-to-r from-blue-50 to-purple-50 border-2 border-blue-200 rounded-lg">
                    {/* Critical Threshold */}
                    {rule.current_rules.confidence_critical_days !== undefined && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="text-sm font-medium text-gray-900 flex items-center gap-2">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border bg-red-100 text-red-800 border-red-300">
                              🔴 Critical
                            </span>
                            After {rule.current_rules.confidence_critical_days ?? rule.default_rules.confidence_critical_days ?? 90} days
                          </label>
                          <span className="text-xs text-gray-500">
                            Default: {rule.default_rules.confidence_critical_days ?? 90} days
                          </span>
                        </div>
                        <input
                          type="range"
                          min="30"
                          max="365"
                          step="1"
                          value={rule.current_rules.confidence_critical_days ?? rule.default_rules.confidence_critical_days ?? 90}
                          onChange={(e) =>
                            handleRuleChange(
                              rule.resource_type,
                              "confidence_critical_days",
                              parseInt(e.target.value)
                            )
                          }
                          className="w-full h-2 bg-gradient-to-r from-orange-200 to-red-300 rounded-lg appearance-none cursor-pointer"
                        />
                      </div>
                    )}

                    {/* High Threshold */}
                    {rule.current_rules.confidence_high_days !== undefined && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="text-sm font-medium text-gray-900 flex items-center gap-2">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border bg-orange-100 text-orange-800 border-orange-300">
                              🟠 High
                            </span>
                            After {rule.current_rules.confidence_high_days ?? rule.default_rules.confidence_high_days ?? 30} days
                          </label>
                          <span className="text-xs text-gray-500">
                            Default: {rule.default_rules.confidence_high_days ?? 30} days
                          </span>
                        </div>
                        <input
                          type="range"
                          min="7"
                          max="180"
                          step="1"
                          value={rule.current_rules.confidence_high_days ?? rule.default_rules.confidence_high_days ?? 30}
                          onChange={(e) =>
                            handleRuleChange(
                              rule.resource_type,
                              "confidence_high_days",
                              parseInt(e.target.value)
                            )
                          }
                          className="w-full h-2 bg-gradient-to-r from-yellow-200 to-orange-300 rounded-lg appearance-none cursor-pointer"
                        />
                      </div>
                    )}

                    {/* Medium Threshold */}
                    {rule.current_rules.confidence_medium_days !== undefined && (
                      <div>
                        <div className="flex items-center justify-between mb-2">
                          <label className="text-sm font-medium text-gray-900 flex items-center gap-2">
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border bg-yellow-100 text-yellow-800 border-yellow-300">
                              🟡 Medium
                            </span>
                            After {rule.current_rules.confidence_medium_days ?? rule.default_rules.confidence_medium_days ?? 7} days
                          </label>
                          <span className="text-xs text-gray-500">
                            Default: {rule.default_rules.confidence_medium_days ?? 7} days
                          </span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="60"
                          step="1"
                          value={rule.current_rules.confidence_medium_days ?? rule.default_rules.confidence_medium_days ?? 7}
                          onChange={(e) =>
                            handleRuleChange(
                              rule.resource_type,
                              "confidence_medium_days",
                              parseInt(e.target.value)
                            )
                          }
                          className="w-full h-2 bg-gradient-to-r from-green-200 to-yellow-300 rounded-lg appearance-none cursor-pointer"
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Idle Running Instances Threshold (EC2 only) */}
              {rule.resource_type.startsWith('ec2_instance') && rule.current_rules.min_idle_days !== undefined && (
                <div className="mb-4">
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-gray-900">
                      Minimum Age (Idle Running Instances): {rule.current_rules.min_idle_days} days
                    </h4>
                    <span className="text-sm text-gray-500">
                      Default: {rule.default_rules.min_idle_days} days
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="30"
                    step="1"
                    value={rule.current_rules.min_idle_days || 0}
                    onChange={(e) =>
                      handleRuleChange(
                        rule.resource_type,
                        "min_idle_days",
                        parseInt(e.target.value)
                      )
                    }
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>0 days (detect immediately)</span>
                    <span>30 days</span>
                  </div>
                </div>
              )}
            </div>
          );
        })
      )}
    </>
  );
}
