"use client";

import { useState } from "react";
import {
  BookOpen,
  Cloud,
  Shield,
  Zap,
  Target,
  TrendingDown,
  CheckCircle,
  AlertTriangle,
  HelpCircle,
  Eye,
  EyeOff,
  Trash2,
  Settings,
  ArrowLeft,
} from "lucide-react";
import Link from "next/link";

export default function DocsPage() {
  const [activeSection, setActiveSection] = useState<string>("introduction");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const sections = [
    { id: "introduction", label: "Introduction", icon: BookOpen },
    { id: "getting-started", label: "Getting Started", icon: Zap },
    { id: "detection-strategy", label: "Detection Strategy", icon: Target },
    { id: "supported-resources", label: "Supported Resources", icon: Cloud },
    { id: "detection-rules", label: "Detection Rules", icon: Settings },
    { id: "understanding-results", label: "Understanding Results", icon: Eye },
    { id: "faq", label: "FAQ", icon: HelpCircle },
  ];

  const handleSectionChange = (sectionId: string) => {
    setActiveSection(sectionId);
    setIsSidebarOpen(false); // Close sidebar on mobile after selection
  };

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Sidebar - Desktop */}
      <div className="hidden lg:block w-64 border-r bg-white p-6">
        <Link
          href="/dashboard"
          className="mb-6 inline-flex items-center gap-2 rounded-lg bg-gray-100 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Dashboard
        </Link>
        <h2 className="mb-6 text-xl font-bold text-gray-900">Documentation</h2>
        <nav className="space-y-2">
          {sections.map((section) => {
            const Icon = section.icon;
            return (
              <button
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                  activeSection === section.id
                    ? "bg-blue-50 text-blue-700 font-semibold"
                    : "text-gray-600 hover:bg-gray-50"
                }`}
              >
                <Icon className="h-5 w-5" />
                {section.label}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Mobile Sidebar Overlay */}
      {isSidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setIsSidebarOpen(false)}
          />
          {/* Sidebar */}
          <div className="fixed inset-y-0 left-0 w-64 bg-white shadow-xl p-6">
            <button
              onClick={() => setIsSidebarOpen(false)}
              className="mb-6 flex items-center gap-2 text-gray-600 hover:text-gray-900"
            >
              <ArrowLeft className="h-4 w-4" />
              Close
            </button>
            <h2 className="mb-6 text-xl font-bold text-gray-900">Documentation</h2>
            <nav className="space-y-2">
              {sections.map((section) => {
                const Icon = section.icon;
                return (
                  <button
                    key={section.id}
                    onClick={() => handleSectionChange(section.id)}
                    className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                      activeSection === section.id
                        ? "bg-blue-50 text-blue-700 font-semibold"
                        : "text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    <Icon className="h-5 w-5" />
                    {section.label}
                  </button>
                );
              })}
            </nav>
          </div>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8">
        {/* Mobile Header */}
        <div className="lg:hidden mb-6 flex items-center justify-between">
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 transition-colors border border-gray-200"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </Link>
          <button
            onClick={() => setIsSidebarOpen(true)}
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
          >
            <BookOpen className="h-4 w-4" />
            Menu
          </button>
        </div>
        <div className="mx-auto max-w-4xl">
          {activeSection === "introduction" && <IntroductionSection />}
          {activeSection === "getting-started" && <GettingStartedSection />}
          {activeSection === "detection-strategy" && <DetectionStrategySection />}
          {activeSection === "supported-resources" && <SupportedResourcesSection />}
          {activeSection === "detection-rules" && <DetectionRulesSection />}
          {activeSection === "understanding-results" && <UnderstandingResultsSection />}
          {activeSection === "faq" && <FAQSection />}
        </div>
      </div>
    </div>
  );
}

function IntroductionSection() {
  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold text-gray-900">Welcome to CloudWaste</h1>
      <p className="text-xl text-gray-600">
        Automatically detect and eliminate wasted cloud spending on orphaned AWS resources
      </p>

      <div className="grid gap-6 md:grid-cols-3">
        <FeatureCard
          icon={TrendingDown}
          title="Save Money"
          description="Identify resources costing you money every month without providing value"
        />
        <FeatureCard
          icon={Shield}
          title="Intelligent Detection"
          description="Uses CloudWatch metrics to detect truly abandoned resources, not just unattached ones"
        />
        <FeatureCard
          icon={Zap}
          title="Actionable Insights"
          description="Clear explanations and confidence levels help you make informed decisions"
        />
      </div>

      <div className="rounded-lg bg-blue-50 border border-blue-200 p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-2">What is CloudWaste?</h3>
        <p className="text-blue-800">
          CloudWaste is a SaaS platform that helps businesses reduce cloud costs by automatically
          detecting <strong>orphaned and unused resources</strong> in their AWS infrastructure.
          Unlike simple monitoring tools, CloudWaste uses intelligent detection with CloudWatch
          metrics to identify resources that are truly wasted, not just temporarily idle.
        </p>
      </div>

      <div className="space-y-4">
        <h3 className="text-2xl font-bold text-gray-900">How It Works</h3>
        <ol className="list-decimal list-inside space-y-3 text-gray-700">
          <li><strong>Connect your AWS account</strong> with read-only IAM credentials</li>
          <li><strong>Run automated scans</strong> across all your regions</li>
          <li><strong>Review detected resources</strong> with detailed explanations and confidence levels</li>
          <li><strong>Take action</strong> by deleting truly orphaned resources directly in AWS</li>
        </ol>
      </div>

      <div className="rounded-lg bg-green-50 border border-green-200 p-6">
        <h3 className="text-lg font-semibold text-green-900 mb-2">🔒 Security First</h3>
        <p className="text-green-800">
          CloudWaste uses <strong>read-only AWS permissions</strong>. We NEVER delete, modify,
          or write to your AWS resources. All credentials are encrypted in our database. You
          maintain full control and delete resources manually in your AWS console.
        </p>
      </div>
    </div>
  );
}

function GettingStartedSection() {
  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold text-gray-900">Getting Started</h1>

      <div className="space-y-8">
        <StepCard
          number={1}
          title="Connect Your AWS Account"
          description="Add your AWS account with read-only IAM credentials"
        >
          <div className="space-y-3 text-sm text-gray-700">
            <p><strong>Required IAM Permissions:</strong></p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>ec2:Describe*</li>
              <li>rds:Describe*</li>
              <li>s3:List*, s3:Get*</li>
              <li>elasticloadbalancing:Describe*</li>
              <li>cloudwatch:GetMetricStatistics</li>
              <li>cloudwatch:ListMetrics</li>
              <li>sts:GetCallerIdentity</li>
            </ul>
            <p className="mt-3 text-blue-600">
              💡 <strong>Tip:</strong> Use AWS IAM to create a dedicated user with these permissions
              and generate access keys for CloudWaste.
            </p>
          </div>
        </StepCard>

        <StepCard
          number={2}
          title="Run Your First Scan"
          description="Trigger a manual scan or wait for the automated daily scan"
        >
          <div className="space-y-3 text-sm text-gray-700">
            <p>Go to <strong>Scans</strong> page and click <strong>"Start New Scan"</strong></p>
            <p>CloudWaste will:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li>Scan all enabled AWS regions</li>
              <li>Check CloudWatch metrics for resource usage history</li>
              <li>Identify orphaned resources with confidence levels</li>
              <li>Calculate current and cumulative waste costs</li>
            </ul>
            <p className="mt-3 text-gray-600">
              ⏱️ Scans typically complete in 1-5 minutes depending on the number of resources.
            </p>
          </div>
        </StepCard>

        <StepCard
          number={3}
          title="Review Detected Resources"
          description="Analyze orphaned resources with detailed insights"
        >
          <div className="space-y-3 text-sm text-gray-700">
            <p>Each detected resource shows:</p>
            <ul className="list-disc list-inside space-y-1 ml-4">
              <li><strong>🔍 Reason:</strong> Why this resource is considered orphaned</li>
              <li><strong>Confidence Badge:</strong> High (red), Medium (orange), or Low (yellow)</li>
              <li><strong>Future Waste:</strong> Monthly cost if resource stays orphaned</li>
              <li><strong>Already Wasted:</strong> Total money lost since creation</li>
            </ul>
          </div>
        </StepCard>

        <StepCard
          number={4}
          title="Take Action"
          description="Decide what to do with each resource"
        >
          <div className="space-y-3 text-sm text-gray-700">
            <p>For each resource, you can:</p>
            <div className="space-y-2 mt-3">
              <ActionButton icon={Eye} label="View Details" description="See full metadata and usage history" />
              <ActionButton icon={EyeOff} label="Ignore" description="Mark as intentionally kept (removes from active list)" />
              <ActionButton icon={Trash2} label="Mark for Deletion" description="Flag for cleanup (CloudWaste doesn't delete)" color="orange" />
              <ActionButton icon={Trash2} label="Delete Record" description="Remove from CloudWaste (doesn't delete AWS resource)" color="red" />
            </div>
            <p className="mt-4 text-amber-700 bg-amber-50 p-3 rounded">
              ⚠️ <strong>Important:</strong> CloudWaste only detects and tracks orphaned resources.
              You must delete resources manually in your AWS console.
            </p>
          </div>
        </StepCard>
      </div>
    </div>
  );
}

function DetectionStrategySection() {
  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold text-gray-900">Detection Strategy</h1>
      <p className="text-xl text-gray-600">
        How CloudWaste identifies truly orphaned resources
      </p>

      <div className="rounded-lg bg-purple-50 border border-purple-200 p-6">
        <h3 className="text-lg font-semibold text-purple-900 mb-3">🎯 What Makes a Resource "Orphaned"?</h3>
        <p className="text-purple-800 mb-4">
          A resource is considered orphaned if it meets ONE of these criteria:
        </p>
        <ul className="list-disc list-inside space-y-2 text-purple-800 ml-4">
          <li><strong>Never used:</strong> Created but never attached or consumed any I/O</li>
          <li><strong>Abandoned after use:</strong> Was active in the past but no activity for 30+ days</li>
          <li><strong>Part of deleted environment:</strong> Related resources were deleted but this one was forgotten</li>
        </ul>
      </div>

      <div className="space-y-4">
        <h3 className="text-2xl font-bold text-gray-900">Intelligent Detection with CloudWatch</h3>
        <p className="text-gray-700">
          Unlike basic tools that only check resource status (attached/unattached), CloudWaste uses
          <strong> AWS CloudWatch Metrics</strong> to analyze actual usage patterns.
        </p>

        <div className="grid gap-4 md:grid-cols-2">
          <DetectionCard
            title="For EBS Volumes"
            metrics={["VolumeReadOps", "VolumeWriteOps"]}
            logic={[
              "Checks last 90 days of I/O activity",
              "Detects if volume was EVER used",
              "Identifies last active date",
              "Distinguishes 'never used' vs 'abandoned'"
            ]}
          />
          <DetectionCard
            title="For Elastic IPs"
            metrics={["AssociationId"]}
            logic={[
              "Checks if IP is currently associated",
              "Uses custom 'CreatedDate' tag for age",
              "No CloudWatch metrics available (AWS limitation)"
            ]}
          />
          <DetectionCard
            title="For NAT Gateways"
            metrics={["BytesOutToDestination", "BytesOutToSource"]}
            logic={[
              "Checks CloudWatch traffic metrics (30 days)",
              "Validates route table references",
              "Checks subnet associations",
              "Verifies VPC has Internet Gateway",
              "4 orphan scenarios detected"
            ]}
          />
          <DetectionCard
            title="For Load Balancers"
            metrics={["RequestCount (ALB/CLB)", "ActiveFlowCount (NLB)"]}
            logic={[
              "Supports ALB, NLB, CLB, and GWLB",
              "Checks healthy backend targets & target groups",
              "Validates listener configuration",
              "Analyzes CloudWatch traffic (30 days)",
              "Validates security group ingress rules",
              "Detects never-used LBs (>30 days, 0 traffic)",
              "7 comprehensive orphan scenarios"
            ]}
          />
        </div>
      </div>

      <div className="space-y-4">
        <h3 className="text-2xl font-bold text-gray-900">Confidence Levels Explained</h3>
        <div className="space-y-3">
          <ConfidenceBadge
            level="critical"
            color="red"
            criteria={[
              "Abandoned for 90+ days with zero activity",
              "Misconfigured with no routing or connectivity",
              "Multiple failure criteria met simultaneously",
              "Extremely high probability of waste"
            ]}
            recommendation="Immediate action recommended - critical waste"
          />
          <ConfidenceBadge
            level="high"
            color="red"
            criteria={[
              "Never used since creation (30+ days ago)",
              "No I/O activity for 30+ days (was active before)",
              "Clear evidence of abandonment"
            ]}
            recommendation="Safe to delete - high probability of waste"
          />
          <ConfidenceBadge
            level="medium"
            color="orange"
            criteria={[
              "No activity for 7-30 days",
              "Unattached for 30+ days (usage history unavailable)",
              "Created recently but never used (7-30 days)"
            ]}
            recommendation="Review before deleting - may be intentional"
          />
          <ConfidenceBadge
            level="low"
            color="yellow"
            criteria={[
              "Created less than 7 days ago",
              "Usage pattern unclear",
              "May be for future use"
            ]}
            recommendation="Monitor - likely not orphaned yet"
          />
        </div>
      </div>

      <div className="rounded-lg bg-blue-50 border border-blue-200 p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-3">🚫 What We DON'T Detect</h3>
        <ul className="list-disc list-inside space-y-2 text-blue-800 ml-4">
          <li>Resources with activity in the last 7 days (not orphaned)</li>
          <li>Resources explicitly ignored by user settings</li>
          <li>Resources younger than configured minimum age threshold</li>
        </ul>
      </div>
    </div>
  );
}

function SupportedResourcesSection() {
  const resources = [
    {
      name: "EBS Volumes",
      icon: "💾",
      detection: "Unattached volumes with CloudWatch I/O metrics analysis",
      cost: "~$0.08-0.10/GB/month",
      confidence: "High - Uses CloudWatch metrics",
    },
    {
      name: "Elastic IPs",
      icon: "🌐",
      detection: "Unassociated IP addresses",
      cost: "~$3.60/month",
      confidence: "Medium - No CloudWatch metrics available",
    },
    {
      name: "EBS Snapshots",
      icon: "📸",
      detection: "Snapshots >90 days old with deleted source volume",
      cost: "~$0.05/GB/month",
      confidence: "High - Clear orphan signal",
    },
    {
      name: "EC2 Instances (Stopped)",
      icon: "🖥️",
      detection: "Instances stopped for >30 days",
      cost: "Storage costs only",
      confidence: "High - Long stopped duration",
    },
    {
      name: "Load Balancers",
      icon: "⚖️",
      detection: "7 scenarios: No healthy targets, No listeners, No target groups, Never used (0 traffic >30d), Unhealthy long-term (>90d), Low traffic, Security group blocks traffic. Supports ALB, NLB, CLB, and GWLB",
      cost: "~$7.50-22/month (GWLB $7.50, CLB $18, ALB/NLB $22)",
      confidence: "High to Critical - Comprehensive multi-factor validation with CloudWatch metrics and security analysis",
    },
    {
      name: "RDS Instances",
      icon: "🗄️",
      detection: "5 scenarios: Stopped long-term (>7d), Idle running (0 connections), Zero I/O (no read/write), Never connected (>7d), No backups. Comprehensive CloudWatch analysis",
      cost: "~$12-560/month (compute varies by instance type) + $0.092-0.115/GB (storage). Multi-AZ doubles compute cost",
      confidence: "Medium to Critical - Multi-scenario validation with CloudWatch metrics (DatabaseConnections, ReadIOPS, WriteIOPS)",
    },
    {
      name: "NAT Gateways",
      icon: "🚪",
      detection: "4 scenarios: No traffic (<1MB/30d), No routing configuration, VPC without Internet Gateway, Route tables not associated with subnets",
      cost: "~$32.40/month + data processing",
      confidence: "High to Critical - Multi-factor validation including CloudWatch metrics and configuration analysis",
    },
    {
      name: "FSx File Systems",
      icon: "📁",
      detection: "8 scenarios: Completely inactive (0 transfers 30+d), Over-provisioned storage (<10% used), Over-provisioned throughput (<10% utilized), Excessive backup retention (orphaned backups), Unused file shares (Windows: 0 SMB connections 7+d), Low IOPS utilization (<10%), Multi-AZ overkill (dev/test environments), Wrong storage type (SSD for archive workloads). Supports Lustre, Windows, ONTAP, OpenZFS",
      cost: "Lustre: $0.145/GB/month, Windows: $0.13/GB (SSD) or $0.013/GB (HDD), ONTAP: $0.144/GB, OpenZFS: $0.14/GB. Backups: $0.050/GB. Throughput (Windows/ONTAP): $2.20/MB/s. Multi-AZ: 2× cost",
      confidence: "Critical to High - Multi-scenario validation with CloudWatch metrics (DataReadBytes, DataWriteBytes, StorageUsed, ThroughputUtilization, ClientConnections, DiskIopsUtilization) and backup API analysis",
    },
    {
      name: "Neptune Clusters",
      icon: "🔵",
      detection: "Clusters with no database connections for 7+ days",
      cost: "~$250-500/month",
      confidence: "High - No active connections",
    },
    {
      name: "MSK (Kafka) Clusters",
      icon: "📨",
      detection: "Clusters with no data traffic for 7+ days",
      cost: "~$150-300/month per broker",
      confidence: "High - No data in/out",
    },
    {
      name: "EKS Clusters",
      icon: "☸️",
      detection: "5 scenarios: No worker nodes (0 nodes/Fargate profiles), All nodes unhealthy (degraded state), Low CPU utilization (<5% avg), Fargate misconfigured (no profiles), Outdated K8s version (>3 versions behind)",
      cost: "~$73/month (control plane) + $15-277/month per node (t3.small to m5.2xlarge). Full cluster cost calculated based on node types",
      confidence: "Medium to Critical - Multi-scenario validation with CloudWatch CPU metrics and health checks",
    },
    {
      name: "SageMaker Endpoints",
      icon: "🤖",
      detection: "Endpoints with no invocations for 7+ days",
      cost: "~$83-165/month",
      confidence: "High - No model invocations",
    },
    {
      name: "Redshift Clusters",
      icon: "📊",
      detection: "Clusters with no database connections for 7+ days",
      cost: "~$180-720/month",
      confidence: "High - No active queries",
    },
    {
      name: "ElastiCache Clusters",
      icon: "⚡",
      detection: "Zero cache hits, low hit rate (<50%), no connections, or over-provisioned memory (<20% used)",
      cost: "~$12-539/month",
      confidence: "Critical/High - Wasted cache infrastructure",
    },
    {
      name: "VPN Connections",
      icon: "🔐",
      detection: "VPN with <1MB data transfer in 30 days",
      cost: "~$36/month",
      confidence: "High - No VPN traffic",
    },
    {
      name: "Transit Gateway Attachments",
      icon: "🌉",
      detection: "Attachments with <1MB traffic in 30 days",
      cost: "~$36/month",
      confidence: "High - No traffic",
    },
    {
      name: "OpenSearch Domains",
      icon: "🔍",
      detection: "Domains with no search requests for 7+ days",
      cost: "~$116-164/month",
      confidence: "High - No search activity",
    },
    {
      name: "Global Accelerator",
      icon: "🌍",
      detection: "Accelerators with 0 endpoints for 7+ days",
      cost: "~$18/month",
      confidence: "High - No endpoints configured",
    },
    {
      name: "Kinesis Streams",
      icon: "🌊",
      detection: "Streams with no incoming records for 7+ days",
      cost: "~$15/month per shard",
      confidence: "High - No data ingestion",
    },
    {
      name: "VPC Endpoints",
      icon: "🔗",
      detection: "Endpoints with no network interfaces for 7+ days",
      cost: "~$7/month",
      confidence: "High - No network usage",
    },
    {
      name: "DocumentDB Clusters",
      icon: "📄",
      detection: "Clusters with no database connections for 7+ days",
      cost: "~$199/month",
      confidence: "High - No active connections",
    },
    {
      name: "S3 Buckets",
      icon: "🗄️",
      detection: "4 scenarios: Empty buckets (0 objects, 90+ days old), All objects very old (365+ days, no recent activity), Incomplete multipart uploads (30+ days old, hidden storage costs), No lifecycle policy with old objects (180+ days, optimization opportunity)",
      cost: "~$0.023/GB/month (Standard) to $0.004/GB/month (Glacier). Empty buckets cost $0 but waste management overhead",
      confidence: "Medium to High - Based on bucket age, object age distribution, multipart upload analysis, and lifecycle policy evaluation",
    },
    {
      name: "Lambda Functions",
      icon: "⚡",
      detection: "4 scenarios (priority): Unused provisioned concurrency (<1% utilization over 30 days - VERY EXPENSIVE), Never invoked (30+ days since creation, 0 invocations), Zero invocations (90+ days without invocations), 100% failures (>95% error rate over 30 days)",
      cost: "Provisioned concurrency: $0.0000041667/GB-second (~$10-100/month for unused). Regular: $0.20/1M requests + $0.0000166667/GB-second compute. Never invoked: ~$0.50/month (storage only)",
      confidence: "Critical (provisioned concurrency) to High - Based on CloudWatch Invocations, ProvisionedConcurrencyInvocations, and Errors metrics",
    },
    {
      name: "DynamoDB Tables",
      icon: "🗃️",
      detection: "5 scenarios (priority): Over-provisioned capacity (<10% utilization over 7 days - VERY EXPENSIVE), Unused Global Secondary Indexes (GSI never queried in 14+ days - doubles cost), Never used Provisioned tables (0 usage since creation), Never used On-Demand tables (60+ days without usage), Empty tables (0 items for 90+ days)",
      cost: "Provisioned: $0.00013/RCU/hour + $0.00013/WCU/hour (~$0.095/unit/month) + $0.25/GB storage. On-Demand: $0.25/1M reads + $1.25/1M writes. GSI costs same as table",
      confidence: "Critical (over-provisioned <5% util) to High - Based on CloudWatch ConsumedReadCapacityUnits, ConsumedWriteCapacityUnits metrics and table metadata",
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold text-gray-900">Supported Resources</h1>
      <p className="text-xl text-gray-600">Currently supporting 25 AWS resource types with intelligent CloudWatch-based detection</p>

      <div className="grid gap-4">
        {resources.map((resource, index) => (
          <div key={index} className="rounded-lg border bg-white p-6 hover:shadow-md transition-shadow">
            <div className="flex items-start gap-4">
              <div className="text-4xl">{resource.icon}</div>
              <div className="flex-1">
                <h3 className="text-xl font-semibold text-gray-900">{resource.name}</h3>
                <p className="mt-2 text-gray-700"><strong>Detection:</strong> {resource.detection}</p>
                <p className="mt-1 text-gray-700"><strong>Typical Cost:</strong> {resource.cost}</p>
                <p className="mt-1 text-sm text-gray-600"><strong>Confidence:</strong> {resource.confidence}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="rounded-lg bg-gray-100 border p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-2">🚀 Coming Soon</h3>
        <p className="text-gray-700">
          We're actively working on support for: CloudFormation stacks, ECS/Fargate tasks,
          and multi-cloud providers (Azure, GCP).
        </p>
      </div>
    </div>
  );
}

function DetectionRulesSection() {
  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold text-gray-900">Detection Rules</h1>
      <p className="text-xl text-gray-600">Customize how CloudWaste identifies orphaned resources</p>

      <div className="space-y-4">
        <p className="text-gray-700">
          Go to <strong>Settings → Detection Rules</strong> to configure custom detection criteria
          for each resource type.
        </p>

        <div className="grid gap-6 md:grid-cols-2">
          <RuleCard
            title="Minimum Age"
            description="Resources younger than this threshold are ignored to avoid false positives"
            range="0-90 days"
            default="7 days (EBS Volumes), 3 days (Elastic IPs)"
            example="Set to 0 to detect immediately, or 30 to only flag old resources"
          />
          <RuleCard
            title="High Confidence Threshold"
            description="Resources older than this are marked with 'high confidence'"
            range="7-180 days"
            default="30 days"
            example="Resources older than 30 days with no activity → high confidence"
          />
        </div>

        <div className="rounded-lg bg-amber-50 border border-amber-200 p-6">
          <h3 className="text-lg font-semibold text-amber-900 mb-2">⚠️ Important Notes</h3>
          <ul className="list-disc list-inside space-y-2 text-amber-800 ml-4">
            <li>Rules apply to <strong>future scans only</strong> (not retroactive)</li>
            <li>Each resource type can have different rules</li>
            <li>Lower thresholds may increase false positives</li>
            <li>Higher thresholds may miss short-term waste</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function UnderstandingResultsSection() {
  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold text-gray-900">Understanding Results</h1>

      <div className="space-y-6">
        <div>
          <h3 className="text-2xl font-bold text-gray-900 mb-4">Resource Actions</h3>
          <div className="space-y-3">
            <ActionExplanation
              icon={Eye}
              title="View Details"
              description="Click to expand full resource metadata including CloudWatch usage history, creation date, encryption status, and more."
            />
            <ActionExplanation
              icon={EyeOff}
              title="Ignore Resource"
              description="Mark this resource as intentionally kept. It will be filtered out of active orphan lists but kept in database for tracking."
              color="gray"
            />
            <ActionExplanation
              icon={Trash2}
              title="Mark for Deletion"
              description="Flag this resource for cleanup. CloudWaste doesn't delete anything - you must manually delete in AWS console."
              color="orange"
            />
            <ActionExplanation
              icon={Trash2}
              title="Delete Record"
              description="Remove this resource from CloudWaste database only. Does NOT delete the actual AWS resource."
              color="red"
            />
          </div>
        </div>

        <div>
          <h3 className="text-2xl font-bold text-gray-900 mb-4">Cost Metrics</h3>
          <div className="space-y-3">
            <MetricExplanation
              label="Future waste"
              value="$0.80/month"
              description="Estimated monthly cost if this resource stays orphaned. Based on AWS pricing for the resource type and size."
            />
            <MetricExplanation
              label="Already wasted"
              value="$0.10 over 21 hours"
              description="Total money lost since resource creation. Calculated as: (monthly_cost / 30 days) × age_in_days"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function FAQSection() {
  const faqs = [
    {
      q: "Does CloudWaste delete my AWS resources?",
      a: "No. CloudWaste only detects and reports orphaned resources. You maintain full control and must delete resources manually in your AWS console. We use read-only IAM permissions."
    },
    {
      q: "Why is my recently created resource flagged as orphaned?",
      a: "Check the confidence badge. Resources with 'low confidence' are flagged for monitoring but may not be truly orphaned. Adjust 'Minimum Age' in Detection Rules to avoid this."
    },
    {
      q: "How accurate are the cost estimates?",
      a: "Cost estimates are based on AWS public pricing and actual resource specifications (size, type). They don't include discounts (Reserved Instances, Savings Plans) or specific pricing agreements."
    },
    {
      q: "Can I customize detection rules per resource type?",
      a: "Yes! Go to Settings → Detection Rules to configure minimum age and confidence thresholds for each of the 22 supported resource types (5 core + 17 advanced high-cost resources)."
    },
    {
      q: "What if CloudWatch metrics are unavailable?",
      a: "Resources without CloudWatch metrics will show 'usage history unavailable' and typically receive 'medium' or 'low' confidence. Consider setting custom tags like 'CreatedDate' for better tracking."
    },
    {
      q: "How often should I run scans?",
      a: "CloudWaste automatically runs daily scans. You can also trigger manual scans anytime. More frequent scans help catch waste early."
    },
    {
      q: "Is my AWS data secure?",
      a: "Yes. All credentials are encrypted with Fernet encryption. We use read-only permissions. Your data never leaves our secure infrastructure except for AWS API calls."
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold text-gray-900">Frequently Asked Questions</h1>

      <div className="space-y-4">
        {faqs.map((faq, index) => (
          <div key={index} className="rounded-lg border bg-white p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-2">{faq.q}</h3>
            <p className="text-gray-700">{faq.a}</p>
          </div>
        ))}
      </div>

      <div className="rounded-lg bg-blue-50 border border-blue-200 p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-2">Need More Help?</h3>
        <p className="text-blue-800">
          Contact us at <strong>support@cloudwaste.com</strong> or visit our GitHub issues page
          for feature requests and bug reports.
        </p>
      </div>
    </div>
  );
}

// Helper Components

function FeatureCard({ icon: Icon, title, description }: any) {
  return (
    <div className="rounded-lg border bg-white p-6">
      <div className="mb-4 inline-flex rounded-lg bg-blue-100 p-3">
        <Icon className="h-6 w-6 text-blue-600" />
      </div>
      <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
      <p className="mt-2 text-gray-600">{description}</p>
    </div>
  );
}

function StepCard({ number, title, description, children }: any) {
  return (
    <div className="rounded-lg border bg-white p-6">
      <div className="flex items-start gap-4">
        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-blue-600 text-white font-bold">
          {number}
        </div>
        <div className="flex-1">
          <h3 className="text-xl font-semibold text-gray-900">{title}</h3>
          <p className="mt-1 text-gray-600">{description}</p>
          <div className="mt-4">{children}</div>
        </div>
      </div>
    </div>
  );
}

function ActionButton({ icon: Icon, label, description, color = "blue" }: any) {
  const colors: any = {
    blue: "bg-blue-100 text-blue-700",
    gray: "bg-gray-100 text-gray-700",
    orange: "bg-orange-100 text-orange-700",
    red: "bg-red-100 text-red-700",
  };

  return (
    <div className="flex items-start gap-3">
      <div className={`rounded p-2 ${colors[color]}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div>
        <p className="font-semibold text-gray-900">{label}</p>
        <p className="text-sm text-gray-600">{description}</p>
      </div>
    </div>
  );
}

function DetectionCard({ title, metrics, logic }: any) {
  return (
    <div className="rounded-lg border bg-white p-6">
      <h4 className="text-lg font-semibold text-gray-900 mb-3">{title}</h4>
      <div className="space-y-3">
        <div>
          <p className="text-sm font-medium text-gray-700">CloudWatch Metrics:</p>
          <ul className="mt-1 list-disc list-inside text-sm text-gray-600 ml-2">
            {metrics.map((metric: string, i: number) => (
              <li key={i}><code className="bg-gray-100 px-1">{metric}</code></li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-sm font-medium text-gray-700">Detection Logic:</p>
          <ul className="mt-1 list-disc list-inside text-sm text-gray-600 ml-2">
            {logic.map((item: string, i: number) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function ConfidenceBadge({ level, color, criteria, recommendation }: any) {
  const colors: any = {
    red: "bg-red-100 border-red-200",
    orange: "bg-orange-100 border-orange-200",
    yellow: "bg-yellow-100 border-yellow-200",
  };

  const badgeColors: any = {
    red: "bg-red-100 text-red-700",
    orange: "bg-orange-100 text-orange-700",
    yellow: "bg-yellow-100 text-yellow-700",
  };

  return (
    <div className={`rounded-lg border p-4 ${colors[color]}`}>
      <div className="flex items-center gap-3 mb-2">
        <span className={`px-3 py-1 rounded text-sm font-semibold ${badgeColors[color]}`}>
          {level} confidence
        </span>
        <CheckCircle className="h-5 w-5 text-gray-600" />
      </div>
      <p className="text-sm font-medium text-gray-900 mb-2">Criteria:</p>
      <ul className="list-disc list-inside text-sm text-gray-700 ml-2 space-y-1">
        {criteria.map((item: string, i: number) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
      <p className="mt-3 text-sm font-medium text-gray-900">
        ✅ Recommendation: <span className="font-normal">{recommendation}</span>
      </p>
    </div>
  );
}

function RuleCard({ title, description, range, defaultValue, example }: any) {
  return (
    <div className="rounded-lg border bg-white p-6">
      <h4 className="text-lg font-semibold text-gray-900">{title}</h4>
      <p className="mt-2 text-gray-700">{description}</p>
      <div className="mt-4 space-y-2 text-sm">
        <p><strong>Range:</strong> {range}</p>
        <p><strong>Default:</strong> {defaultValue}</p>
        <p className="text-gray-600"><em>Example: {example}</em></p>
      </div>
    </div>
  );
}

function ActionExplanation({ icon: Icon, title, description, color = "blue" }: any) {
  const colors: any = {
    blue: "bg-blue-100 text-blue-700",
    gray: "bg-gray-100 text-gray-700",
    orange: "bg-orange-100 text-orange-700",
    red: "bg-red-100 text-red-700",
  };

  return (
    <div className="flex items-start gap-4 rounded-lg border bg-white p-4">
      <div className={`rounded p-2 ${colors[color]}`}>
        <Icon className="h-5 w-5" />
      </div>
      <div>
        <h4 className="font-semibold text-gray-900">{title}</h4>
        <p className="mt-1 text-sm text-gray-600">{description}</p>
      </div>
    </div>
  );
}

function MetricExplanation({ label, value, description }: any) {
  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-baseline gap-2">
        <span className="text-gray-600">{label}:</span>
        <span className="font-semibold text-orange-600">{value}</span>
      </div>
      <p className="mt-2 text-sm text-gray-600">{description}</p>
    </div>
  );
}
