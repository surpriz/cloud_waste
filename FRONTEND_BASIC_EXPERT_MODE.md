# Guide d'Implémentation : Mode Basic/Expert (Frontend)

## ✅ Backend Terminé

Le backend est prêt avec :
- ✅ Endpoint GET `/api/v1/detection-rules/grouped` (règles groupées par famille)
- ✅ Endpoint POST `/api/v1/detection-rules/grouped/bulk-update` (sauvegarde bulk)
- ✅ Mappings RESOURCE_FAMILIES (40 types AWS → 4 familles)

**Commits:**
- `365272d` - Granularité AWS uniformisée
- `dcfa2c6` - Backend Basic/Expert mode

---

## 🎯 Objectif Frontend

Ajouter 2 modes de vue dans `frontend/src/app/(dashboard)/dashboard/settings/page.tsx`:
- **Mode Basic** (défaut) : Afficher ~20-30 familles de ressources (groupées)
- **Mode Expert** : Afficher 119 resource_types individuels (actuel)

---

## 📋 Étape 1 : Mettre à Jour les Labels AWS

**Fichier:** `frontend/src/app/(dashboard)/dashboard/settings/page.tsx`

**Action:** Remplacer les anciens labels AWS par les nouveaux (40 types granulaires)

### Ancien Code (à remplacer)
```typescript
const AWS_RESOURCE_LABELS: { [key: string]: string } = {
  ebs_volume: "EBS Volumes",
  elastic_ip: "Elastic IPs",
  ebs_snapshot: "EBS Snapshots",
  ec2_instance: "EC2 Instances (Stopped)",
  // ...
};
```

### Nouveau Code (copier-coller)
```typescript
const AWS_RESOURCE_LABELS: { [key: string]: string } = {
  // EBS Volumes (10 granular types)
  ebs_volume_unattached: "EBS Volume - Unattached",
  ebs_volume_on_stopped_instance: "EBS Volume - On Stopped Instance",
  ebs_volume_gp2_migration: "EBS Volume - GP2 Migration Opportunity",
  ebs_volume_unnecessary_io2: "EBS Volume - Unnecessary IO2",
  ebs_volume_overprovisioned_iops: "EBS Volume - Overprovisioned IOPS",
  ebs_volume_overprovisioned_throughput: "EBS Volume - Overprovisioned Throughput",
  ebs_volume_idle: "EBS Volume - Idle",
  ebs_volume_low_iops_usage: "EBS Volume - Low IOPS Usage",
  ebs_volume_low_throughput_usage: "EBS Volume - Low Throughput Usage",
  ebs_volume_type_downgrade: "EBS Volume - Type Downgrade Opportunity",

  // Elastic IPs (10 granular types)
  elastic_ip_unassociated: "Elastic IP - Unassociated",
  elastic_ip_on_stopped_instance: "Elastic IP - On Stopped Instance",
  elastic_ip_multiple_per_instance: "Elastic IP - Multiple Per Instance",
  elastic_ip_on_detached_eni: "Elastic IP - On Detached ENI",
  elastic_ip_never_used: "Elastic IP - Never Used",
  elastic_ip_on_unused_nat_gateway: "Elastic IP - On Unused NAT Gateway",
  elastic_ip_idle: "Elastic IP - Idle",
  elastic_ip_low_traffic: "Elastic IP - Low Traffic",
  elastic_ip_unused_nat_gateway: "Elastic IP - Unused NAT Gateway",
  elastic_ip_on_failed_instance: "Elastic IP - On Failed Instance",

  // EBS Snapshots (10 granular types)
  ebs_snapshot_orphaned: "EBS Snapshot - Orphaned",
  ebs_snapshot_redundant: "EBS Snapshot - Redundant",
  ebs_snapshot_unused_ami: "EBS Snapshot - Unused AMI",
  ebs_snapshot_old_unused: "EBS Snapshot - Old Unused",
  ebs_snapshot_from_deleted_instance: "EBS Snapshot - From Deleted Instance",
  ebs_snapshot_incomplete_failed: "EBS Snapshot - Incomplete/Failed",
  ebs_snapshot_untagged: "EBS Snapshot - Untagged",
  ebs_snapshot_excessive_retention: "EBS Snapshot - Excessive Retention",
  ebs_snapshot_duplicate: "EBS Snapshot - Duplicate",
  ebs_snapshot_never_restored: "EBS Snapshot - Never Restored",

  // EC2 Instances (10 granular types)
  ec2_instance_stopped: "EC2 Instance - Stopped",
  ec2_instance_idle_running: "EC2 Instance - Idle Running",
  ec2_instance_oversized: "EC2 Instance - Oversized",
  ec2_instance_old_generation: "EC2 Instance - Old Generation",
  ec2_instance_burstable_credit_waste: "EC2 Instance - Burstable Credit Waste",
  ec2_instance_dev_test_24_7: "EC2 Instance - Dev/Test 24/7",
  ec2_instance_untagged: "EC2 Instance - Untagged",
  ec2_instance_right_sizing_opportunity: "EC2 Instance - Right Sizing Opportunity",
  ec2_instance_spot_eligible: "EC2 Instance - Spot Eligible",
  ec2_instance_scheduled_unused: "EC2 Instance - Scheduled Unused",

  // Other AWS resources (keep existing)
  load_balancer: "Load Balancers",
  rds_instance: "RDS Instances",
  // ... rest of existing labels
};
```

