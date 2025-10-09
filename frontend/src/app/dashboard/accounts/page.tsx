"use client";

import { useEffect, useState } from "react";
import { useAccountStore } from "@/stores/useAccountStore";
import { Plus, Trash2, RefreshCw, CheckCircle, XCircle, HelpCircle, ChevronDown, ChevronUp, Copy, ExternalLink, Edit } from "lucide-react";

export default function AccountsPage() {
  const { accounts, fetchAccounts, deleteAccount, isLoading } = useAccountStore();
  const [showAddForm, setShowAddForm] = useState(false);
  const [editingAccount, setEditingAccount] = useState<any>(null);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  return (
    <div className="space-y-4 md:space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900">Cloud Accounts</h1>
          <p className="mt-1 md:mt-2 text-sm md:text-base text-gray-600">
            Manage your cloud provider accounts for resource scanning
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition-colors hover:bg-blue-700"
        >
          <Plus className="h-5 w-5" />
          Add Account
        </button>
      </div>

      {/* Add Account Form */}
      {showAddForm && <AddAccountForm onClose={() => setShowAddForm(false)} />}

      {/* Edit Account Form */}
      {editingAccount && (
        <EditAccountForm
          account={editingAccount}
          onClose={() => setEditingAccount(null)}
        />
      )}

      {/* Accounts List */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="h-8 w-8 animate-spin text-gray-400" />
        </div>
      ) : accounts.length === 0 ? (
        <div className="rounded-lg border border-dashed border-gray-300 p-12 text-center">
          <h3 className="text-lg font-medium text-gray-900">No accounts yet</h3>
          <p className="mt-2 text-gray-600">
            Get started by adding your first cloud account
          </p>
          <button
            onClick={() => setShowAddForm(true)}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-5 w-5" />
            Add Account
          </button>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {accounts.map((account) => (
            <AccountCard
              key={account.id}
              account={account}
              onEdit={() => setEditingAccount(account)}
              onDelete={() => deleteAccount(account.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AccountCard({ account, onEdit, onDelete }: any) {
  const providerColors: any = {
    aws: "bg-orange-100 text-orange-700",
    azure: "bg-blue-100 text-blue-700",
    gcp: "bg-red-100 text-red-700",
  };

  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <span
              className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ${
                providerColors[account.provider] || "bg-gray-100 text-gray-700"
              }`}
            >
              {account.provider}
            </span>
            {account.is_active ? (
              <CheckCircle className="h-4 w-4 text-green-500" />
            ) : (
              <XCircle className="h-4 w-4 text-red-500" />
            )}
          </div>
          <h3 className="mt-3 text-lg font-semibold text-gray-900">
            {account.account_name}
          </h3>
          <p className="mt-1 text-sm text-gray-600">
            ID: {account.account_identifier}
          </p>
          {account.regions?.regions && (
            <p className="mt-2 text-sm text-gray-500">
              Regions: {account.regions.regions.join(", ")}
            </p>
          )}
          {account.last_scan_at && (
            <p className="mt-2 text-xs text-gray-400">
              Last scan: {new Date(account.last_scan_at).toLocaleDateString()}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={onEdit}
            className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-blue-50 hover:text-blue-600"
            title="Edit account"
          >
            <Edit className="h-5 w-5" />
          </button>
          <button
            onClick={onDelete}
            className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600"
            title="Delete account"
          >
            <Trash2 className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
}

function AWSCredentialsHelp() {
  const [copiedPolicy, setCopiedPolicy] = useState(false);

  const iamPolicy = `{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ec2:Describe*",
      "rds:Describe*",
      "s3:List*",
      "s3:Get*",
      "elasticloadbalancing:Describe*",
      "ce:GetCostAndUsage",
      "ce:GetCostForecast",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics",
      "sts:GetCallerIdentity",
      "fsx:DescribeFileSystems",
      "kafka:ListClusters",
      "kafka:ListClustersV2",
      "eks:ListClusters",
      "eks:DescribeCluster",
      "eks:ListNodegroups",
      "eks:DescribeNodegroup",
      "sagemaker:ListEndpoints",
      "sagemaker:DescribeEndpoint",
      "sagemaker:DescribeEndpointConfig",
      "redshift:DescribeClusters",
      "elasticache:DescribeCacheClusters",
      "globalaccelerator:ListAccelerators",
      "globalaccelerator:ListListeners",
      "globalaccelerator:ListEndpointGroups",
      "kinesis:ListStreams",
      "kinesis:DescribeStream"
    ],
    "Resource": "*"
  }]
}`;

  const copyPolicy = () => {
    navigator.clipboard.writeText(iamPolicy);
    setCopiedPolicy(true);
    setTimeout(() => setCopiedPolicy(false), 2000);
  };

  return (
    <div className="mb-6 rounded-xl border-2 border-green-200 bg-gradient-to-br from-green-50 to-blue-50 p-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-600 text-white shadow-md">
          <HelpCircle className="h-6 w-6" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-gray-900">How to get your AWS credentials</h3>
          <p className="text-sm text-gray-600 mt-1">Follow these steps to create a read-only IAM user</p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Step 1 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-white font-bold text-sm flex-shrink-0">
            1
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Go to AWS IAM Console</h4>
            <p className="text-sm text-gray-600 mt-1">
              Search for "IAM" in AWS Console → Click "Users" → "Create user"
            </p>
            <a
              href="https://console.aws.amazon.com/iam/home#/users"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              <ExternalLink className="h-4 w-4" />
              Open IAM Console
            </a>
          </div>
        </div>

        {/* Step 2 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-purple-600 text-white font-bold text-sm flex-shrink-0">
            2
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Create IAM User</h4>
            <p className="text-sm text-gray-600 mt-1">
              User name: <code className="bg-gray-200 px-2 py-0.5 rounded">cloudwaste-scanner</code>
              <br />
              Access type: ✓ Programmatic access (NOT Console access)
            </p>
          </div>
        </div>

        {/* Step 3 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-orange-600 text-white font-bold text-sm flex-shrink-0">
            3
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Attach Read-Only Policy</h4>
            <p className="text-sm text-gray-600 mt-1">
              Click "Create policy" → Select JSON tab → Paste this policy:
            </p>
            <div className="mt-2 relative">
              <pre className="bg-gray-900 text-green-400 p-4 rounded-lg text-xs overflow-x-auto">
                {iamPolicy}
              </pre>
              <button
                onClick={copyPolicy}
                className="absolute top-2 right-2 flex items-center gap-1 rounded bg-gray-700 px-3 py-1 text-xs text-white hover:bg-gray-600 transition-colors"
              >
                <Copy className="h-3 w-3" />
                {copiedPolicy ? "Copied!" : "Copy"}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-2">
              Policy name: <code className="bg-gray-200 px-2 py-0.5 rounded">CloudWasteReadOnlyPolicy</code>
            </p>
          </div>
        </div>

        {/* Step 4 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-green-600 text-white font-bold text-sm flex-shrink-0">
            4
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Get Credentials & Account ID</h4>
            <p className="text-sm text-gray-600 mt-1">
              After creating the user, AWS will show:
            </p>
            <ul className="text-sm text-gray-600 mt-2 space-y-1 list-disc list-inside">
              <li><strong>Access Key ID</strong>: AKIAIOSFODNN7EXAMPLE</li>
              <li><strong>Secret Access Key</strong>: wJalrXUtnFEMI/...</li>
            </ul>
            <div className="mt-3 rounded-lg bg-amber-50 border border-amber-200 p-3">
              <p className="text-xs text-amber-800 font-medium">
                ⚠️ Save the Secret Key now - you won't see it again!
              </p>
            </div>
            <p className="text-sm text-gray-600 mt-3">
              <strong>Account ID</strong>: Click your name (top-right) → 12-digit number
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-lg bg-blue-50 border border-blue-200 p-4">
        <p className="text-sm text-blue-900">
          <strong>🔒 Security:</strong> CloudWaste only uses READ-ONLY permissions. We never modify or delete your AWS resources.
        </p>
      </div>
    </div>
  );
}

function AddAccountForm({ onClose }: { onClose: () => void }) {
  const { createAccount, isLoading, error } = useAccountStore();
  const [showHelp, setShowHelp] = useState(false);
  const [formData, setFormData] = useState({
    account_name: "",
    account_identifier: "",
    aws_access_key_id: "",
    aws_secret_access_key: "",
    regions: "us-east-1,eu-west-1,eu-central-1",
    description: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createAccount({
        provider: "aws",
        account_name: formData.account_name,
        account_identifier: formData.account_identifier,
        aws_access_key_id: formData.aws_access_key_id,
        aws_secret_access_key: formData.aws_secret_access_key,
        regions: formData.regions.split(",").map((r) => r.trim()),
        description: formData.description || undefined,
      });
      onClose();
    } catch (err) {
      // Error handled by store
    }
  };

  return (
    <div className="rounded-2xl border-2 border-blue-200 bg-white p-8 shadow-xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          Add AWS Account
        </h2>
        <button
          type="button"
          onClick={() => setShowHelp(!showHelp)}
          className="flex items-center gap-2 rounded-lg bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 transition-colors"
        >
          <HelpCircle className="h-4 w-4" />
          {showHelp ? "Hide" : "How to get credentials?"}
          {showHelp ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {/* Help Section */}
      {showHelp && <AWSCredentialsHelp />}

      <form onSubmit={handleSubmit} className="mt-6 space-y-5">
        {error && (
          <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-700 flex items-start gap-2">
            <XCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Account Name *
          </label>
          <input
            required
            type="text"
            value={formData.account_name}
            onChange={(e) =>
              setFormData({ ...formData, account_name: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
            placeholder="Production AWS"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            AWS Account ID *
            <span className="ml-2 text-xs font-normal text-gray-500">(12 digits)</span>
          </label>
          <input
            required
            type="text"
            value={formData.account_identifier}
            onChange={(e) =>
              setFormData({ ...formData, account_identifier: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono"
            placeholder="123456789012"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            AWS Access Key ID *
          </label>
          <input
            required
            type="text"
            value={formData.aws_access_key_id}
            onChange={(e) =>
              setFormData({ ...formData, aws_access_key_id: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
            placeholder="AKIAIOSFODNN7EXAMPLE"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            AWS Secret Access Key *
          </label>
          <input
            required
            type="password"
            value={formData.aws_secret_access_key}
            onChange={(e) =>
              setFormData({
                ...formData,
                aws_secret_access_key: e.target.value,
              })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
            placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Regions (comma-separated, max 3)
          </label>
          <input
            type="text"
            value={formData.regions}
            onChange={(e) =>
              setFormData({ ...formData, regions: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono"
            placeholder="us-east-1,eu-west-1,eu-central-1"
          />
          <p className="mt-2 text-xs text-gray-500">
            💡 Tip: Limit to 3 regions for faster scans
          </p>
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Description (optional)
          </label>
          <textarea
            value={formData.description}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
            rows={3}
            placeholder="Production environment AWS account"
          />
        </div>

        <div className="flex gap-4 pt-4">
          <button
            type="submit"
            disabled={isLoading}
            className="flex-1 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-3 font-semibold text-white shadow-lg hover:shadow-xl transition-all hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <>
                <RefreshCw className="h-5 w-5 animate-spin" />
                Adding...
              </>
            ) : (
              <>
                <Plus className="h-5 w-5" />
                Add Account
              </>
            )}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-all"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

function EditAccountForm({ account, onClose }: { account: any; onClose: () => void }) {
  const { updateAccount, isLoading, error } = useAccountStore();
  const [formData, setFormData] = useState({
    account_name: account.account_name || "",
    aws_access_key_id: "",
    aws_secret_access_key: "",
    regions: account.regions?.join(",") || "us-east-1",
    scheduled_scan_enabled: account.scheduled_scan_enabled ?? true,
    scheduled_scan_frequency: account.scheduled_scan_frequency || "daily",
    scheduled_scan_hour: account.scheduled_scan_hour ?? 2,
    scheduled_scan_day_of_week: account.scheduled_scan_day_of_week ?? 0,
    scheduled_scan_day_of_month: account.scheduled_scan_day_of_month ?? 1,
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const updateData: any = {
        account_name: formData.account_name,
        regions: formData.regions.split(",").map((r) => r.trim()),
        scheduled_scan_enabled: formData.scheduled_scan_enabled,
        scheduled_scan_frequency: formData.scheduled_scan_frequency,
        scheduled_scan_hour: formData.scheduled_scan_hour,
      };

      // Add day fields based on frequency
      if (formData.scheduled_scan_frequency === "weekly") {
        updateData.scheduled_scan_day_of_week = formData.scheduled_scan_day_of_week;
      } else if (formData.scheduled_scan_frequency === "monthly") {
        updateData.scheduled_scan_day_of_month = formData.scheduled_scan_day_of_month;
      }

      // Only include credentials if they were provided
      if (formData.aws_access_key_id && formData.aws_secret_access_key) {
        updateData.aws_access_key_id = formData.aws_access_key_id;
        updateData.aws_secret_access_key = formData.aws_secret_access_key;
      }

      await updateAccount(account.id, updateData);
      onClose();
    } catch (err) {
      // Error handled by store
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4">
      <div className="max-w-2xl w-full rounded-2xl border-2 border-blue-200 bg-white p-8 shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
            Edit AWS Account
          </h2>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="rounded-xl bg-red-50 border border-red-200 p-4 text-sm text-red-700 flex items-start gap-2">
              <XCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Account Name *
            </label>
            <input
              required
              type="text"
              value={formData.account_name}
              onChange={(e) =>
                setFormData({ ...formData, account_name: e.target.value })
              }
              className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
              placeholder="Production AWS"
            />
          </div>

          <div className="rounded-xl bg-blue-50 border border-blue-200 p-4">
            <p className="text-sm text-blue-900">
              <strong>Update Credentials (optional):</strong> Leave empty to keep existing credentials. Fill both fields to update.
            </p>
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              New AWS Access Key ID (optional)
            </label>
            <input
              type="text"
              value={formData.aws_access_key_id}
              onChange={(e) =>
                setFormData({ ...formData, aws_access_key_id: e.target.value })
              }
              className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
              placeholder="AKIAIOSFODNN7EXAMPLE"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              New AWS Secret Access Key (optional)
            </label>
            <input
              type="password"
              value={formData.aws_secret_access_key}
              onChange={(e) =>
                setFormData({
                  ...formData,
                  aws_secret_access_key: e.target.value,
                })
              }
              className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
              placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
            />
          </div>

          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-2">
              Regions (comma-separated, max 3)
            </label>
            <input
              type="text"
              value={formData.regions}
              onChange={(e) =>
                setFormData({ ...formData, regions: e.target.value })
              }
              className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono"
              placeholder="us-east-1,eu-west-1,eu-central-1"
            />
            <p className="mt-2 text-xs text-gray-500">
              💡 Tip: Limit to 3 regions for faster scans
            </p>
          </div>

          {/* Scheduled Scan Settings */}
          <div className="space-y-4 rounded-xl bg-purple-50 border border-purple-200 p-6">
            <h3 className="text-lg font-bold text-purple-900">Scheduled Scan Settings</h3>

            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="scheduled_scan_enabled"
                checked={formData.scheduled_scan_enabled}
                onChange={(e) =>
                  setFormData({ ...formData, scheduled_scan_enabled: e.target.checked })
                }
                className="h-5 w-5 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
              />
              <label htmlFor="scheduled_scan_enabled" className="text-sm font-semibold text-gray-700">
                Enable automatic scheduled scans
              </label>
            </div>

            {formData.scheduled_scan_enabled && (
              <>
                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Scan Frequency
                  </label>
                  <select
                    value={formData.scheduled_scan_frequency}
                    onChange={(e) =>
                      setFormData({ ...formData, scheduled_scan_frequency: e.target.value })
                    }
                    className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition-all"
                  >
                    <option value="daily">Daily</option>
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-semibold text-gray-700 mb-2">
                    Scan Hour (UTC)
                  </label>
                  <select
                    value={formData.scheduled_scan_hour}
                    onChange={(e) =>
                      setFormData({ ...formData, scheduled_scan_hour: parseInt(e.target.value) })
                    }
                    className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition-all"
                  >
                    {Array.from({ length: 24 }, (_, i) => (
                      <option key={i} value={i}>
                        {i.toString().padStart(2, '0')}:00 UTC
                      </option>
                    ))}
                  </select>
                  <p className="mt-2 text-xs text-gray-500">
                    💡 Current UTC time: {new Date().toUTCString()}
                  </p>
                </div>

                {formData.scheduled_scan_frequency === "weekly" && (
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Day of Week
                    </label>
                    <select
                      value={formData.scheduled_scan_day_of_week}
                      onChange={(e) =>
                        setFormData({ ...formData, scheduled_scan_day_of_week: parseInt(e.target.value) })
                      }
                      className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition-all"
                    >
                      <option value={0}>Monday</option>
                      <option value={1}>Tuesday</option>
                      <option value={2}>Wednesday</option>
                      <option value={3}>Thursday</option>
                      <option value={4}>Friday</option>
                      <option value={5}>Saturday</option>
                      <option value={6}>Sunday</option>
                    </select>
                  </div>
                )}

                {formData.scheduled_scan_frequency === "monthly" && (
                  <div>
                    <label className="block text-sm font-semibold text-gray-700 mb-2">
                      Day of Month
                    </label>
                    <select
                      value={formData.scheduled_scan_day_of_month}
                      onChange={(e) =>
                        setFormData({ ...formData, scheduled_scan_day_of_month: parseInt(e.target.value) })
                      }
                      className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-purple-500 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition-all"
                    >
                      {Array.from({ length: 31 }, (_, i) => (
                        <option key={i + 1} value={i + 1}>
                          {i + 1}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </>
            )}
          </div>

          <div className="flex gap-4 pt-4">
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 rounded-xl bg-gradient-to-r from-blue-600 to-purple-600 px-6 py-3 font-semibold text-white shadow-lg hover:shadow-xl transition-all hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="h-5 w-5 animate-spin" />
                  Updating...
                </>
              ) : (
                <>
                  <CheckCircle className="h-5 w-5" />
                  Update Account
                </>
              )}
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-all"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
