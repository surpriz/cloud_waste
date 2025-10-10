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
    [key: string]: any;
  };
  default_rules: {
    enabled: boolean;
    min_age_days?: number;
    min_stopped_days?: number;
    confidence_threshold_days?: number;
    description?: string;
    [key: string]: any;
  };
  description: string;
}

const RESOURCE_ICONS: { [key: string]: any } = {
  ebs_volume: HardDrive,
  elastic_ip: Globe,
  ebs_snapshot: Camera,
  ec2_instance: Server,
  nat_gateway: Activity,
  load_balancer: Zap,
  rds_instance: Database,
};

const RESOURCE_LABELS: { [key: string]: string } = {
  ebs_volume: "EBS Volumes",
  elastic_ip: "Elastic IPs",
  ebs_snapshot: "EBS Snapshots",
  ec2_instance: "EC2 Instances (Stopped)",
  nat_gateway: "NAT Gateways",
  load_balancer: "Load Balancers",
  rds_instance: "RDS Instances",
};

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<"profile" | "notifications" | "security" | "detection">("detection");
  const [detectionRules, setDetectionRules] = useState<DetectionRule[]>([]);
  const [isLoading, setIsLoading] = useState(false);

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
      const response = await fetch("http://localhost:8000/api/v1/detection-rules/", {
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
      const response = await fetch(`http://localhost:8000/api/v1/detection-rules/${resourceType}`, {
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
      const response = await fetch(`http://localhost:8000/api/v1/detection-rules/${resourceType}`, {
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
      const response = await fetch(`http://localhost:8000/api/v1/detection-rules/`, {
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
              <div className="flex flex-col sm:flex-row items-start justify-between gap-4">
                <div className="flex-1">
                  <h2 className="text-lg md:text-xl font-bold text-blue-900 mb-2">🎯 Configure Detection Criteria</h2>
                  <p className="text-sm md:text-base text-blue-700">
                    Customize how CloudWaste identifies orphaned resources in your AWS infrastructure.
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
            </div>

            {isLoading ? (
              <div className="text-center py-12 text-gray-600">Loading detection rules...</div>
            ) : (
              detectionRules.map((rule) => {
                const Icon = RESOURCE_ICONS[rule.resource_type] || HardDrive;
                const label = RESOURCE_LABELS[rule.resource_type] || rule.resource_type;
                const isCustomized = JSON.stringify(rule.current_rules) !== JSON.stringify(rule.default_rules);

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
                            {isCustomized && (
                              <span className="text-xs bg-orange-200 text-orange-800 px-2 py-1 rounded-full font-semibold">
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
                              <strong>Example:</strong> If set to <strong>{rule.current_rules.min_age_days || rule.current_rules.min_stopped_days} days</strong>:
                              {(rule.current_rules.min_age_days || rule.current_rules.min_stopped_days) === 0 ? (
                                <> All {rule.resource_type.replace('_', ' ')} will be detected immediately, even brand new ones.</>
                              ) : (
                                <> A {rule.resource_type.replace('_', ' ')} created on {new Date(Date.now() - (rule.current_rules.min_age_days || rule.current_rules.min_stopped_days) * 24 * 60 * 60 * 1000).toLocaleDateString()} or earlier will be detected. One created today will be ignored.</>
                              )}
                            </p>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Confidence Threshold */}
                    {rule.current_rules.confidence_threshold_days !== undefined && (
                      <div className="mb-4">
                        <div className="flex items-center justify-between mb-2">
                          <h4 className="font-semibold text-gray-900">
                            High Confidence After: {rule.current_rules.confidence_threshold_days} days
                          </h4>
                          <span className="text-sm text-gray-500">
                            Default: {rule.default_rules.confidence_threshold_days} days
                          </span>
                        </div>
                        <input
                          type="range"
                          min="7"
                          max="180"
                          step="1"
                          value={rule.current_rules.confidence_threshold_days}
                          onChange={(e) =>
                            handleRuleChange(
                              rule.resource_type,
                              "confidence_threshold_days",
                              parseInt(e.target.value)
                            )
                          }
                          className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
                        />
                        <div className="flex justify-between text-xs text-gray-500 mt-1">
                          <span>7 days</span>
                          <span>180 days</span>
                        </div>

                        {/* Interactive Example for Confidence */}
                        <div className="mt-4 rounded-lg bg-gradient-to-r from-purple-50 to-pink-50 border-2 border-purple-200 p-4">
                          <h5 className="font-semibold text-purple-900 mb-2 flex items-center gap-2">
                            <span>🎯</span> Confidence Levels
                          </h5>
                          <div className="space-y-2 text-sm">
                            <div className="flex items-start gap-2">
                              <span className="text-green-600 font-bold">HIGH</span>
                              <span className="text-gray-700">
                                Resources <strong>{rule.current_rules.confidence_threshold_days}+ days old</strong> → marked as <span className="bg-green-100 text-green-800 px-2 py-0.5 rounded font-semibold">high confidence</span>
                              </span>
                            </div>
                            <div className="flex items-start gap-2">
                              <span className="text-yellow-600 font-bold">LOW</span>
                              <span className="text-gray-700">
                                Resources <strong>less than {rule.current_rules.confidence_threshold_days} days old</strong> → marked as <span className="bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded font-semibold">low confidence</span>
                              </span>
                            </div>
                          </div>
                          <div className="mt-3 p-3 bg-white rounded border border-purple-300">
                            <p className="text-xs text-purple-800">
                              <strong>Why it matters:</strong> High confidence resources are very likely to be true orphans and safe to delete. Low confidence resources might still be in use or recently created for a purpose.
                            </p>
                          </div>
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
