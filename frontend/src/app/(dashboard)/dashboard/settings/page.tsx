"use client";

import { useEffect, useState } from "react";
import { User, Bell, Shield, Trash2, Save, Key, Sliders, RotateCcw, HardDrive, Globe, Camera, Server, Activity, Zap, Database, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useNotifications } from "@/hooks/useNotifications";
import { Toast } from "@/components/ui/Toast";
import { NotificationHistory } from "@/components/ui/NotificationHistory";

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
    description?: string;
    [key: string]: any;
  };
  description: string;
}

// AWS Resources
const AWS_RESOURCE_ICONS: { [key: string]: any } = {
  ebs_volume: HardDrive,
  elastic_ip: Globe,
  ebs_snapshot: Camera,
  ec2_instance: Server,
  load_balancer: Zap,
  rds_instance: Database,
};

const AWS_RESOURCE_LABELS: { [key: string]: string } = {
  ebs_volume: "EBS Volumes",
  elastic_ip: "Elastic IPs",
  ebs_snapshot: "EBS Snapshots",
  ec2_instance: "EC2 Instances (Stopped)",
  load_balancer: "Load Balancers",
  rds_instance: "RDS Instances",
};

// Azure Resources
const AZURE_RESOURCE_ICONS: { [key: string]: any } = {
  managed_disk_unattached: HardDrive,
  public_ip_unassociated: Globe,
  disk_snapshot_orphaned: Camera,
  virtual_machine_deallocated: Server,
  // Phase 1 - Advanced waste scenarios
  managed_disk_on_stopped_vm: HardDrive,
  public_ip_on_stopped_resource: Globe,
  public_ip_dynamic_unassociated: Globe,
  public_ip_unnecessary_standard_sku: Globe,
  public_ip_unnecessary_zone_redundancy: Globe,
  public_ip_ddos_protection_unused: Globe,
  public_ip_on_nic_without_vm: Globe,
  public_ip_reserved_but_unused: Globe,
  disk_snapshot_redundant: Camera,
  disk_snapshot_very_old: Camera,
  disk_snapshot_premium_source: Camera,
  disk_snapshot_large_unused: Camera,
  disk_snapshot_full_instead_incremental: Camera,
  disk_snapshot_excessive_retention: Camera,
  disk_snapshot_manual_without_policy: Camera,
  disk_snapshot_never_restored: Camera,
  disk_snapshot_frequent_creation: Camera,
  managed_disk_unnecessary_zrs: HardDrive,
  managed_disk_unnecessary_cmk: HardDrive,
  // Phase 2 - Azure Monitor Metrics-based scenarios
  managed_disk_idle: HardDrive,
  managed_disk_unused_bursting: Zap,
  managed_disk_overprovisioned: Database,
  managed_disk_underutilized_hdd: HardDrive,
  public_ip_no_traffic: Globe,
  public_ip_very_low_traffic: Globe,
  // VM Phase A - Virtual Machine waste scenarios
  virtual_machine_stopped_not_deallocated: Server,
  virtual_machine_never_started: Server,
  virtual_machine_oversized_premium: Server,
  virtual_machine_untagged_orphan: Server,
  virtual_machine_idle: Server,
  virtual_machine_old_generation: Server,
  virtual_machine_spot_convertible: Server,
  virtual_machine_underutilized: Server,
  virtual_machine_memory_overprovisioned: Server,
  // AKS - Azure Kubernetes Service
  azure_aks_cluster: Server,
  // NAT Gateway - Azure NAT Gateway waste scenarios (10 types)
  nat_gateway_no_subnet: Activity,
  nat_gateway_never_used: Activity,
  nat_gateway_no_public_ip: Activity,
  nat_gateway_single_vm: Activity,
  nat_gateway_redundant: Activity,
  nat_gateway_dev_test_always_on: Activity,
  nat_gateway_unnecessary_zones: Activity,
  nat_gateway_no_traffic: Activity,
  nat_gateway_very_low_traffic: Activity,
  nat_gateway_private_link_alternative: Activity,
};