### Mettre à Jour les Icônes aussi
```typescript
const AWS_RESOURCE_ICONS: { [key: string]: any } = {
  // EBS Volumes → HardDrive
  ebs_volume_unattached: HardDrive,
  ebs_volume_on_stopped_instance: HardDrive,
  ebs_volume_gp2_migration: HardDrive,
  ebs_volume_unnecessary_io2: HardDrive,
  ebs_volume_overprovisioned_iops: HardDrive,
  ebs_volume_overprovisioned_throughput: HardDrive,
  ebs_volume_idle: HardDrive,
  ebs_volume_low_iops_usage: HardDrive,
  ebs_volume_low_throughput_usage: HardDrive,
  ebs_volume_type_downgrade: HardDrive,

  // Elastic IPs → Globe
  elastic_ip_unassociated: Globe,
  elastic_ip_on_stopped_instance: Globe,
  elastic_ip_multiple_per_instance: Globe,
  elastic_ip_on_detached_eni: Globe,
  elastic_ip_never_used: Globe,
  elastic_ip_on_unused_nat_gateway: Globe,
  elastic_ip_idle: Globe,
  elastic_ip_low_traffic: Globe,
  elastic_ip_unused_nat_gateway: Globe,
  elastic_ip_on_failed_instance: Globe,

  // EBS Snapshots → Camera
  ebs_snapshot_orphaned: Camera,
  ebs_snapshot_redundant: Camera,
  ebs_snapshot_unused_ami: Camera,
  ebs_snapshot_old_unused: Camera,
  ebs_snapshot_from_deleted_instance: Camera,
  ebs_snapshot_incomplete_failed: Camera,
  ebs_snapshot_untagged: Camera,
  ebs_snapshot_excessive_retention: Camera,
  ebs_snapshot_duplicate: Camera,
  ebs_snapshot_never_restored: Camera,

  // EC2 Instances → Server
  ec2_instance_stopped: Server,
  ec2_instance_idle_running: Server,
  ec2_instance_oversized: Server,
  ec2_instance_old_generation: Server,
  ec2_instance_burstable_credit_waste: Server,
  ec2_instance_dev_test_24_7: Server,
  ec2_instance_untagged: Server,
  ec2_instance_right_sizing_opportunity: Server,
  ec2_instance_spot_eligible: Server,
  ec2_instance_scheduled_unused: Server,

  // Other AWS resources (keep existing)
  load_balancer: Zap,
  rds_instance: Database,
  // ... rest of existing icons
};
```

