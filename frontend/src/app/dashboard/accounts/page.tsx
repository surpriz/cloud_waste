"use client";

import { useEffect, useState } from "react";
import { useAccountStore } from "@/stores/useAccountStore";
import { Plus, Trash2, RefreshCw, CheckCircle, XCircle } from "lucide-react";

export default function AccountsPage() {
  const { accounts, fetchAccounts, deleteAccount, isLoading } = useAccountStore();
  const [showAddForm, setShowAddForm] = useState(false);

  useEffect(() => {
    fetchAccounts();
  }, [fetchAccounts]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Cloud Accounts</h1>
          <p className="mt-2 text-gray-600">
            Manage your cloud provider accounts for resource scanning
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white transition-colors hover:bg-blue-700"
        >
          <Plus className="h-5 w-5" />
          Add Account
        </button>
      </div>

      {/* Add Account Form */}
      {showAddForm && <AddAccountForm onClose={() => setShowAddForm(false)} />}

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
              onDelete={() => deleteAccount(account.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AccountCard({ account, onDelete }: any) {
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
        <button
          onClick={onDelete}
          className="rounded-lg p-2 text-gray-400 transition-colors hover:bg-red-50 hover:text-red-600"
        >
          <Trash2 className="h-5 w-5" />
        </button>
      </div>
    </div>
  );
}

function AddAccountForm({ onClose }: { onClose: () => void }) {
  const { createAccount, isLoading, error } = useAccountStore();
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
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold text-gray-900">Add AWS Account</h2>
      <form onSubmit={handleSubmit} className="mt-4 space-y-4">
        {error && (
          <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
            {error}
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700">
            Account Name *
          </label>
          <input
            required
            type="text"
            value={formData.account_name}
            onChange={(e) =>
              setFormData({ ...formData, account_name: e.target.value })
            }
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2"
            placeholder="Production AWS"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            AWS Account ID *
          </label>
          <input
            required
            type="text"
            value={formData.account_identifier}
            onChange={(e) =>
              setFormData({ ...formData, account_identifier: e.target.value })
            }
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2"
            placeholder="123456789012"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            AWS Access Key ID *
          </label>
          <input
            required
            type="text"
            value={formData.aws_access_key_id}
            onChange={(e) =>
              setFormData({ ...formData, aws_access_key_id: e.target.value })
            }
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2"
            placeholder="AKIAIOSFODNN7EXAMPLE"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
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
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2"
            placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            Regions (comma-separated, max 3)
          </label>
          <input
            type="text"
            value={formData.regions}
            onChange={(e) =>
              setFormData({ ...formData, regions: e.target.value })
            }
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2"
            placeholder="us-east-1,eu-west-1"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">
            Description
          </label>
          <textarea
            value={formData.description}
            onChange={(e) =>
              setFormData({ ...formData, description: e.target.value })
            }
            className="mt-1 block w-full rounded-lg border border-gray-300 px-3 py-2"
            rows={3}
            placeholder="Production environment AWS account"
          />
        </div>

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={isLoading}
            className="flex-1 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:bg-blue-300"
          >
            {isLoading ? "Adding..." : "Add Account"}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex-1 rounded-lg border border-gray-300 px-4 py-2 font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