const AZURE_RESOURCE_LABELS: { [key: string]: string } = {
  managed_disk_unattached: "Managed Disks (Unattached)",
  public_ip_unassociated: "Public IP Addresses (Unassociated)",
  disk_snapshot_orphaned: "Disk Snapshots (Orphaned)",
  virtual_machine_deallocated: "Virtual Machines (Deallocated)",
  // Phase 1 - Advanced waste scenarios
  managed_disk_on_stopped_vm: "Managed Disks (On Stopped VMs)",
  public_ip_on_stopped_resource: "Public IPs (On Stopped Resources)",
  public_ip_dynamic_unassociated: "Public IPs (Dynamic, Stuck in Provisioned State)",
  public_ip_unnecessary_standard_sku: "Public IPs (Standard SKU in Dev/Test)",
  public_ip_unnecessary_zone_redundancy: "Public IPs (Unnecessary Zone Redundancy)",
  public_ip_ddos_protection_unused: "Public IPs (DDoS Protection Unused) 💰",
  public_ip_on_nic_without_vm: "Public IPs (On NICs without VMs)",
  public_ip_reserved_but_unused: "Public IPs (Reserved but No IP Assigned)",
  disk_snapshot_redundant: "Disk Snapshots (Redundant - >3 per disk)",
  disk_snapshot_very_old: "Disk Snapshots (Very Old >1 year)",
  disk_snapshot_premium_source: "Disk Snapshots (Large Premium Source >1TB)",
  disk_snapshot_large_unused: "Disk Snapshots (Large Unused >1TB) 💰",
  disk_snapshot_full_instead_incremental: "Disk Snapshots (Full vs Incremental) 💰💰💰",
  disk_snapshot_excessive_retention: "Disk Snapshots (Excessive Retention >50) 💰💰",
  disk_snapshot_manual_without_policy: "Disk Snapshots (Manual without Policy)",
  disk_snapshot_never_restored: "Disk Snapshots (Never Restored)",
  disk_snapshot_frequent_creation: "Disk Snapshots (Too Frequent - Daily vs Weekly) 💰💰",
  managed_disk_unnecessary_zrs: "Managed Disks (Unnecessary ZRS in Dev/Test)",
  managed_disk_unnecessary_cmk: "Managed Disks (Unnecessary CMK Encryption)",
  // Phase 2 - Azure Monitor Metrics-based scenarios
  managed_disk_idle: "Managed Disks (Idle - Zero I/O) 📊",
  managed_disk_unused_bursting: "Managed Disks (Unused Bursting) 📊",
  managed_disk_overprovisioned: "Managed Disks (Over-Provisioned Performance) 📊",
  managed_disk_underutilized_hdd: "Managed Disks (Under-Utilized HDD) 📊",
  public_ip_no_traffic: "Public IPs (Zero Network Traffic) 📊",
  public_ip_very_low_traffic: "Public IPs (Very Low Traffic <1GB/month) 📊",
  // VM Phase A - Virtual Machine waste scenarios
  virtual_machine_stopped_not_deallocated: "Virtual Machines (Stopped, NOT Deallocated) ⚠️",
  virtual_machine_never_started: "Virtual Machines (Never Started)",
  virtual_machine_oversized_premium: "Virtual Machines (Oversized + Premium Disks)",
  virtual_machine_untagged_orphan: "Virtual Machines (Untagged Orphans)",
  virtual_machine_idle: "Virtual Machines (Idle - Running but Unused) 📊",
  virtual_machine_old_generation: "Virtual Machines (Old Generation SKUs - v1/v2/v3)",
  virtual_machine_spot_convertible: "Virtual Machines (Spot-Eligible Workloads) 💰",
  virtual_machine_underutilized: "Virtual Machines (Underutilized - Rightsizing) 📊",
  virtual_machine_memory_overprovisioned: "Virtual Machines (Memory Over-Provisioned) 📊",
  // AKS - Azure Kubernetes Service
  azure_aks_cluster: "AKS Clusters (Azure Kubernetes Service)",
  // NAT Gateway - Azure NAT Gateway waste scenarios (10 types)
  nat_gateway_no_subnet: "NAT Gateways (No Subnets Attached) 💰",
  nat_gateway_never_used: "NAT Gateways (Never Used - No VMs) 💰",
  nat_gateway_no_public_ip: "NAT Gateways (No Public IP) 💰",
  nat_gateway_single_vm: "NAT Gateways (Single VM - Use Public IP Instead) 💰",
  nat_gateway_redundant: "NAT Gateways (Redundant in Same VNet) 💰",
  nat_gateway_dev_test_always_on: "NAT Gateways (Dev/Test Always On - Use Scheduling) 💰",
  nat_gateway_unnecessary_zones: "NAT Gateways (Multi-Zone Unnecessary)",
  nat_gateway_no_traffic: "NAT Gateways (Zero Traffic - Azure Monitor) 📊💰",
  nat_gateway_very_low_traffic: "NAT Gateways (Very Low Traffic <10GB/month) 📊💰",
  nat_gateway_private_link_alternative: "NAT Gateways (Private Link/Service Endpoints Better) 💰",
};