---

## 📋 Étape 2 : Ajouter le Toggle Basic/Expert

**Fichier:** `frontend/src/app/(dashboard)/dashboard/settings/page.tsx`

**Localisation:** Après la section des filtres (provider, category, search), avant l'affichage des règles

### Code à Ajouter

```typescript
// Dans le composant SettingsPage, ajouter le state:
const [viewMode, setViewMode] = useState<"basic" | "expert">("basic");

// Optionnel: Persister la préférence utilisateur
useEffect(() => {
  const savedMode = localStorage.getItem("detectionRulesViewMode");
  if (savedMode === "basic" || savedMode === "expert") {
    setViewMode(savedMode);
  }
}, []);

const handleViewModeChange = (mode: "basic" | "expert") => {
  setViewMode(mode);
  localStorage.setItem("detectionRulesViewMode", mode);
};

// Dans le JSX, après les filtres provider/category/search:
```

```tsx
{/* Basic/Expert Mode Toggle */}
<div className="mb-4">
  <div className="flex items-center justify-between bg-white rounded-xl p-4 border-2 border-gray-200 shadow-sm">
    <div>
      <h3 className="text-sm font-semibold text-gray-700 mb-1">Configuration Mode</h3>
      <p className="text-xs text-gray-500">
        {viewMode === "basic"
          ? "📦 Grouped view - Configure resource families with common settings"
          : "🔧 Advanced view - Configure each scenario individually"}
      </p>
    </div>
    <div className="flex items-center gap-2">
      <button
        onClick={() => handleViewModeChange("basic")}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm transition-all ${
          viewMode === "basic"
            ? "bg-blue-600 text-white shadow-md"
            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
        }`}
      >
        <Package className="h-4 w-4" />
        Basic
      </button>
      <button
        onClick={() => handleViewModeChange("expert")}
        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-semibold text-sm transition-all ${
          viewMode === "expert"
            ? "bg-purple-600 text-white shadow-md"
            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
        }`}
      >
        <Sliders className="h-4 w-4" />
        Expert
      </button>
    </div>
  </div>
</div>
```

---

## 📋 Étape 3 : Affichage Conditionnel

**Remplacer le rendu des règles existant par:**

```tsx
{viewMode === "basic" ? (
  <BasicModeView
    detectionRules={detectionRules}
    filters={{selectedProvider, selectedCategory, searchQuery}}
  />
) : (
  <ExpertModeView
    detectionRules={detectionRules}
    filters={{selectedProvider, selectedCategory, searchQuery}}
  />
)}
```

---

## 📋 Étape 4 : Créer BasicModeView Component

**Nouveau Fichier:** `frontend/src/components/detection/BasicModeView.tsx`

