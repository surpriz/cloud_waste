"use client";

import { useState, useEffect } from "react";
import { ChevronDown, ChevronRight, Save, RotateCcw, HardDrive, Globe, Camera, Server } from "lucide-react";

interface GroupedFamily {
  resource_family: string;
  label: string;
  scenario_count: number;
  scenarios: Array<{
    resource_type: string;
    description: string;
    enabled: boolean;
    is_customized: boolean;
  }>;
  common_params: {
    enabled?: boolean;
    min_age_days?: number;
    confidence_threshold_days?: number;
    min_stopped_days?: number;
  };
  enabled: boolean;
  is_customized: boolean;
}

interface BasicModeViewProps {
  selectedProvider: "aws" | "azure" | "gcp" | "microsoft365" | "all";
  searchQuery: string;
  showSuccess: (message: string) => void;
  showError: (message: string) => void;
}

const FAMILY_ICONS: { [key: string]: any } = {
  ebs_volume: HardDrive,
  elastic_ip: Globe,
  ebs_snapshot: Camera,
  ec2_instance: Server,
  managed_disk: HardDrive,
  public_ip: Globe,
  disk_snapshot: Camera,
  virtual_machine: Server,
  nat_gateway: Globe,
};

export function BasicModeView({ selectedProvider, searchQuery, showSuccess, showError }: BasicModeViewProps) {
  const [families, setFamilies] = useState<GroupedFamily[]>([]);
  const [expandedFamilies, setExpandedFamilies] = useState<Set<string>>(new Set());
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    fetchGroupedRules();
  }, []);

  const fetchGroupedRules = async () => {
    setIsLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_URL}/api/v1/detection-rules/grouped`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setFamilies(data);
      }
    } catch (error) {
      console.error("Failed to fetch grouped rules:", error);
      showError("Failed to load detection rules");
    } finally {
      setIsLoading(false);
    }
  };

  const toggleFamily = (familyName: string) => {
    setExpandedFamilies((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(familyName)) {
        newSet.delete(familyName);
      } else {
        newSet.add(familyName);
      }
      return newSet;
    });
  };

  const updateFamilyRules = (familyName: string, field: string, value: any) => {
    setFamilies((prevFamilies) =>
      prevFamilies.map((family) =>
        family.resource_family === familyName
          ? {
              ...family,
              common_params: {
                ...family.common_params,
                [field]: value,
              },
            }
          : family
      )
    );
  };

  const saveFamilyRules = async (family: GroupedFamily) => {
    try {
      const token = localStorage.getItem("access_token");
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(
        `${API_URL}/api/v1/detection-rules/grouped/bulk-update?family=${family.resource_family}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(family.common_params),
        }
      );

      if (response.ok) {
        await fetchGroupedRules();
        showSuccess(`Saved rules for ${family.label}`);
      } else {
        showError("Failed to save rules");
      }
    } catch (error) {
      console.error("Failed to save family rules:", error);
      showError("Failed to save rules");
    }
  };

  const getProviderFromFamily = (familyName: string): string => {
    // Azure families
    if (
      familyName.startsWith("managed_disk") ||
      familyName.startsWith("public_ip") ||
      familyName.startsWith("disk_snapshot") ||
      familyName.startsWith("virtual_machine") ||
      familyName.startsWith("nat_gateway") ||
      familyName.startsWith("azure_") ||
      familyName.startsWith("load_balancer") ||
      familyName.startsWith("application_gateway") ||
      familyName.startsWith("sql_database") ||
      familyName.startsWith("cosmosdb") ||
      familyName.startsWith("postgres_mysql") ||
      familyName.startsWith("synapse") ||
      familyName.startsWith("redis") ||
      familyName.startsWith("storage") ||
      familyName.startsWith("functions") ||
      familyName.startsWith("container_app") ||
      familyName.startsWith("avd_") ||
      familyName.startsWith("hdinsight") ||
      familyName.startsWith("ml_compute") ||
      familyName.startsWith("app_service") ||
      familyName.startsWith("expressroute") ||
      familyName.startsWith("vpn_gateway") ||
      familyName.startsWith("network_interface")
    ) {
      return "azure";
    }

    // GCP families
    if (
      familyName.startsWith("compute_instance") ||
      familyName.startsWith("persistent_disk") ||
      familyName.startsWith("cloud_sql") ||
      familyName.startsWith("gke_") ||
      familyName.startsWith("dataflow") ||
      familyName.startsWith("dataproc") ||
      familyName.startsWith("bigquery") ||
      familyName.startsWith("memorystore") ||
      familyName.startsWith("gcp_cloud") ||
      familyName.startsWith("vertex_ai") ||
      familyName.startsWith("notebook_instance")
    ) {
      return "gcp";
    }

    // AWS families (default)
    return "aws";
  };

  // Apply filters
  const filteredFamilies = families.filter((family) => {
    // Provider filter
    if (selectedProvider !== "all") {
      const provider = getProviderFromFamily(family.resource_family);
      if (provider !== selectedProvider) return false;
    }

    // Search filter
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      const matchesLabel = family.label.toLowerCase().includes(query);
      const matchesScenario = family.scenarios.some(
        (scenario) =>
          scenario.resource_type.toLowerCase().includes(query) ||
          scenario.description.toLowerCase().includes(query)
      );
      if (!matchesLabel && !matchesScenario) return false;
    }

    return true;
  });

  if (isLoading) {
    return <div className="text-center py-12 text-gray-600">Loading detection rules...</div>;
  }

  return (
    <div className="space-y-4">
      {/* Family Counter */}
      <div className="rounded-lg bg-blue-50 border-2 border-blue-200 p-4">
        <p className="text-sm font-semibold text-blue-900">
          📊 Showing <span className="text-blue-600">{filteredFamilies.length}</span> resource{" "}
          {filteredFamilies.length !== 1 ? "families" : "family"}
          {families.length !== filteredFamilies.length && (
            <span className="text-gray-600"> (filtered from {families.length} total)</span>
          )}
        </p>
      </div>

      {filteredFamilies.length === 0 ? (
        <div className="text-center py-12 text-gray-600">
          <p className="text-lg font-semibold mb-2">No resource families found</p>
          <p className="text-sm">Try adjusting your filters or search query</p>
        </div>
      ) : (
        filteredFamilies.map((family) => {
          const Icon = FAMILY_ICONS[family.resource_family] || HardDrive;
          const isExpanded = expandedFamilies.has(family.resource_family);
          const provider = getProviderFromFamily(family.resource_family);

          return (
            <div
              key={family.resource_family}
              className={`rounded-2xl bg-white p-4 md:p-6 shadow-lg border-2 transition-all ${
                family.is_customized ? "border-orange-300 bg-orange-50/30" : "border-gray-200"
              }`}
            >
              {/* Family Header */}
              <div className="flex items-start justify-between mb-4">
                <div
                  className="flex items-center gap-3 flex-1 cursor-pointer"
                  onClick={() => toggleFamily(family.resource_family)}
                >
                  <div className="p-3 bg-blue-100 rounded-xl">
                    <Icon className="w-6 h-6 text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-lg font-bold text-gray-900">{family.label}</h3>
                      <span
                        className={`text-xs px-2 py-1 rounded-full font-semibold ${
                          provider === "gcp"
                            ? "bg-red-100 text-red-800"
                            : provider === "azure"
                            ? "bg-blue-100 text-blue-800"
                            : "bg-orange-100 text-orange-800"
                        }`}
                      >
                        {provider === "gcp" ? "🔴 GCP" : provider === "azure" ? "🔵 AZURE" : "🟠 AWS"}
                      </span>
                      {family.is_customized && (
                        <span className="px-2 py-0.5 bg-purple-200 text-purple-800 text-xs font-semibold rounded-full">
                          CUSTOMIZED
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-600 mt-1">
                      {family.scenario_count} scenario{family.scenario_count !== 1 ? "s" : ""} •{" "}
                      {family.scenarios.filter((s) => s.enabled).length} enabled
                    </p>
                  </div>
                  <button className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                    {isExpanded ? (
                      <ChevronDown className="w-5 h-5 text-gray-500" />
                    ) : (
                      <ChevronRight className="w-5 h-5 text-gray-500" />
                    )}
                  </button>
                </div>
              </div>

              {/* Common Parameters */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="flex items-center gap-2 text-sm font-medium text-gray-700">
                    <input
                      type="checkbox"
                      checked={family.common_params.enabled ?? true}
                      onChange={(e) =>
                        updateFamilyRules(family.resource_family, "enabled", e.target.checked)
                      }
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                    Detection Enabled
                  </label>
                </div>
                {family.common_params.min_age_days !== undefined && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Minimum Age (days)
                    </label>
                    <input
                      type="number"
                      value={family.common_params.min_age_days}
                      onChange={(e) =>
                        updateFamilyRules(family.resource_family, "min_age_days", parseInt(e.target.value))
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      min="0"
                    />
                  </div>
                )}
                {family.common_params.confidence_threshold_days !== undefined && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Confidence Threshold (days)
                    </label>
                    <input
                      type="number"
                      value={family.common_params.confidence_threshold_days}
                      onChange={(e) =>
                        updateFamilyRules(
                          family.resource_family,
                          "confidence_threshold_days",
                          parseInt(e.target.value)
                        )
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      min="0"
                    />
                  </div>
                )}
                {family.common_params.min_stopped_days !== undefined && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Minimum Stopped Days
                    </label>
                    <input
                      type="number"
                      value={family.common_params.min_stopped_days}
                      onChange={(e) =>
                        updateFamilyRules(
                          family.resource_family,
                          "min_stopped_days",
                          parseInt(e.target.value)
                        )
                      }
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      min="0"
                    />
                  </div>
                )}
              </div>

              {/* Expanded Scenarios */}
              {isExpanded && (
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <h4 className="text-sm font-semibold text-gray-700 mb-3">Individual Scenarios:</h4>
                  <div className="space-y-2">
                    {family.scenarios.map((scenario) => (
                      <div
                        key={scenario.resource_type}
                        className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
                      >
                        <div className="flex-1">
                          <p className="text-sm font-medium text-gray-900">{scenario.resource_type}</p>
                          <p className="text-xs text-gray-600 mt-1">{scenario.description}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          {scenario.is_customized && (
                            <span className="px-2 py-0.5 bg-orange-100 text-orange-700 text-xs font-semibold rounded-full">
                              CUSTOM
                            </span>
                          )}
                          <span
                            className={`px-2 py-0.5 text-xs font-semibold rounded-full ${
                              scenario.enabled
                                ? "bg-green-100 text-green-700"
                                : "bg-gray-100 text-gray-700"
                            }`}
                          >
                            {scenario.enabled ? "Enabled" : "Disabled"}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-3 mt-4">
                <button
                  onClick={() => saveFamilyRules(family)}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
                >
                  <Save className="w-4 h-4" />
                  Save Changes
                </button>
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}
