import type { Metadata } from "next";
import { FileText, AlertTriangle, Shield, Ban, Scale } from "lucide-react";

export const metadata: Metadata = {
  title: "Terms of Service - CloudWaste",
  description:
    "CloudWaste Terms of Service - Read our terms and conditions for using the CloudWaste platform.",
};

export default function TermsOfServicePage() {
  return (
    <div className="prose prose-gray max-w-none">
      {/* Header */}
      <div className="not-prose mb-8">
        <div className="flex items-center gap-3 mb-4">
          <FileText className="w-8 h-8 text-blue-600" />
          <h1 className="text-4xl font-bold text-gray-900">Terms of Service</h1>
        </div>
        <p className="text-gray-600 text-lg">
          Last updated: <strong>January 2025</strong>
        </p>
        <p className="text-gray-600 mt-2">
          These Terms of Service ("Terms") govern your access to and use of CloudWaste ("Service", "we", "us", or
          "our"). By accessing or using our Service, you agree to be bound by these Terms.
        </p>
      </div>

      {/* Important Notice */}
      <div className="not-prose bg-yellow-50 border border-yellow-200 rounded-lg p-6 mb-8">
        <h3 className="text-lg font-semibold text-yellow-900 mb-3 flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          Important Notice
        </h3>
        <p className="text-yellow-800 text-sm">
          Please read these Terms carefully before using CloudWaste. By creating an account or using our Service,
          you acknowledge that you have read, understood, and agree to be bound by these Terms. If you do not agree,
          please do not use our Service.
        </p>
      </div>

      {/* Table of Contents */}
      <nav className="not-prose bg-gray-50 rounded-lg p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Table of Contents</h2>
        <ol className="space-y-2 text-sm">
          <li>
            <a href="#acceptance" className="text-blue-600 hover:underline">
              1. Acceptance of Terms
            </a>
          </li>
          <li>
            <a href="#eligibility" className="text-blue-600 hover:underline">
              2. Eligibility
            </a>
          </li>
          <li>
            <a href="#description" className="text-blue-600 hover:underline">
              3. Service Description
            </a>
          </li>
          <li>
            <a href="#accounts" className="text-blue-600 hover:underline">
              4. User Accounts
            </a>
          </li>
          <li>
            <a href="#cloud-access" className="text-blue-600 hover:underline">
              5. Cloud Account Access
            </a>
          </li>
          <li>
            <a href="#user-responsibilities" className="text-blue-600 hover:underline">
              6. User Responsibilities
            </a>
          </li>
          <li>
            <a href="#prohibited-activities" className="text-blue-600 hover:underline">
              7. Prohibited Activities
            </a>
          </li>
          <li>
            <a href="#intellectual-property" className="text-blue-600 hover:underline">
              8. Intellectual Property
            </a>
          </li>
          <li>
            <a href="#liability" className="text-blue-600 hover:underline">
              9. Limitation of Liability
            </a>
          </li>
          <li>
            <a href="#warranties" className="text-blue-600 hover:underline">
              10. Warranties and Disclaimers
            </a>
          </li>
          <li>
            <a href="#termination" className="text-blue-600 hover:underline">
              11. Termination
            </a>
          </li>
          <li>
            <a href="#changes" className="text-blue-600 hover:underline">
              12. Changes to Terms
            </a>
          </li>
          <li>
            <a href="#governing-law" className="text-blue-600 hover:underline">
              13. Governing Law
            </a>
          </li>
          <li>
            <a href="#contact" className="text-blue-600 hover:underline">
              14. Contact Information
            </a>
          </li>
        </ol>
      </nav>

      {/* 1. Acceptance of Terms */}
      <section id="acceptance" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">1. Acceptance of Terms</h2>
        <p>
          By accessing or using CloudWaste, you agree to comply with and be bound by these Terms. These Terms
          constitute a legally binding agreement between you and CloudWaste.
        </p>
        <p className="mt-4">
          If you are using CloudWaste on behalf of an organization, you represent and warrant that you have the
          authority to bind that organization to these Terms, and your acceptance of these Terms will be treated as
          acceptance by that organization.
        </p>
      </section>

      {/* 2. Eligibility */}
      <section id="eligibility" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">2. Eligibility</h2>
        <p>
          You must be at least <strong>18 years old</strong> (or the age of majority in your jurisdiction) to use
          CloudWaste. By using our Service, you represent and warrant that you meet this age requirement.
        </p>
        <p className="mt-4">
          You may not use CloudWaste if you are prohibited from receiving our Service under applicable law.
        </p>
      </section>

      {/* 3. Service Description */}
      <section id="description" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">3. Service Description</h2>
        <p>
          CloudWaste is a cloud resource optimization platform that helps you:
        </p>
        <ul className="space-y-2 mt-4">
          <li>
            <strong>Detect orphaned resources:</strong> Identify unused or idle cloud resources across AWS, Azure,
            and GCP
          </li>
          <li>
            <strong>Estimate cost savings:</strong> Calculate potential savings from removing waste
          </li>
          <li>
            <strong>Analyze usage patterns:</strong> Review CloudWatch/Azure Monitor metrics for resource utilization
          </li>
          <li>
            <strong>Track optimization:</strong> Monitor your cloud cost reduction over time
          </li>
        </ul>
        <div className="not-prose bg-blue-50 border border-blue-200 rounded-lg p-4 mt-6">
          <p className="text-blue-900 text-sm flex items-start gap-2">
            <Shield className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <span>
              <strong>Read-Only Access:</strong> CloudWaste only requests <strong>read-only permissions</strong> to
              your cloud accounts. We <strong>cannot and will not</strong> delete, modify, or create any resources in
              your cloud environments. All actions must be performed manually by you.
            </span>
          </p>
        </div>
      </section>

      {/* 4. User Accounts */}
      <section id="accounts" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">4. User Accounts</h2>
        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">4.1 Account Creation</h3>
        <p>
          To use CloudWaste, you must create an account by providing accurate and complete information. You are
          responsible for:
        </p>
        <ul className="space-y-2 mt-2">
          <li>
            <strong>Maintaining security:</strong> Keeping your password confidential
          </li>
          <li>
            <strong>Account activity:</strong> All activities that occur under your account
          </li>
          <li>
            <strong>Unauthorized access:</strong> Notifying us immediately if you suspect unauthorized access
          </li>
        </ul>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">4.2 Account Termination</h3>
        <p>
          You may terminate your account at any time by contacting us at{" "}
          <a href="mailto:support@cloudwaste.com" className="text-blue-600 hover:underline">
            support@cloudwaste.com
          </a>
          . We may suspend or terminate your account if you violate these Terms.
        </p>
      </section>

      {/* 5. Cloud Account Access */}
      <section id="cloud-access" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">5. Cloud Account Access</h2>
        <p>
          When you connect your cloud accounts (AWS, Azure, GCP) to CloudWaste, you grant us <strong>limited,
          read-only access</strong> to:
        </p>
        <ul className="space-y-2 mt-4">
          <li>List and describe cloud resources (EC2, S3, RDS, Azure VMs, GCP Compute, etc.)</li>
          <li>Retrieve CloudWatch/Azure Monitor metrics for usage analysis</li>
          <li>Access cost and billing information (if you enable Cost Explorer permissions)</li>
        </ul>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">5.1 Your Responsibilities</h3>
        <p>You are responsible for:</p>
        <ul className="space-y-2 mt-2">
          <li>
            <strong>Granting correct permissions:</strong> Ensuring the IAM roles/service principals you provide have
            only read-only permissions
          </li>
          <li>
            <strong>Credential security:</strong> Rotating credentials regularly (we recommend every 90 days)
          </li>
          <li>
            <strong>Revoking access:</strong> Removing CloudWaste's access from your cloud console if you no longer
            use our Service
          </li>
        </ul>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">5.2 Data Encryption</h3>
        <p>
          All cloud credentials you provide are <strong>encrypted at rest</strong> using industry-standard Fernet
          symmetric encryption. We store credentials securely and never expose them in logs or error messages.
        </p>
      </section>

      {/* 6. User Responsibilities */}
      <section id="user-responsibilities" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">6. User Responsibilities</h2>
        <p>As a user of CloudWaste, you agree to:</p>
        <ul className="space-y-2 mt-4">
          <li>
            <strong>Verify recommendations:</strong> Review all resource recommendations before taking action in your
            cloud console
          </li>
          <li>
            <strong>Understand limitations:</strong> CloudWaste provides <strong>recommendations only</strong> and
            cannot delete resources on your behalf
          </li>
          <li>
            <strong>Backup critical data:</strong> Always backup important data before deleting any cloud resources
          </li>
          <li>
            <strong>Comply with laws:</strong> Use CloudWaste in compliance with all applicable laws and regulations
          </li>
          <li>
            <strong>Respect rate limits:</strong> Not abuse our API or attempt to bypass rate limiting
          </li>
        </ul>
      </section>

      {/* 7. Prohibited Activities */}
      <section id="prohibited-activities" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <Ban className="w-6 h-6 text-red-600" />
          7. Prohibited Activities
        </h2>
        <p>You may NOT use CloudWaste to:</p>
        <div className="not-prose bg-red-50 border border-red-200 rounded-lg p-6 mt-4">
          <ul className="space-y-2 text-red-900 text-sm">
            <li>✗ Reverse engineer, decompile, or disassemble the Service</li>
            <li>✗ Attempt to gain unauthorized access to our systems or other users' accounts</li>
            <li>✗ Use the Service for illegal activities or to violate any laws</li>
            <li>✗ Upload malicious code, viruses, or malware</li>
            <li>✗ Scrape, spider, or crawl the Service using automated means</li>
            <li>✗ Interfere with or disrupt the Service's operation</li>
            <li>✗ Impersonate another person or entity</li>
            <li>✗ Share your account credentials with others</li>
            <li>✗ Use the Service to compete with CloudWaste or build a similar product</li>
          </ul>
        </div>
        <p className="mt-4 text-sm text-gray-600">
          <strong>Violation of these Terms may result in immediate account suspension or termination.</strong>
        </p>
      </section>

      {/* 8. Intellectual Property */}
      <section id="intellectual-property" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">8. Intellectual Property</h2>
        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">8.1 CloudWaste IP</h3>
        <p>
          All content, features, and functionality of CloudWaste (including but not limited to design, text,
          graphics, logos, code, and software) are owned by CloudWaste and are protected by copyright, trademark,
          and other intellectual property laws.
        </p>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">8.2 Your Data</h3>
        <p>
          You retain all rights to your cloud data. By using CloudWaste, you grant us a limited license to process
          your data solely for providing the Service. We do not claim ownership of your data.
        </p>
      </section>

      {/* 9. Limitation of Liability */}
      <section id="liability" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">9. Limitation of Liability</h2>
        <div className="not-prose bg-gray-50 border border-gray-300 rounded-lg p-6">
          <p className="text-gray-900 text-sm font-semibold mb-3">
            TO THE MAXIMUM EXTENT PERMITTED BY LAW:
          </p>
          <ul className="space-y-3 text-gray-800 text-sm">
            <li>
              CloudWaste provides recommendations and analysis <strong>for informational purposes only</strong>. We
              are not responsible for:
              <ul className="ml-6 mt-2 space-y-1">
                <li>• Accidental deletion of cloud resources</li>
                <li>• Data loss or service interruptions</li>
                <li>• Incorrect cost estimations</li>
                <li>• Downtime or availability issues</li>
              </ul>
            </li>
            <li>
              <strong>You are solely responsible</strong> for verifying recommendations and deciding what actions to
              take in your cloud console.
            </li>
            <li>
              CloudWaste's total liability for any claims shall not exceed the amount you paid us in the 12 months
              preceding the claim (or $100 if you have not paid us).
            </li>
            <li>
              We are not liable for indirect, incidental, special, consequential, or punitive damages.
            </li>
          </ul>
        </div>
      </section>

      {/* 10. Warranties */}
      <section id="warranties" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">10. Warranties and Disclaimers</h2>
        <p>
          CloudWaste is provided on an <strong>"AS IS"</strong> and <strong>"AS AVAILABLE"</strong> basis. We do not
          warrant that:
        </p>
        <ul className="space-y-2 mt-4">
          <li>The Service will be uninterrupted, error-free, or secure</li>
          <li>All recommendations will be accurate or result in cost savings</li>
          <li>Defects will be corrected immediately</li>
          <li>The Service will meet your specific requirements</li>
        </ul>
        <p className="mt-4 text-sm text-gray-600">
          We disclaim all warranties, express or implied, including warranties of merchantability, fitness for a
          particular purpose, and non-infringement.
        </p>
      </section>

      {/* 11. Termination */}
      <section id="termination" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">11. Termination</h2>
        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">11.1 Termination by You</h3>
        <p>
          You may stop using CloudWaste at any time. To delete your account, contact{" "}
          <a href="mailto:support@cloudwaste.com" className="text-blue-600 hover:underline">
            support@cloudwaste.com
          </a>
          .
        </p>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">11.2 Termination by Us</h3>
        <p>We may suspend or terminate your access to CloudWaste:</p>
        <ul className="space-y-2 mt-2">
          <li>If you violate these Terms</li>
          <li>If your account is inactive for more than 12 months</li>
          <li>If we reasonably believe your account poses a security risk</li>
          <li>For legal or regulatory reasons</li>
        </ul>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">11.3 Effect of Termination</h3>
        <p>
          Upon termination, your right to use CloudWaste will cease immediately. We will delete your account data
          within 30 days, except as required by law or to enforce these Terms.
        </p>
      </section>

      {/* 12. Changes to Terms */}
      <section id="changes" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">12. Changes to Terms</h2>
        <p>
          We may modify these Terms from time to time. If we make material changes, we will notify you by:
        </p>
        <ul className="space-y-2 mt-2">
          <li>Email to the address associated with your account</li>
          <li>A prominent notice on our website</li>
        </ul>
        <p className="mt-4">
          Continued use of CloudWaste after changes constitutes acceptance of the revised Terms. If you do not agree,
          you must stop using the Service.
        </p>
      </section>

      {/* 13. Governing Law */}
      <section id="governing-law" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <Scale className="w-6 h-6 text-blue-600" />
          13. Governing Law and Jurisdiction
        </h2>
        <p>
          These Terms are governed by the laws of <strong>[YOUR COUNTRY/STATE]</strong>, without regard to conflict
          of law principles.
        </p>
        <p className="mt-4">
          Any disputes arising from these Terms or your use of CloudWaste shall be resolved in the courts of{" "}
          <strong>[YOUR JURISDICTION]</strong>.
        </p>
        <p className="mt-4 text-sm text-gray-600">
          <strong>EU Users:</strong> Nothing in these Terms affects your mandatory consumer rights under EU law.
        </p>
      </section>

      {/* 14. Contact Information */}
      <section id="contact" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">14. Contact Information</h2>
        <p>
          If you have any questions about these Terms, please contact us:
        </p>
        <div className="not-prose bg-blue-50 rounded-lg p-6 mt-4">
          <p className="text-gray-900 font-semibold text-lg">CloudWaste Legal Team</p>
          <p className="text-gray-700 mt-2">
            Email:{" "}
            <a href="mailto:legal@cloudwaste.com" className="text-blue-600 hover:underline font-semibold">
              legal@cloudwaste.com
            </a>
          </p>
          <p className="text-gray-700">
            Address: <span className="font-mono">[YOUR COMPANY ADDRESS]</span>
          </p>
        </div>
      </section>

      {/* Footer */}
      <div className="not-prose border-t border-gray-200 pt-8 mt-12">
        <p className="text-sm text-gray-500 text-center">
          © {new Date().getFullYear()} CloudWaste. All rights reserved.
        </p>
        <p className="text-xs text-gray-400 text-center mt-2">
          By using CloudWaste, you agree to these Terms of Service and our{" "}
          <a href="/legal/privacy" className="text-blue-600 hover:underline">
            Privacy Policy
          </a>
          .
        </p>
      </div>
    </div>
  );
}