```tsx
"use client";

import { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, Save, Settings } from "lucide-react";

interface GroupedRule {
  resource_family: string;
  label: string;
  scenarios: Array<{
    resource_type: string;
    description: string;
    enabled: boolean;
    is_customized: boolean;
  }>;
  scenario_count: number;
  enabled_count: number;
  total_count: number;
  common_params: {
    enabled?: boolean;
    min_age_days?: number;
    confidence_threshold_days?: number;
    [key: string]: any;
  };
  enabled: boolean;
  is_customized: boolean;
}

interface BasicModeViewProps {
  detectionRules: any[];
  filters: {
    selectedProvider: string;
    selectedCategory: string;
    searchQuery: string;
  };
}

export function BasicModeView({ detectionRules, filters }: BasicModeViewProps) {
  const [groupedRules, setGroupedRules] = useState<GroupedRule[]>([]);
  const [expandedFamilies, setExpandedFamilies] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchGroupedRules();
  }, []);

  const fetchGroupedRules = async () => {
    try {
      const response = await fetch("/api/v1/detection-rules/grouped", {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
      });
      const data = await response.json();
      setGroupedRules(data);
    } catch (error) {
      console.error("Failed to fetch grouped rules:", error);
    } finally {
      setLoading(false);
    }
  };

  const handleBulkUpdate = async (family: string, rules: any) => {
    try {
      await fetch(`/api/v1/detection-rules/grouped/bulk-update?family=${family}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${localStorage.getItem("token")}`,
        },
        body: JSON.stringify(rules),
      });
      // Refresh
      fetchGroupedRules();
    } catch (error) {
      console.error("Failed to update family rules:", error);
    }
  };

  const toggleExpand = (family: string) => {
    setExpandedFamilies((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(family)) {
        newSet.delete(family);
      } else {
        newSet.add(family);
      }
      return newSet;
    });
  };

  if (loading) {
    return <div className="text-center py-8">Loading grouped rules...</div>;
  }

  // Apply filters
  const filteredGroups = groupedRules.filter((group) => {
    // Filter logic here (similar to ExpertModeView)
    return true; // Simplified
  });

  return (
    <div className="space-y-4">
      {filteredGroups.map((group) => (
        <div
          key={group.resource_family}
          className={`rounded-2xl bg-white p-6 shadow-lg border-2 transition-all ${
            group.is_customized ? "border-orange-300 bg-orange-50/30" : "border-gray-200"
          }`}
        >
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <div className="flex items-center gap-3">
                <h3 className="text-xl font-bold text-gray-900">{group.label}</h3>
                <span className="text-sm bg-blue-100 text-blue-800 px-3 py-1 rounded-full font-semibold">
                  {group.enabled_count}/{group.scenario_count} enabled
                </span>
                {group.is_customized && (
                  <span className="text-xs bg-purple-200 text-purple-800 px-2 py-1 rounded-full font-semibold">
                    CUSTOM
                  </span>
                )}
              </div>
              <p className="text-sm text-gray-600 mt-1">
                {group.scenario_count} detection scenario{group.scenario_count > 1 ? "s" : ""}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => handleBulkUpdate(group.resource_family, group.common_params)}
                className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700"
              >
                <Save className="h-4 w-4" />
                Save
              </button>
              <button
                onClick={() => toggleExpand(group.resource_family)}
                className="flex items-center gap-2 rounded-lg border-2 border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-100"
              >
                {expandedFamilies.has(group.resource_family) ? (
                  <>
                    <ChevronUp className="h-4 w-4" />
                    <span className="sr-only">Collapse</span>
                  </>
                ) : (
                  <>
                    <ChevronDown className="h-4 w-4" />
                    <span className="sr-only">Expand</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Common Parameters */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div className="flex items-center justify-between bg-gray-50 p-3 rounded-lg">
              <span className="text-sm font-semibold text-gray-700">Detection Enabled</span>
              <label className="relative inline-flex cursor-pointer items-center">
                <input
                  type="checkbox"
                  checked={group.common_params.enabled ?? true}
                  onChange={(e) => {
                    // Update common params
                    handleBulkUpdate(group.resource_family, {
                      ...group.common_params,
                      enabled: e.target.checked,
                    });
                  }}
                  className="peer sr-only"
                />
                <div className="peer h-6 w-11 rounded-full bg-gray-300 after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:bg-white after:transition-all peer-checked:bg-blue-600 peer-checked:after:translate-x-full" />
              </label>
            </div>

            {group.common_params.min_age_days !== undefined && (
              <div className="bg-gray-50 p-3 rounded-lg">
                <label className="block text-sm font-semibold text-gray-700 mb-1">
                  Minimum Age (days)
                </label>
                <input
                  type="number"
                  value={group.common_params.min_age_days}
                  onChange={(e) => {
                    // Update common params (without saving, user clicks Save button)
                    setGroupedRules((prev) =>
                      prev.map((g) =>
                        g.resource_family === group.resource_family
                          ? {
                              ...g,
                              common_params: {
                                ...g.common_params,
                                min_age_days: parseInt(e.target.value),
                              },
                            }
                          : g
                      )
                    );
                  }}
                  className="w-full rounded-lg border-2 border-gray-300 px-3 py-2 text-sm"
                />
              </div>
            )}
          </div>

          {/* Expanded Scenarios List */}
          {expandedFamilies.has(group.resource_family) && (
            <div className="mt-4 border-t-2 border-gray-200 pt-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <Settings className="h-4 w-4" />
                Individual Scenarios
              </h4>
              <div className="space-y-2">
                {group.scenarios.map((scenario) => (
                  <div
                    key={scenario.resource_type}
                    className="flex items-start justify-between bg-gray-50 p-3 rounded-lg"
                  >
                    <div className="flex-1">
                      <p className="text-sm font-medium text-gray-900">{scenario.resource_type}</p>
                      <p className="text-xs text-gray-600 mt-1">{scenario.description}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs px-2 py-1 rounded-full font-semibold ${
                          scenario.enabled
                            ? "bg-green-100 text-green-800"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {scenario.enabled ? "✓ Enabled" : "✗ Disabled"}
                      </span>
                      {scenario.is_customized && (
                        <span className="text-xs bg-purple-100 text-purple-800 px-2 py-1 rounded-full">
                          Custom
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
```