// Helper function to get provider from resource type
const getResourceProvider = (resourceType: string): "aws" | "azure" => {
  if (resourceType in AZURE_RESOURCE_ICONS) {
    return "azure";
  }
  return "aws";
};

// Helper function to get icon for resource type
const getResourceIcon = (resourceType: string) => {
  const provider = getResourceProvider(resourceType);
  if (provider === "azure") {
    return AZURE_RESOURCE_ICONS[resourceType] || HardDrive;
  }
  return AWS_RESOURCE_ICONS[resourceType] || HardDrive;
};

// Helper function to get label for resource type
const getResourceLabel = (resourceType: string): string => {
  const provider = getResourceProvider(resourceType);
  if (provider === "azure") {
    return AZURE_RESOURCE_LABELS[resourceType] || resourceType;
  }
  return AWS_RESOURCE_LABELS[resourceType] || resourceType;
};

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"profile" | "notifications" | "security" | "detection">("detection");
  const [detectionRules, setDetectionRules] = useState<DetectionRule[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<"aws" | "azure" | "all">("all");

  // Use advanced notification system
  const { currentNotification, history, showSuccess, showError, dismiss, clearHistory } = useNotifications();

  useEffect(() => {
    if (activeTab === "detection") {
      fetchDetectionRules();
    }
  }, [activeTab]);

  const fetchDetectionRules = async () => {
    setIsLoading(true);
    try {
      const token = localStorage.getItem("access_token");
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_URL}/api/v1/detection-rules/`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setDetectionRules(data);
      }
    } catch (error) {
      console.error("Failed to fetch detection rules:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const updateRule = async (resourceType: string) => {
    try {
      // Find the current rule from state to get the latest values
      const currentRule = detectionRules.find(r => r.resource_type === resourceType);
      if (!currentRule) {
        console.error("Rule not found:", resourceType);
        return;
      }

      console.log("🔍 DEBUG - Saving rule for:", resourceType);
      console.log("🔍 DEBUG - Current rules:", currentRule.current_rules);

      const token = localStorage.getItem("access_token");
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_URL}/api/v1/detection-rules/${resourceType}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ rules: currentRule.current_rules }),
      });

      console.log("🔍 DEBUG - Response status:", response.status);
      console.log("🔍 DEBUG - Response OK:", response.ok);

      if (response.ok) {
        await fetchDetectionRules();
        showSuccess("Rules saved successfully!");
      }
    } catch (error) {
      console.error("Failed to update rule:", error);
      showError("Failed to save rules");
    }
  };

  const resetRule = async (resourceType: string) => {
    if (!confirm("Reset this rule to default values?")) return;

    try {
      const token = localStorage.getItem("access_token");
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_URL}/api/v1/detection-rules/${resourceType}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        await fetchDetectionRules();
        showSuccess("Rule reset to defaults!");
      }
    } catch (error) {
      console.error("Failed to reset rule:", error);
    }
  };

  const resetAllRules = async () => {
    if (!confirm("⚠️ Reset ALL detection rules to default values?\n\nThis will delete all your custom settings for all 20+ resource types.")) return;

    try {
      const token = localStorage.getItem("access_token");
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const response = await fetch(`${API_URL}/api/v1/detection-rules/`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (response.ok) {
        await fetchDetectionRules();
        showSuccess("All rules reset to defaults!");
      }
    } catch (error) {
      console.error("Failed to reset all rules:", error);
      showError("Failed to reset all rules");
    }
  };

  const handleRuleChange = (resourceType: string, field: string, value: any) => {
    setDetectionRules((prev) =>
      prev.map((rule) =>
        rule.resource_type === resourceType
          ? {
              ...rule,
              current_rules: {
                ...rule.current_rules,
                [field]: value,
              },
            }
          : rule
      )
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 p-4 md:p-8">
      <div className="mx-auto max-w-6xl">
        {/* Back to Dashboard Button */}
        <Link
          href="/dashboard"
          className="mb-4 md:mb-6 inline-flex items-center gap-2 rounded-lg bg-white px-3 md:px-4 py-2 text-sm font-medium text-gray-700 shadow-sm hover:bg-gray-50 transition-colors border border-gray-200"
        >
          <ArrowLeft className="h-4 w-4" />
          <span className="hidden sm:inline">Back to Dashboard</span>
          <span className="sm:hidden">Back</span>
        </Link>

        {/* Header */}
        <div className="mb-6 md:mb-8 flex items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl md:text-4xl font-bold text-gray-900">Settings</h1>
            <p className="mt-2 text-sm md:text-base text-gray-600">Manage your account preferences and detection rules</p>
          </div>
          <NotificationHistory notifications={history} onClearHistory={clearHistory} />
        </div>

        {/* Tabs */}
        <div className="mb-6 flex gap-2 md:gap-4 border-b border-gray-200 overflow-x-auto pb-0 scrollbar-hide">
          <button
            onClick={() => setActiveTab("detection")}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 font-semibold transition-colors whitespace-nowrap ${
              activeTab === "detection"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            <Sliders className="h-5 w-5" />
            Detection Rules
          </button>
          <button
            onClick={() => setActiveTab("profile")}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 font-semibold transition-colors whitespace-nowrap ${
              activeTab === "profile"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            <User className="h-5 w-5" />
            Profile
          </button>
          <button
            onClick={() => setActiveTab("notifications")}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 font-semibold transition-colors whitespace-nowrap ${
              activeTab === "notifications"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            <Bell className="h-5 w-5" />
            Notifications
          </button>
          <button
            onClick={() => setActiveTab("security")}
            className={`flex items-center gap-2 border-b-2 px-4 py-3 font-semibold transition-colors whitespace-nowrap ${
              activeTab === "security"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
          >
            <Shield className="h-5 w-5" />
            Security
          </button>
        </div>

        {/* Advanced Notification Toast */}
        {currentNotification && (
          <Toast notification={currentNotification} onClose={dismiss} />
        )}

        {/* Detection Rules Tab */}
        {activeTab === "detection" && (
          <div className="space-y-6">
            <div className="rounded-2xl bg-gradient-to-br from-blue-50 to-indigo-50 border-2 border-blue-200 p-4 md:p-6">
              <div className="flex flex-col gap-4">
                <div className="flex flex-col sm:flex-row items-start justify-between gap-4">
                  <div className="flex-1">
                    <h2 className="text-lg md:text-xl font-bold text-blue-900 mb-2">🎯 Configure Detection Criteria</h2>
                    <p className="text-sm md:text-base text-blue-700">
                      Customize how CloudWaste identifies orphaned resources across AWS and Azure.
                      Adjust age thresholds and confidence levels to match your workflow.
                    </p>
                  </div>
                  <button
                    onClick={resetAllRules}
                    className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-lg border-2 border-orange-400 bg-orange-50 px-4 py-2 text-sm font-semibold text-orange-700 hover:bg-orange-100 transition-colors whitespace-nowrap"
                    title="Reset all detection rules to default values"
                  >
                    <RotateCcw className="h-4 w-4" />
                    <span className="hidden md:inline">Reset All to Defaults</span>
                    <span className="md:hidden">Reset All</span>
                  </button>
                </div>

                {/* Provider Filter */}
                <div className="flex gap-2">
                  <button
                    onClick={() => setSelectedProvider("all")}
                    className={`px-4 py-2 rounded-lg font-semibold transition-colors ${
                      selectedProvider === "all"
                        ? "bg-blue-600 text-white"
                        : "bg-white text-gray-700 border-2 border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    All Providers
                  </button>
                  <button
                    onClick={() => setSelectedProvider("aws")}
                    className={`px-4 py-2 rounded-lg font-semibold transition-colors ${
                      selectedProvider === "aws"
                        ? "bg-orange-500 text-white"
                        : "bg-white text-gray-700 border-2 border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    🟠 AWS
                  </button>
                  <button
                    onClick={() => setSelectedProvider("azure")}
                    className={`px-4 py-2 rounded-lg font-semibold transition-colors ${
                      selectedProvider === "azure"
                        ? "bg-blue-500 text-white"
                        : "bg-white text-gray-700 border-2 border-gray-300 hover:bg-gray-50"
                    }`}
                  >
                    🔵 Azure
                  </button>
                </div>
              </div>
            </div>

            {isLoading ? (
              <div className="text-center py-12 text-gray-600">Loading detection rules...</div>
            ) : (
              detectionRules
                .filter((rule) => {
                  if (selectedProvider === "all") return true;
                  const provider = getResourceProvider(rule.resource_type);
                  return provider === selectedProvider;
                })
                .map((rule) => {
                const Icon = getResourceIcon(rule.resource_type);
                const label = getResourceLabel(rule.resource_type);
                const isCustomized = JSON.stringify(rule.current_rules) !== JSON.stringify(rule.default_rules);
                const provider = getResourceProvider(rule.resource_type);

                return (
                  <div
                    key={rule.resource_type}
                    className={`rounded-2xl bg-white p-4 md:p-6 shadow-lg border-2 transition-all ${
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
                              provider === "azure"
                                ? "bg-blue-100 text-blue-800"
                                : "bg-orange-100 text-orange-800"
                            }`}>
                              {provider === "azure" ? "🔵 AZURE" : "🟠 AWS"}
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
                            {rule.resource_type === 'ec2_instance' ? 'Minimum Age (Stopped Instances)' : 'Minimum Age'}: {rule.current_rules.min_age_days || rule.current_rules.min_stopped_days} days
                          </h4>
                          <span className="text-sm text-gray-500">
                            Default: {rule.default_rules.min_age_days || rule.default_rules.min_stopped_days} days
                          </span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max="90"
                          step="1"
                          value={rule.current_rules.min_age_days || rule.current_rules.min_stopped_days || 0}
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

                        {/* Interactive Example */}
                        <div className="mt-4 rounded-lg bg-gradient-to-r from-blue-50 to-purple-50 border-2 border-blue-200 p-4">
                          <h5 className="font-semibold text-blue-900 mb-2 flex items-center gap-2">
                            <span>💡</span> What will be detected?
                          </h5>
                          <div className="space-y-2 text-sm">
                            <div className="flex items-start gap-2">
                              <span className="text-green-600 font-bold">✓</span>
                              <span className="text-gray-700">
                                Resources created <strong>{rule.current_rules.min_age_days || rule.current_rules.min_stopped_days}+ days ago</strong> will be detected
                              </span>
                            </div>
                            <div className="flex items-start gap-2">
                              <span className="text-red-600 font-bold">✗</span>
                              <span className="text-gray-700">
                                Resources created <strong>less than {rule.current_rules.min_age_days || rule.current_rules.min_stopped_days} days ago</strong> will be ignored
                              </span>
                            </div>
                          </div>
                          <div className="mt-3 p-3 bg-white rounded border border-blue-300">
                            <p className="text-xs text-blue-800">
                              <strong>Example:</strong> If set to <strong>{rule.current_rules?.min_age_days || rule.current_rules?.min_stopped_days || 0} days</strong>:
                              {(rule.current_rules?.min_age_days || rule.current_rules?.min_stopped_days || 0) === 0 ? (
                                <> All {rule.resource_type.replace('_', ' ')} will be detected immediately, even brand new ones.</>
                              ) : (
                                <> A {rule.resource_type.replace('_', ' ')} created on {new Date(Date.now() - ((rule.current_rules?.min_age_days || rule.current_rules?.min_stopped_days || 0) * 24 * 60 * 60 * 1000)).toLocaleDateString()} or earlier will be detected. One created today will be ignored.</>
                              )}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Confidence Level Thresholds (New Standardized System) */}
                    <div className="mb-4">
                      <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                        🎯 Confidence Level Thresholds
                      </h4>
                      <div className="space-y-4 p-4 bg-gradient-to-r from-blue-50 to-purple-50 border-2 border-blue-200 rounded-lg">
                        {/* Critical Threshold */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <label className="text-sm font-medium text-gray-900 flex items-center gap-2">
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border bg-red-100 text-red-800 border-red-300">
                                🔴 Critical
                              </span>
                              After {rule.current_rules.confidence_critical_days || rule.default_rules.confidence_critical_days || 90} days
                            </label>
                            <span className="text-xs text-gray-500">
                              Default: {rule.default_rules.confidence_critical_days || 90} days
                            </span>
                          </div>
                          <input
                            type="range"
                            min="30"
                            max="365"
                            step="1"
                            value={rule.current_rules.confidence_critical_days || rule.default_rules.confidence_critical_days || 90}
                            onChange={(e) =>
                              handleRuleChange(
                                rule.resource_type,
                                "confidence_critical_days",
                                parseInt(e.target.value)
                              )
                            }
                            className="w-full h-2 bg-gradient-to-r from-orange-200 to-red-300 rounded-lg appearance-none cursor-pointer"
                          />
                          <div className="flex justify-between text-xs text-gray-500 mt-1">
                            <span>30 days</span>
                            <span>365 days</span>
                          </div>
                        </div>

                        {/* High Threshold */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <label className="text-sm font-medium text-gray-900 flex items-center gap-2">
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border bg-orange-100 text-orange-800 border-orange-300">
                                🟠 High
                              </span>
                              After {rule.current_rules.confidence_high_days || rule.default_rules.confidence_high_days || 30} days
                            </label>
                            <span className="text-xs text-gray-500">
                              Default: {rule.default_rules.confidence_high_days || 30} days
                            </span>
                          </div>
                          <input
                            type="range"
                            min="7"
                            max="180"
                            step="1"
                            value={rule.current_rules.confidence_high_days || rule.default_rules.confidence_high_days || 30}
                            onChange={(e) =>
                              handleRuleChange(
                                rule.resource_type,
                                "confidence_high_days",
                                parseInt(e.target.value)
                              )
                            }
                            className="w-full h-2 bg-gradient-to-r from-yellow-200 to-orange-300 rounded-lg appearance-none cursor-pointer"
                          />
                          <div className="flex justify-between text-xs text-gray-500 mt-1">
                            <span>7 days</span>
                            <span>180 days</span>
                          </div>
                        </div>

                        {/* Medium Threshold */}
                        <div>
                          <div className="flex items-center justify-between mb-2">
                            <label className="text-sm font-medium text-gray-900 flex items-center gap-2">
                              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border bg-yellow-100 text-yellow-800 border-yellow-300">
                                🟡 Medium
                              </span>
                              After {rule.current_rules.confidence_medium_days || rule.default_rules.confidence_medium_days || 7} days
                            </label>
                            <span className="text-xs text-gray-500">
                              Default: {rule.default_rules.confidence_medium_days || 7} days
                            </span>
                          </div>
                          <input
                            type="range"
                            min="1"
                            max="60"
                            step="1"
                            value={rule.current_rules.confidence_medium_days || rule.default_rules.confidence_medium_days || 7}
                            onChange={(e) =>
                              handleRuleChange(
                                rule.resource_type,
                                "confidence_medium_days",
                                parseInt(e.target.value)
                              )
                            }
                            className="w-full h-2 bg-gradient-to-r from-green-200 to-yellow-300 rounded-lg appearance-none cursor-pointer"
                          />
                          <div className="flex justify-between text-xs text-gray-500 mt-1">
                            <span>1 day</span>
                            <span>60 days</span>
                          </div>
                        </div>

                        {/* Visual Example */}
                        <div className="mt-4 p-3 bg-white rounded border border-blue-300">
                          <h5 className="font-semibold text-blue-900 mb-2 text-sm">How it works:</h5>
                          <div className="space-y-1.5 text-xs text-gray-700">
                            <div className="flex items-center gap-2">
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold border bg-red-100 text-red-800 border-red-300">🔴</span>
                              <span>Resources <strong>{rule.current_rules.confidence_critical_days || rule.default_rules.confidence_critical_days || 90}+ days old</strong> → Critical priority</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold border bg-orange-100 text-orange-800 border-orange-300">🟠</span>
                              <span>Resources <strong>{rule.current_rules.confidence_high_days || rule.default_rules.confidence_high_days || 30}-{(rule.current_rules.confidence_critical_days || rule.default_rules.confidence_critical_days || 90) - 1} days old</strong> → High priority</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold border bg-yellow-100 text-yellow-800 border-yellow-300">🟡</span>
                              <span>Resources <strong>{rule.current_rules.confidence_medium_days || rule.default_rules.confidence_medium_days || 7}-{(rule.current_rules.confidence_high_days || rule.default_rules.confidence_high_days || 30) - 1} days old</strong> → Medium priority</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-xs font-semibold border bg-green-100 text-green-800 border-green-300">🟢</span>
                              <span>Resources <strong>less than {rule.current_rules.confidence_medium_days || rule.default_rules.confidence_medium_days || 7} days old</strong> → Low priority</span>
                            </div>
                          </div>
                          <p className="mt-2 text-xs text-blue-800 italic">
                            💡 Tip: Use these thresholds to prioritize which orphaned resources to clean up first based on how long they've been wasting money.
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Legacy Confidence Threshold (Kept for backwards compatibility) */}
                    {rule.current_rules.confidence_threshold_days !== undefined && (
                      <div className="mb-4 opacity-50">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-semibold text-gray-900 text-sm">
                            Legacy: High Confidence After {rule.current_rules.confidence_threshold_days} days
                          </h4>
                          <span className="text-xs text-gray-500">
                            (Use new system above)
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Idle Running Instances Threshold (EC2 only) */}
                    {rule.resource_type === 'ec2_instance' && rule.current_rules.min_idle_days !== undefined && (
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

                        {/* Interactive Example for Idle Running */}
                        <div className="mt-4 rounded-lg bg-gradient-to-r from-cyan-50 to-blue-50 border-2 border-cyan-200 p-4">
                          <h5 className="font-semibold text-cyan-900 mb-2 flex items-center gap-2">
                            <span>🔋</span> What will be detected?
                          </h5>
                          <div className="space-y-2 text-sm">
                            <div className="flex items-start gap-2">
                              <span className="text-green-600 font-bold">✓</span>
                              <span className="text-gray-700">
                                <strong>Running</strong> instances with low CPU (&lt;5%) and low network (&lt;1MB) for <strong>{rule.current_rules.min_idle_days}+ days</strong> will be detected as idle
                              </span>
                            </div>
                            <div className="flex items-start gap-2">
                              <span className="text-red-600 font-bold">✗</span>
                              <span className="text-gray-700">
                                Running instances idle for <strong>less than {rule.current_rules.min_idle_days} days</strong> will be ignored
                              </span>
                            </div>
                          </div>
                          <div className="mt-3 p-3 bg-white rounded border border-cyan-300">
                            <p className="text-xs text-cyan-800">
                              <strong>Note:</strong> This setting applies ONLY to running instances with very low utilization. Stopped instances are controlled by the "Minimum Age (Stopped Instances)" setting above.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        )}

        {/* Profile Tab */}
        {activeTab === "profile" && (
          <div className="rounded-2xl bg-white p-8 shadow-lg">
            <h2 className="mb-6 text-2xl font-bold text-gray-900">Profile Information</h2>
            <div className="space-y-6">
              <div>
                <label className="mb-2 block text-sm font-semibold text-gray-700">Full Name</label>
                <input
                  type="text"
                  placeholder="John Doe"
                  className="w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              </div>
              <div>
                <label className="mb-2 block text-sm font-semibold text-gray-700">Email Address</label>
                <input
                  type="email"
                  placeholder="john@example.com"
                  className="w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                />
              </div>
              <div className="flex gap-4 pt-4">
                <button className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-3 font-semibold text-white shadow-lg transition-all hover:scale-[1.02] hover:shadow-xl">
                  <Save className="h-5 w-5" />
                  Save Changes
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Notifications Tab */}
        {activeTab === "notifications" && (
          <div className="rounded-2xl bg-white p-8 shadow-lg">
            <h2 className="mb-6 text-2xl font-bold text-gray-900">Notification Preferences</h2>
            <div className="space-y-6">
              <div className="flex items-center justify-between border-b border-gray-200 pb-4">
                <div>
                  <h3 className="font-semibold text-gray-900">Scan Completion</h3>
                  <p className="text-sm text-gray-600">Get notified when scans finish</p>
                </div>
                <label className="relative inline-flex cursor-pointer items-center">
                  <input type="checkbox" className="peer sr-only" defaultChecked />
                  <div className="peer h-6 w-11 rounded-full bg-gray-300 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:bg-blue-600 peer-checked:after:translate-x-full"></div>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Security Tab */}
        {activeTab === "security" && (
          <div className="space-y-6">
            <div className="rounded-2xl bg-white p-8 shadow-lg">
              <h2 className="mb-6 text-2xl font-bold text-gray-900">Change Password</h2>
              <div className="space-y-6">
                <div>
                  <label className="mb-2 block text-sm font-semibold text-gray-700">Current Password</label>
                  <input
                    type="password"
                    className="w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                  />
                </div>
                <button className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-3 font-semibold text-white shadow-lg transition-all hover:scale-[1.02] hover:shadow-xl">
                  <Key className="h-5 w-5" />
                  Update Password
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
