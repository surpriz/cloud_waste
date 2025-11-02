"use client";

import { useEffect, useState } from "react";
import { useAccountStore } from "@/stores/useAccountStore";
import { accountsAPI } from "@/lib/api";
import { Plus, Trash2, RefreshCw, CheckCircle, XCircle, HelpCircle, ChevronDown, ChevronUp, Copy, ExternalLink, Edit, Info, AlertCircle } from "lucide-react";

export default function AccountsPage() {
  const { accounts, fetchAccounts, deleteAccount, isLoading } = useAccountStore();
  const [showProviderSelector, setShowProviderSelector] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<"aws" | "azure" | "gcp" | "microsoft365" | null>(null);
  const [editingAccount, setEditingAccount] = useState<any>(null);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  const handleAddAccount = (provider: "aws" | "azure" | "gcp" | "microsoft365") => {
    setSelectedProvider(provider);
    setShowProviderSelector(false);
  };

  const closeAddForm = () => {
    setSelectedProvider(null);
  };

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
          onClick={() => setShowProviderSelector(true)}
          className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition-colors hover:bg-blue-700"
        >
          <Plus className="h-5 w-5" />
          Add Account
        </button>
      </div>

      {/* Provider Selector */}
      {showProviderSelector && (
        <ProviderSelector
          onSelectProvider={handleAddAccount}
          onClose={() => setShowProviderSelector(false)}
        />
      )}

      {/* Add AWS Account Form */}
      {selectedProvider === "aws" && <AddAWSAccountForm onClose={closeAddForm} />}

      {/* Add Azure Account Form */}
      {selectedProvider === "azure" && <AddAzureAccountForm onClose={closeAddForm} />}

      {/* Add GCP Account Form */}
      {selectedProvider === "gcp" && <AddGCPAccountForm onClose={closeAddForm} />}

      {/* Add Microsoft 365 Account Form */}
      {selectedProvider === "microsoft365" && <AddMicrosoft365AccountForm onClose={closeAddForm} />}

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
            onClick={() => setShowProviderSelector(true)}
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
    microsoft365: "bg-green-100 text-green-700",
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
          {account.regions && Array.isArray(account.regions) && account.regions.length > 0 && (
            <p className="mt-2 text-sm text-gray-500">
              Regions: {account.regions.join(", ")}
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
      "s3:GetBucketLocation",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:ListAllMyBuckets",
      "elasticloadbalancing:Describe*",
      "fsx:Describe*",
      "neptune:Describe*",
      "neptune:List*",
      "kafka:ListClusters",
      "kafka:ListClustersV2",
      "kafka:DescribeCluster",
      "kafka:DescribeClusterV2",
      "eks:ListClusters",
      "eks:DescribeCluster",
      "eks:ListNodegroups",
      "eks:DescribeNodegroup",
      "sagemaker:ListEndpoints",
      "sagemaker:DescribeEndpoint",
      "sagemaker:DescribeEndpointConfig",
      "redshift:DescribeClusters",
      "elasticache:DescribeCacheClusters",
      "elasticache:DescribeReplicationGroups",
      "globalaccelerator:ListAccelerators",
      "globalaccelerator:ListListeners",
      "globalaccelerator:ListEndpointGroups",
      "kinesis:ListStreams",
      "kinesis:DescribeStream",
      "kinesis:DescribeStreamSummary",
      "es:DescribeDomains",
      "es:ListDomainNames",
      "docdb:DescribeDBClusters",
      "docdb:DescribeDBInstances",
      "lambda:ListFunctions",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:GetProvisionedConcurrencyConfig",
      "dynamodb:ListTables",
      "dynamodb:DescribeTable",
      "dynamodb:DescribeTimeToLive",
      "ce:GetCostAndUsage",
      "ce:GetCostForecast",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics",
      "sts:GetCallerIdentity"
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

function ProviderSelector({ onSelectProvider, onClose }: { onSelectProvider: (provider: "aws" | "azure" | "gcp" | "microsoft365") => void; onClose: () => void }) {
  return (
    <div className="rounded-2xl border-2 border-blue-200 bg-white p-8 shadow-xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
          Select Cloud Provider
        </h2>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* AWS Card */}
        <button
          onClick={() => onSelectProvider("aws")}
          className="flex flex-col items-center gap-4 rounded-xl border-2 border-orange-200 bg-orange-50 p-6 transition-all hover:border-orange-400 hover:bg-orange-100 hover:shadow-lg"
        >
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-orange-600 text-white shadow-md">
            <span className="text-2xl font-bold">AWS</span>
          </div>
          <div className="text-center">
            <h3 className="text-lg font-bold text-gray-900">Amazon Web Services</h3>
            <p className="mt-1 text-sm text-gray-600">Connect your AWS account</p>
          </div>
        </button>

        {/* Azure Card */}
        <button
          onClick={() => onSelectProvider("azure")}
          className="flex flex-col items-center gap-4 rounded-xl border-2 border-blue-200 bg-blue-50 p-6 transition-all hover:border-blue-400 hover:bg-blue-100 hover:shadow-lg"
        >
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-blue-600 text-white shadow-md">
            <span className="text-xl font-bold">Azure</span>
          </div>
          <div className="text-center">
            <h3 className="text-lg font-bold text-gray-900">Microsoft Azure</h3>
            <p className="mt-1 text-sm text-gray-600">Connect your Azure subscription</p>
          </div>
        </button>

        {/* GCP Card */}
        <button
          onClick={() => onSelectProvider("gcp")}
          className="flex flex-col items-center gap-4 rounded-xl border-2 border-red-200 bg-red-50 p-6 transition-all hover:border-red-400 hover:bg-red-100 hover:shadow-lg"
        >
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-600 text-white shadow-md">
            <span className="text-xl font-bold">GCP</span>
          </div>
          <div className="text-center">
            <h3 className="text-lg font-bold text-gray-900">Google Cloud Platform</h3>
            <p className="mt-1 text-sm text-gray-600">Connect your GCP project</p>
          </div>
        </button>

        {/* Microsoft 365 Card */}
        <button
          onClick={() => onSelectProvider("microsoft365")}
          className="flex flex-col items-center gap-4 rounded-xl border-2 border-green-200 bg-green-50 p-6 transition-all hover:border-green-400 hover:bg-green-100 hover:shadow-lg"
        >
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-600 text-white shadow-md">
            <span className="text-base font-bold">M365</span>
          </div>
          <div className="text-center">
            <h3 className="text-lg font-bold text-gray-900">Microsoft 365</h3>
            <p className="mt-1 text-sm text-gray-600">Connect SharePoint & OneDrive</p>
          </div>
        </button>
      </div>

      <div className="mt-6 flex justify-end">
        <button
          onClick={onClose}
          className="rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-all"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function AddAWSAccountForm({ onClose }: { onClose: () => void }) {
  const { createAccount, isLoading, error } = useAccountStore();
  const [showHelp, setShowHelp] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    status: 'idle' | 'success' | 'error';
    message: string;
  } | null>(null);
  const [formData, setFormData] = useState({
    account_name: "",
    account_identifier: "",
    aws_access_key_id: "",
    aws_secret_access_key: "",
    regions: "us-east-1,eu-west-1,eu-central-1",
    description: "",
  });

  const isFormValid = () => {
    return !!(
      formData.account_name &&
      formData.account_identifier &&
      formData.aws_access_key_id &&
      formData.aws_secret_access_key
    );
  };

  const handleTestConnection = async () => {
    setIsValidating(true);
    setValidationResult(null);

    try {
      const testData = {
        provider: "aws" as const,
        account_name: formData.account_name || "Test",
        account_identifier: formData.account_identifier,
        regions: formData.regions.split(",").map((r) => r.trim()).filter(Boolean),
        aws_access_key_id: formData.aws_access_key_id,
        aws_secret_access_key: formData.aws_secret_access_key,
      };

      const result = await accountsAPI.validateCredentials(testData);
      setValidationResult({
        status: 'success',
        message: result.message,
      });
    } catch (error: any) {
      setValidationResult({
        status: 'error',
        message: error.message || 'Validation failed',
      });
    } finally {
      setIsValidating(false);
    }
  };

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

        {/* Validation Result */}
        {validationResult && (
          <div className={`p-4 rounded-xl ${
            validationResult.status === 'success'
              ? 'bg-green-50 border-2 border-green-200'
              : 'bg-red-50 border-2 border-red-200'
          }`}>
            <p className={`text-sm font-medium ${
              validationResult.status === 'success' ? 'text-green-700' : 'text-red-700'
            }`}>
              {validationResult.message}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4">
          {/* Test Connection Button */}
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={isValidating || !isFormValid()}
            className="flex-1 rounded-xl border-2 border-blue-600 bg-white px-6 py-3 font-semibold text-blue-600 hover:bg-blue-50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isValidating ? (
              <>
                <RefreshCw className="h-5 w-5 animate-spin" />
                Testing...
              </>
            ) : (
              <>
                <CheckCircle className="h-5 w-5" />
                Test Connection
              </>
            )}
          </button>

          {/* Add Account Button */}
          <button
            type="submit"
            disabled={isLoading || validationResult?.status !== 'success'}
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
            className="rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-all"
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
  const isAzure = account.provider === "azure";

  const [formData, setFormData] = useState({
    account_name: account.account_name || "",
    // AWS fields
    aws_access_key_id: "",
    aws_secret_access_key: "",
    // Azure fields
    azure_tenant_id: "",
    azure_client_id: "",
    azure_client_secret: "",
    azure_subscription_id: "",
    // Common fields
    regions: account.regions?.join(",") || (isAzure ? "eastus,westeurope,northeurope" : "us-east-1"),
    resource_groups: account.resource_groups?.join(",") || "",
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
        regions: formData.regions.split(",").map((r: string) => r.trim()).filter(Boolean),
        resource_groups: formData.resource_groups.trim() ? formData.resource_groups.split(",").map((rg: string) => rg.trim()).filter(Boolean) : null,
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
      if (isAzure) {
        // Azure credentials - all 4 fields must be provided to update
        if (formData.azure_tenant_id && formData.azure_client_id &&
            formData.azure_client_secret && formData.azure_subscription_id) {
          updateData.azure_tenant_id = formData.azure_tenant_id;
          updateData.azure_client_id = formData.azure_client_id;
          updateData.azure_client_secret = formData.azure_client_secret;
          updateData.azure_subscription_id = formData.azure_subscription_id;
        }
      } else {
        // AWS credentials - both fields must be provided to update
        if (formData.aws_access_key_id && formData.aws_secret_access_key) {
          updateData.aws_access_key_id = formData.aws_access_key_id;
          updateData.aws_secret_access_key = formData.aws_secret_access_key;
        }
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
            Edit {isAzure ? "Azure" : "AWS"} Account
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
              placeholder={isAzure ? "Production Azure" : "Production AWS"}
            />
          </div>

          <div className="rounded-xl bg-blue-50 border border-blue-200 p-4">
            <p className="text-sm text-blue-900">
              <strong>Update Credentials (optional):</strong> Leave empty to keep existing credentials. {isAzure ? "Fill all 4 fields to update." : "Fill both fields to update."}
            </p>
          </div>

          {isAzure ? (
            <>
              {/* Azure Credentials */}
              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  New Azure Tenant ID (optional)
                  <span className="ml-2 text-xs font-normal text-gray-500">(Directory ID)</span>
                </label>
                <input
                  type="text"
                  value={formData.azure_tenant_id}
                  onChange={(e) =>
                    setFormData({ ...formData, azure_tenant_id: e.target.value })
                  }
                  className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  New Azure Client ID (optional)
                  <span className="ml-2 text-xs font-normal text-gray-500">(Application ID)</span>
                </label>
                <input
                  type="text"
                  value={formData.azure_client_id}
                  onChange={(e) =>
                    setFormData({ ...formData, azure_client_id: e.target.value })
                  }
                  className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  New Azure Client Secret (optional)
                </label>
                <input
                  type="password"
                  value={formData.azure_client_secret}
                  onChange={(e) =>
                    setFormData({ ...formData, azure_client_secret: e.target.value })
                  }
                  className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
                  placeholder="Client secret value"
                />
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 mb-2">
                  New Azure Subscription ID (optional)
                  <span className="ml-2 text-xs font-normal text-gray-500">(GUID format)</span>
                </label>
                <input
                  type="text"
                  value={formData.azure_subscription_id}
                  onChange={(e) =>
                    setFormData({ ...formData, azure_subscription_id: e.target.value })
                  }
                  className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                />
              </div>
            </>
          ) : (
            <>
              {/* AWS Credentials */}
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
            </>
          )}

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
              placeholder={isAzure ? "eastus,westeurope,francecentral" : "us-east-1,eu-west-1,eu-central-1"}
            />
            <p className="mt-2 text-xs text-gray-500">
              💡 Tip: Limit to 3 regions for faster scans
            </p>
          </div>

          {/* Resource Groups (Azure only) */}
          {isAzure && (
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-2">
                Resource Groups (comma-separated, optional)
                <span className="ml-2 text-xs font-normal text-gray-500">Leave empty to scan ALL resource groups</span>
              </label>
              <input
                type="text"
                value={formData.resource_groups}
                onChange={(e) =>
                  setFormData({ ...formData, resource_groups: e.target.value })
                }
                className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono"
                placeholder="rg-prod,rg-staging,rg-dev"
              />
              <p className="mt-2 text-xs text-gray-500">
                🎯 Tip: Filter by specific resource groups to scan only what matters
              </p>
            </div>
          )}

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

function AzureCredentialsHelp() {
  const [copiedPolicy, setCopiedPolicy] = useState(false);

  const azureReaderRole = `{
  "properties": {
    "roleName": "Reader",
    "description": "Read-only access to Azure resources",
    "assignableScopes": ["/subscriptions/{subscription-id}"],
    "permissions": [{
      "actions": ["*/read"],
      "notActions": [],
      "dataActions": [],
      "notDataActions": []
    }]
  }
}`;

  const copyPolicy = () => {
    navigator.clipboard.writeText(azureReaderRole);
    setCopiedPolicy(true);
    setTimeout(() => setCopiedPolicy(false), 2000);
  };

  return (
    <div className="mb-6 rounded-xl border-2 border-blue-200 bg-gradient-to-br from-blue-50 to-purple-50 p-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-600 text-white shadow-md">
          <HelpCircle className="h-6 w-6" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-gray-900">How to get your Azure credentials</h3>
          <p className="text-sm text-gray-600 mt-1">Follow these steps to create a Service Principal</p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Step 1 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-white font-bold text-sm flex-shrink-0">
            1
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Go to Azure Portal</h4>
            <p className="text-sm text-gray-600 mt-1">
              Navigate to Azure Active Directory → App registrations → New registration
            </p>
            <a
              href="https://portal.azure.com/#view/Microsoft_AAD_IAM/ActiveDirectoryMenuBlade/~/RegisteredApps"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 font-medium"
            >
              <ExternalLink className="h-4 w-4" />
              Open App Registrations
            </a>
          </div>
        </div>

        {/* Step 2 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-purple-600 text-white font-bold text-sm flex-shrink-0">
            2
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Create Service Principal</h4>
            <p className="text-sm text-gray-600 mt-1">
              Name: <code className="bg-gray-200 px-2 py-0.5 rounded">cloudwaste-scanner</code>
              <br />
              Supported account types: Single tenant
              <br />
              Redirect URI: Leave blank
            </p>
          </div>
        </div>

        {/* Step 3 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-orange-600 text-white font-bold text-sm flex-shrink-0">
            3
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Get Client Secret</h4>
            <p className="text-sm text-gray-600 mt-1">
              In your app → Certificates & secrets → New client secret
              <br />
              Description: CloudWaste Scanner
              <br />
              Expires: 24 months (recommended)
            </p>
            <div className="mt-3 rounded-lg bg-amber-50 border border-amber-200 p-3">
              <p className="text-xs text-amber-800 font-medium">
                ⚠️ Save the Client Secret VALUE immediately - you won't see it again!
              </p>
            </div>
          </div>
        </div>

        {/* Step 4 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-green-600 text-white font-bold text-sm flex-shrink-0">
            4
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Assign Reader Role</h4>
            <p className="text-sm text-gray-600 mt-1">
              Go to Subscriptions → Select your subscription → Access control (IAM) → Add role assignment
            </p>
            <ul className="text-sm text-gray-600 mt-2 space-y-1 list-disc list-inside">
              <li><strong>Role</strong>: Reader (read-only access)</li>
              <li><strong>Assign access to</strong>: User, group, or service principal</li>
              <li><strong>Select</strong>: cloudwaste-scanner</li>
            </ul>
          </div>
        </div>

        {/* Step 5 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-white font-bold text-sm flex-shrink-0">
            5
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Get Credentials</h4>
            <p className="text-sm text-gray-600 mt-1">
              Go to your App registration → Overview page:
            </p>
            <ul className="text-sm text-gray-600 mt-2 space-y-1 list-disc list-inside">
              <li><strong>Application (client) ID</strong>: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</li>
              <li><strong>Directory (tenant) ID</strong>: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</li>
            </ul>
            <p className="text-sm text-gray-600 mt-3">
              <strong>Subscription ID</strong>: Go to Subscriptions → Copy your subscription ID
            </p>
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-lg bg-blue-50 border border-blue-200 p-4">
        <p className="text-sm text-blue-900">
          <strong>🔒 Security:</strong> CloudWaste only uses READ-ONLY permissions (Reader role). We never modify or delete your Azure resources.
        </p>
      </div>
    </div>
  );
}

function AddAzureAccountForm({ onClose }: { onClose: () => void }) {
  const { createAccount, isLoading, error } = useAccountStore();
  const [showHelp, setShowHelp] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    status: 'idle' | 'success' | 'error';
    message: string;
  } | null>(null);
  const [formData, setFormData] = useState({
    account_name: "",
    azure_tenant_id: "",
    azure_client_id: "",
    azure_client_secret: "",
    azure_subscription_id: "",
    regions: "eastus,westeurope,northeurope",
    resource_groups: "",
    description: "",
  });

  const isFormValid = () => {
    return !!(
      formData.account_name &&
      formData.azure_tenant_id &&
      formData.azure_client_id &&
      formData.azure_client_secret &&
      formData.azure_subscription_id
    );
  };

  const handleTestConnection = async () => {
    setIsValidating(true);
    setValidationResult(null);

    try {
      const testData = {
        provider: "azure" as const,
        account_name: formData.account_name || "Test",
        account_identifier: formData.azure_subscription_id,
        regions: formData.regions.split(",").map((r: string) => r.trim()).filter(Boolean),
        azure_tenant_id: formData.azure_tenant_id,
        azure_client_id: formData.azure_client_id,
        azure_client_secret: formData.azure_client_secret,
        azure_subscription_id: formData.azure_subscription_id,
      };

      const result = await accountsAPI.validateCredentials(testData);
      setValidationResult({
        status: 'success',
        message: result.message,
      });
    } catch (error: any) {
      setValidationResult({
        status: 'error',
        message: error.message || 'Validation failed',
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createAccount({
        provider: "azure",
        account_name: formData.account_name,
        account_identifier: formData.azure_subscription_id,
        azure_tenant_id: formData.azure_tenant_id,
        azure_client_id: formData.azure_client_id,
        azure_client_secret: formData.azure_client_secret,
        azure_subscription_id: formData.azure_subscription_id,
        regions: formData.regions.split(",").map((r: string) => r.trim()).filter(Boolean),
        resource_groups: formData.resource_groups.trim() ? formData.resource_groups.split(",").map((rg: string) => rg.trim()).filter(Boolean) : undefined,
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
          Add Azure Account
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
      {showHelp && <AzureCredentialsHelp />}

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
            placeholder="Production Azure"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Azure Subscription ID *
            <span className="ml-2 text-xs font-normal text-gray-500">(GUID format)</span>
          </label>
          <input
            required
            type="text"
            value={formData.azure_subscription_id}
            onChange={(e) =>
              setFormData({ ...formData, azure_subscription_id: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Azure Tenant ID *
            <span className="ml-2 text-xs font-normal text-gray-500">(Directory ID)</span>
          </label>
          <input
            required
            type="text"
            value={formData.azure_tenant_id}
            onChange={(e) =>
              setFormData({ ...formData, azure_tenant_id: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Azure Client ID *
            <span className="ml-2 text-xs font-normal text-gray-500">(Application ID)</span>
          </label>
          <input
            required
            type="text"
            value={formData.azure_client_id}
            onChange={(e) =>
              setFormData({ ...formData, azure_client_id: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Azure Client Secret *
          </label>
          <input
            required
            type="password"
            value={formData.azure_client_secret}
            onChange={(e) =>
              setFormData({
                ...formData,
                azure_client_secret: e.target.value,
              })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono text-sm"
            placeholder="Client secret value from step 3"
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
            placeholder="eastus,westeurope,northeurope"
          />
          <p className="mt-2 text-xs text-gray-500">
            💡 Tip: Common regions - eastus, westeurope, northeurope, westus2
          </p>
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Resource Groups (comma-separated, optional)
            <span className="ml-2 text-xs font-normal text-gray-500">Leave empty to scan ALL resource groups</span>
          </label>
          <input
            type="text"
            value={formData.resource_groups}
            onChange={(e) =>
              setFormData({ ...formData, resource_groups: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all font-mono"
            placeholder="rg-prod,rg-staging,rg-dev"
          />
          <p className="mt-2 text-xs text-gray-500">
            🎯 Tip: Filter by specific resource groups to scan only what matters (e.g., rg-production, rg-dev)
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
            placeholder="Production environment Azure subscription"
          />
        </div>

        {/* Validation Result */}
        {validationResult && (
          <div className={`p-4 rounded-xl ${
            validationResult.status === 'success'
              ? 'bg-green-50 border-2 border-green-200'
              : 'bg-red-50 border-2 border-red-200'
          }`}>
            <p className={`text-sm font-medium ${
              validationResult.status === 'success' ? 'text-green-700' : 'text-red-700'
            }`}>
              {validationResult.message}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4">
          {/* Test Connection Button */}
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={isValidating || !isFormValid()}
            className="flex-1 rounded-xl border-2 border-blue-600 bg-white px-6 py-3 font-semibold text-blue-600 hover:bg-blue-50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isValidating ? (
              <>
                <RefreshCw className="h-5 w-5 animate-spin" />
                Testing...
              </>
            ) : (
              <>
                <CheckCircle className="h-5 w-5" />
                Test Connection
              </>
            )}
          </button>

          {/* Add Account Button */}
          <button
            type="submit"
            disabled={isLoading || validationResult?.status !== 'success'}
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
            className="rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-all"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

// GCP Account Form Component
function AddGCPAccountForm({ onClose }: { onClose: () => void }) {
  const { createAccount, isLoading, error } = useAccountStore();
  const [showHelp, setShowHelp] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    status: 'idle' | 'success' | 'error';
    message: string;
  } | null>(null);
  const [jsonError, setJsonError] = useState<string>("");
  const [formData, setFormData] = useState({
    account_name: "",
    gcp_project_id: "",
    gcp_service_account_json: "",
    regions: "us-central1,us-east1,europe-west1",
    description: "",
  });

  const isFormValid = () => {
    return !!(
      formData.account_name &&
      formData.gcp_project_id &&
      formData.gcp_service_account_json &&
      !jsonError
    );
  };

  const handleJsonChange = (value: string) => {
    setFormData({ ...formData, gcp_service_account_json: value });

    // Validate JSON format
    if (!value.trim()) {
      setJsonError("");
      return;
    }

    try {
      const parsed = JSON.parse(value);

      // Validate it looks like a service account JSON
      if (!parsed.type || parsed.type !== "service_account") {
        setJsonError("⚠️ This doesn't look like a Service Account JSON (missing 'type: service_account')");
      } else if (!parsed.project_id) {
        setJsonError("⚠️ Missing 'project_id' in Service Account JSON");
      } else if (!parsed.private_key) {
        setJsonError("⚠️ Missing 'private_key' in Service Account JSON");
      } else if (!parsed.client_email) {
        setJsonError("⚠️ Missing 'client_email' in Service Account JSON");
      } else {
        setJsonError("");
      }
    } catch (e) {
      setJsonError("❌ Invalid JSON format - please paste valid JSON");
    }
  };

  const handleTestConnection = async () => {
    setIsValidating(true);
    setValidationResult(null);

    try {
      const testData = {
        provider: "gcp" as const,
        account_name: formData.account_name || "Test",
        account_identifier: formData.gcp_project_id,
        regions: formData.regions.split(",").map((r: string) => r.trim()).filter(Boolean),
        gcp_project_id: formData.gcp_project_id,
        gcp_service_account_json: formData.gcp_service_account_json,
      };

      const result = await accountsAPI.validateCredentials(testData);
      setValidationResult({
        status: 'success',
        message: result.message,
      });
    } catch (error: any) {
      setValidationResult({
        status: 'error',
        message: error.message || 'Validation failed',
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createAccount({
        provider: "gcp",
        account_name: formData.account_name,
        account_identifier: formData.gcp_project_id,
        gcp_project_id: formData.gcp_project_id,
        gcp_service_account_json: formData.gcp_service_account_json,
        regions: formData.regions.split(",").map((r: string) => r.trim()).filter(Boolean),
        description: formData.description || undefined,
      });
      onClose();
    } catch (err) {
      // Error handled by store
    }
  };

  return (
    <div className="rounded-2xl border-2 border-red-200 bg-white p-8 shadow-xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold bg-gradient-to-r from-red-600 to-pink-600 bg-clip-text text-transparent">
          Add GCP Account
        </h2>
        <button
          type="button"
          onClick={() => setShowHelp(!showHelp)}
          className="flex items-center gap-2 rounded-lg bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 transition-colors"
        >
          <HelpCircle className="h-4 w-4" />
          {showHelp ? "Hide" : "How to get credentials?"}
          {showHelp ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {/* Help Section */}
      {showHelp && <GCPCredentialsHelp />}

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
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500/20 transition-all"
            placeholder="Production GCP"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            GCP Project ID *
            <span className="ml-2 text-xs font-normal text-gray-500">(e.g., my-project-123456)</span>
          </label>
          <input
            required
            type="text"
            value={formData.gcp_project_id}
            onChange={(e) =>
              setFormData({ ...formData, gcp_project_id: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500/20 transition-all font-mono text-sm"
            placeholder="my-project-123456"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Service Account JSON Key *
            <span className="ml-2 text-xs font-normal text-gray-500">(paste entire JSON file content)</span>
          </label>
          <textarea
            required
            value={formData.gcp_service_account_json}
            onChange={(e) => handleJsonChange(e.target.value)}
            className={`block w-full rounded-xl border-2 px-4 py-3 focus:outline-none focus:ring-2 transition-all font-mono text-xs ${
              jsonError
                ? "border-red-300 focus:border-red-500 focus:ring-red-500/20"
                : "border-gray-300 focus:border-red-500 focus:ring-red-500/20"
            }`}
            rows={8}
            placeholder='{\n  "type": "service_account",\n  "project_id": "my-project-123456",\n  "private_key_id": "...",\n  "private_key": "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n",\n  "client_email": "cloudwaste@my-project.iam.gserviceaccount.com",\n  ...\n}'
          />
          {jsonError && (
            <p className="mt-2 text-sm text-red-600">{jsonError}</p>
          )}
          <p className="mt-2 text-xs text-gray-500">
            🔒 Security: This JSON key will be encrypted before storage
          </p>
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Regions (comma-separated)
          </label>
          <input
            type="text"
            value={formData.regions}
            onChange={(e) =>
              setFormData({ ...formData, regions: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500/20 transition-all font-mono"
            placeholder="us-central1,us-east1,europe-west1"
          />
          <p className="mt-2 text-xs text-gray-500">
            💡 Tip: Common regions - us-central1, us-east1, us-west1, europe-west1, europe-west2, asia-southeast1, asia-northeast1
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
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500/20 transition-all"
            rows={3}
            placeholder="Production environment GCP project"
          />
        </div>

        {/* Validation Result */}
        {validationResult && (
          <div className={`p-4 rounded-xl ${
            validationResult.status === 'success'
              ? 'bg-green-50 border-2 border-green-200'
              : 'bg-red-50 border-2 border-red-200'
          }`}>
            <p className={`text-sm font-medium ${
              validationResult.status === 'success' ? 'text-green-700' : 'text-red-700'
            }`}>
              {validationResult.message}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4">
          {/* Test Connection Button */}
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={isValidating || !isFormValid()}
            className="flex-1 rounded-xl border-2 border-red-600 bg-white px-6 py-3 font-semibold text-red-600 hover:bg-red-50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isValidating ? (
              <>
                <RefreshCw className="h-5 w-5 animate-spin" />
                Testing...
              </>
            ) : (
              <>
                <CheckCircle className="h-5 w-5" />
                Test Connection
              </>
            )}
          </button>

          {/* Add Account Button */}
          <button
            type="submit"
            disabled={isLoading || validationResult?.status !== 'success'}
            className="flex-1 rounded-xl bg-gradient-to-r from-red-600 to-pink-600 px-6 py-3 font-semibold text-white shadow-lg hover:shadow-xl transition-all hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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
            className="rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-all"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}

// GCP Credentials Help Component
function GCPCredentialsHelp() {
  return (
    <div className="rounded-xl bg-red-50 border-2 border-red-200 p-6 space-y-4 mb-6">
      <h3 className="font-bold text-red-900 flex items-center gap-2">
        <Info className="h-5 w-5" />
        How to create a GCP Service Account for CloudWaste
      </h3>

      <div className="space-y-3 text-sm text-red-800">
        <div className="flex gap-3">
          <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white">
            1
          </span>
          <div>
            <p className="font-semibold">Open Google Cloud Console</p>
            <p className="text-red-700 mt-1">
              Go to{" "}
              <a
                href="https://console.cloud.google.com/iam-admin/serviceaccounts"
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-red-900"
              >
                IAM & Admin → Service Accounts
              </a>
            </p>
          </div>
        </div>

        <div className="flex gap-3">
          <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white">
            2
          </span>
          <div>
            <p className="font-semibold">Create Service Account</p>
            <p className="text-red-700 mt-1">
              Click <strong>"+ CREATE SERVICE ACCOUNT"</strong>
            </p>
            <p className="text-red-700 mt-1">
              Name: <code className="bg-red-100 px-1 rounded">CloudWaste-Scanner</code>
            </p>
            <p className="text-red-700 mt-1">
              Description: <code className="bg-red-100 px-1 rounded">Read-only access for CloudWaste waste detection</code>
            </p>
          </div>
        </div>

        <div className="flex gap-3">
          <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white">
            3
          </span>
          <div>
            <p className="font-semibold">Grant Viewer Role (Read-Only)</p>
            <p className="text-red-700 mt-1">
              Role: <code className="bg-red-100 px-1 rounded font-semibold">Viewer</code>
            </p>
            <p className="text-red-700 mt-1 text-xs">
              ⚠️ This role provides read-only access across all GCP resources
            </p>
          </div>
        </div>

        <div className="flex gap-3">
          <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white">
            4
          </span>
          <div>
            <p className="font-semibold">Create JSON Key</p>
            <p className="text-red-700 mt-1">
              Click on the service account → <strong>KEYS</strong> tab → <strong>ADD KEY</strong> → <strong>Create new key</strong>
            </p>
            <p className="text-red-700 mt-1">
              Select <strong>JSON</strong> format → Click <strong>CREATE</strong>
            </p>
            <p className="text-red-700 mt-1">
              A JSON file will download automatically (e.g., <code className="bg-red-100 px-1 rounded text-xs">my-project-123456-abcdef.json</code>)
            </p>
          </div>
        </div>

        <div className="flex gap-3">
          <span className="flex-shrink-0 flex h-6 w-6 items-center justify-center rounded-full bg-red-600 text-xs font-bold text-white">
            5
          </span>
          <div>
            <p className="font-semibold">Copy JSON Content</p>
            <p className="text-red-700 mt-1">
              Open the downloaded JSON file with a text editor
            </p>
            <p className="text-red-700 mt-1">
              Copy the <strong>entire content</strong> and paste it in the "Service Account JSON Key" field above
            </p>
          </div>
        </div>
      </div>

      <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-4">
        <p className="text-xs text-yellow-800 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <span>
            <strong>Security Best Practice:</strong> The Viewer role provides read-only access to all resources in your GCP project.
            CloudWaste will NEVER modify, delete, or create resources. The JSON key will be encrypted before storage.
            You can revoke access anytime by deleting the service account in GCP Console.
          </span>
        </p>
      </div>

      <div className="rounded-lg bg-blue-50 border border-blue-200 p-4">
        <p className="text-xs text-blue-800 flex items-start gap-2">
          <Info className="h-4 w-4 flex-shrink-0 mt-0.5" />
          <span>
            <strong>Required APIs:</strong> Make sure these APIs are enabled in your project: Compute Engine API, Cloud Storage API,
            Cloud SQL Admin API, Cloud Monitoring API. You can enable them at{" "}
            <a
              href="https://console.cloud.google.com/apis/library"
              target="_blank"
              rel="noopener noreferrer"
              className="underline hover:text-blue-900"
            >
              APIs & Services → Library
            </a>
          </span>
        </p>
      </div>
    </div>
  );
}

// Microsoft 365 Credentials Help Component
function Microsoft365CredentialsHelp() {
  return (
    <div className="mb-6 rounded-xl border-2 border-green-200 bg-gradient-to-br from-green-50 to-blue-50 p-6">
      <div className="flex items-start gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-600 text-white shadow-md">
          <HelpCircle className="h-6 w-6" />
        </div>
        <div>
          <h3 className="text-lg font-bold text-gray-900">How to get your Microsoft 365 credentials</h3>
          <p className="text-sm text-gray-600 mt-1">Follow these steps to create an Entra ID App Registration</p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Step 1 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-white font-bold text-sm flex-shrink-0">
            1
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Go to Entra Admin Center</h4>
            <p className="text-sm text-gray-600 mt-1">
              Navigate to Microsoft Entra ID → App registrations → New registration
            </p>
            <a
              href="https://entra.microsoft.com/#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade"
              target="_blank"
              rel="noopener noreferrer"
              className="mt-2 inline-flex items-center gap-1 text-sm text-green-600 hover:text-green-700 font-medium"
            >
              <ExternalLink className="h-4 w-4" />
              Open Entra App Registrations
            </a>
          </div>
        </div>

        {/* Step 2 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-purple-600 text-white font-bold text-sm flex-shrink-0">
            2
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Create App Registration</h4>
            <p className="text-sm text-gray-600 mt-1">
              Name: <code className="bg-gray-200 px-2 py-0.5 rounded">CloudWaste-Scanner</code>
              <br />
              Supported account types: Single tenant
              <br />
              Redirect URI: Leave blank
            </p>
          </div>
        </div>

        {/* Step 3 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-orange-600 text-white font-bold text-sm flex-shrink-0">
            3
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Get Client Secret</h4>
            <p className="text-sm text-gray-600 mt-1">
              In your app → Certificates & secrets → New client secret
              <br />
              Description: CloudWaste Scanner
              <br />
              Expires: 24 months (recommended)
            </p>
            <div className="mt-3 rounded-lg bg-amber-50 border border-amber-200 p-3">
              <p className="text-xs text-amber-800 font-medium">
                ⚠️ Save the Client Secret VALUE immediately - you won't see it again!
              </p>
            </div>
          </div>
        </div>

        {/* Step 4 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-green-600 text-white font-bold text-sm flex-shrink-0">
            4
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Grant API Permissions</h4>
            <p className="text-sm text-gray-600 mt-1">
              In your app → API permissions → Add a permission → Microsoft Graph → Application permissions
            </p>
            <p className="text-sm text-gray-600 mt-2 font-semibold">
              Required permissions (read-only):
            </p>
            <ul className="text-sm text-gray-600 mt-1 space-y-1 list-disc list-inside ml-2">
              <li><code className="bg-gray-100 px-1 rounded text-xs">Sites.Read.All</code> - Read SharePoint sites</li>
              <li><code className="bg-gray-100 px-1 rounded text-xs">Files.Read.All</code> - Read OneDrive files</li>
              <li><code className="bg-gray-100 px-1 rounded text-xs">User.Read.All</code> - Read user information</li>
              <li><code className="bg-gray-100 px-1 rounded text-xs">Reports.Read.All</code> - Read usage reports</li>
            </ul>
            <div className="mt-3 rounded-lg bg-red-50 border border-red-200 p-3">
              <p className="text-xs text-red-800 font-medium">
                ⚠️ Important: After adding permissions, click "Grant admin consent" button!
              </p>
            </div>
          </div>
        </div>

        {/* Step 5 */}
        <div className="flex gap-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-white font-bold text-sm flex-shrink-0">
            5
          </div>
          <div className="flex-1">
            <h4 className="font-semibold text-gray-900">Get Credentials</h4>
            <p className="text-sm text-gray-600 mt-1">
              Go to your App registration → Overview page:
            </p>
            <ul className="text-sm text-gray-600 mt-2 space-y-1 list-disc list-inside">
              <li><strong>Application (client) ID</strong>: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</li>
              <li><strong>Directory (tenant) ID</strong>: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx</li>
              <li><strong>Client Secret</strong>: The value you saved in Step 3</li>
            </ul>
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-lg bg-blue-50 border border-blue-200 p-4">
        <p className="text-sm text-blue-900">
          <strong>🔒 Security:</strong> CloudWaste only uses READ-ONLY permissions. We never modify or delete your Microsoft 365 data.
        </p>
      </div>
    </div>
  );
}

// Microsoft 365 Account Form Component
function AddMicrosoft365AccountForm({ onClose }: { onClose: () => void }) {
  const { createAccount, isLoading, error } = useAccountStore();
  const [showHelp, setShowHelp] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    status: 'idle' | 'success' | 'error';
    message: string;
  } | null>(null);
  const [formData, setFormData] = useState({
    account_name: "",
    microsoft365_tenant_id: "",
    microsoft365_client_id: "",
    microsoft365_client_secret: "",
    description: "",
  });

  const isFormValid = () => {
    return !!(
      formData.account_name &&
      formData.microsoft365_tenant_id &&
      formData.microsoft365_client_id &&
      formData.microsoft365_client_secret
    );
  };

  const handleTestConnection = async () => {
    setIsValidating(true);
    setValidationResult(null);

    try {
      const testData = {
        provider: "microsoft365" as const,
        account_name: formData.account_name || "Test",
        account_identifier: formData.microsoft365_tenant_id,
        microsoft365_tenant_id: formData.microsoft365_tenant_id,
        microsoft365_client_id: formData.microsoft365_client_id,
        microsoft365_client_secret: formData.microsoft365_client_secret,
      };

      const result = await accountsAPI.validateCredentials(testData);
      setValidationResult({
        status: 'success',
        message: result.message,
      });
    } catch (error: any) {
      setValidationResult({
        status: 'error',
        message: error.message || 'Validation failed',
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createAccount({
        provider: "microsoft365",
        account_name: formData.account_name,
        account_identifier: formData.microsoft365_tenant_id,
        microsoft365_tenant_id: formData.microsoft365_tenant_id,
        microsoft365_client_id: formData.microsoft365_client_id,
        microsoft365_client_secret: formData.microsoft365_client_secret,
        description: formData.description || undefined,
      });
      onClose();
    } catch (err) {
      // Error handled by store
    }
  };

  return (
    <div className="rounded-2xl border-2 border-green-200 bg-white p-8 shadow-xl">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold bg-gradient-to-r from-green-600 to-blue-600 bg-clip-text text-transparent">
          Add Microsoft 365 Account
        </h2>
        <button
          type="button"
          onClick={() => setShowHelp(!showHelp)}
          className="flex items-center gap-2 rounded-lg bg-green-50 px-4 py-2 text-sm font-medium text-green-700 hover:bg-green-100 transition-colors"
        >
          <HelpCircle className="h-4 w-4" />
          {showHelp ? "Hide" : "How to get credentials?"}
          {showHelp ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </button>
      </div>

      {/* Help Section */}
      {showHelp && <Microsoft365CredentialsHelp />}

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
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-green-500 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all"
            placeholder="Production Microsoft 365"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Tenant ID *
            <span className="ml-2 text-xs font-normal text-gray-500">(Directory ID)</span>
          </label>
          <input
            required
            type="text"
            value={formData.microsoft365_tenant_id}
            onChange={(e) =>
              setFormData({ ...formData, microsoft365_tenant_id: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-green-500 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all font-mono text-sm"
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Client ID *
            <span className="ml-2 text-xs font-normal text-gray-500">(Application ID)</span>
          </label>
          <input
            required
            type="text"
            value={formData.microsoft365_client_id}
            onChange={(e) =>
              setFormData({ ...formData, microsoft365_client_id: e.target.value })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-green-500 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all font-mono text-sm"
            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
          />
        </div>

        <div>
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Client Secret *
          </label>
          <input
            required
            type="password"
            value={formData.microsoft365_client_secret}
            onChange={(e) =>
              setFormData({
                ...formData,
                microsoft365_client_secret: e.target.value,
              })
            }
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-green-500 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all font-mono text-sm"
            placeholder="Client secret value from step 3"
          />
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
            className="block w-full rounded-xl border-2 border-gray-300 px-4 py-3 focus:border-green-500 focus:outline-none focus:ring-2 focus:ring-green-500/20 transition-all"
            rows={3}
            placeholder="Production Microsoft 365 tenant for SharePoint and OneDrive scanning"
          />
        </div>

        {/* Validation Result */}
        {validationResult && (
          <div className={`p-4 rounded-xl ${
            validationResult.status === 'success'
              ? 'bg-green-50 border-2 border-green-200'
              : 'bg-red-50 border-2 border-red-200'
          }`}>
            <p className={`text-sm font-medium ${
              validationResult.status === 'success' ? 'text-green-700' : 'text-red-700'
            }`}>
              {validationResult.message}
            </p>
          </div>
        )}

        {/* Action Buttons */}
        <div className="flex gap-3 pt-4">
          {/* Test Connection Button */}
          <button
            type="button"
            onClick={handleTestConnection}
            disabled={isValidating || !isFormValid()}
            className="flex-1 rounded-xl border-2 border-green-600 bg-white px-6 py-3 font-semibold text-green-600 hover:bg-green-50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isValidating ? (
              <>
                <RefreshCw className="h-5 w-5 animate-spin" />
                Testing...
              </>
            ) : (
              <>
                <CheckCircle className="h-5 w-5" />
                Test Connection
              </>
            )}
          </button>

          {/* Add Account Button */}
          <button
            type="submit"
            disabled={isLoading || validationResult?.status !== 'success'}
            className="flex-1 rounded-xl bg-gradient-to-r from-green-600 to-blue-600 px-6 py-3 font-semibold text-white shadow-lg hover:shadow-xl transition-all hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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
            className="rounded-xl border-2 border-gray-300 bg-white px-6 py-3 font-semibold text-gray-700 hover:bg-gray-50 transition-all"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