---

## 📋 Étape 5 : Créer ExpertModeView Component

**Nouveau Fichier:** `frontend/src/components/detection/ExpertModeView.tsx`

**Action:** Copier le code de rendu existant de `page.tsx` (le `filteredRules.map(...)`) dans ce composant

```tsx
"use client";

interface ExpertModeViewProps {
  detectionRules: any[];
  filters: {
    selectedProvider: string;
    selectedCategory: string;
    searchQuery: string;
  };
}

export function ExpertModeView({ detectionRules, filters }: ExpertModeViewProps) {
  // Copier la logique de filtrage existante de page.tsx
  const filteredRules = detectionRules.filter((rule) => {
    // ... logique de filtrage existante
    return true;
  });

  return (
    <>
      {/* Resource Counter */}
      {/* ... copier le code existant ... */}

      {filteredRules.map((rule) => (
        <div key={rule.resource_type} className="...">
          {/* ... copier le code de rendu existant ... */}
        </div>
      ))}
    </>
  );
}
```

---

## 📋 Étape 6 : Tester

1. **Démarrer l'application**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Aller sur** http://localhost:3000/dashboard/settings

3. **Vérifier:**
   - ✅ Mode Basic affiche ~20-30 familles groupées
   - ✅ Mode Expert affiche 119 lignes individuelles
   - ✅ Le toggle Basic/Expert fonctionne
   - ✅ Sauvegarde en mode Basic met à jour tous les scénarios de la famille
   - ✅ Expand/Collapse affiche les scénarios individuels en mode Basic

---

## ✅ Checklist de Complétion

- [ ] Labels AWS mis à jour (40 nouveaux types)
- [ ] Icônes AWS mises à jour
- [ ] Toggle Basic/Expert ajouté
- [ ] BasicModeView créé et fonctionnel
- [ ] ExpertModeView créé et fonctionnel
- [ ] Persistance localStorage du mode
- [ ] Test sauvegarde mode Basic
- [ ] Test affichage 119 ressources mode Expert
- [ ] Commit frontend

---

## 🚀 Résultat Attendu

**Mode Basic:**
- AWS: 4 familles (EBS Volumes, Elastic IPs, Snapshots, EC2)
- Azure: ~10-15 familles logiques
- GCP: ~10-15 familles logiques
- **Total: ~30 lignes configurables**

**Mode Expert:**
- AWS: 119 resource_types individuels
- Azure: Tous les types individuels
- GCP: Tous les types individuels
- **Total: 119+ lignes configurables**

**UX Améliorée:**
- Mode Basic = configuration rapide et simple
- Mode Expert = contrôle granulaire avancé
- Préférence persistée en localStorage
