import type { Metadata } from "next";
import { Shield, Mail, Lock, Database, UserX, Download, AlertTriangle } from "lucide-react";

export const metadata: Metadata = {
  title: "Privacy Policy - CloudWaste | GDPR Compliant",
  description:
    "CloudWaste Privacy Policy - Learn how we collect, use, and protect your personal data in compliance with GDPR and data protection laws.",
};

export default function PrivacyPolicyPage() {
  return (
    <div className="prose prose-gray max-w-none">
      {/* Header */}
      <div className="not-prose mb-8">
        <div className="flex items-center gap-3 mb-4">
          <Shield className="w-8 h-8 text-blue-600" />
          <h1 className="text-4xl font-bold text-gray-900">Privacy Policy</h1>
        </div>
        <p className="text-gray-600 text-lg">
          Last updated: <strong>January 2025</strong>
        </p>
        <p className="text-gray-600 mt-2">
          This Privacy Policy explains how CloudWaste ("we", "us", or "our") collects, uses, and protects your
          personal data in compliance with the{" "}
          <strong>General Data Protection Regulation (GDPR)</strong> and other applicable data protection laws.
        </p>
      </div>

      {/* GDPR Rights Banner */}
      <div className="not-prose bg-blue-50 border border-blue-200 rounded-lg p-6 mb-8">
        <h3 className="text-lg font-semibold text-blue-900 mb-3 flex items-center gap-2">
          <Shield className="w-5 h-5" />
          Your GDPR Rights
        </h3>
        <p className="text-blue-800 text-sm mb-3">
          Under the GDPR (Regulation EU 2016/679), you have the following rights:
        </p>
        <ul className="space-y-2 text-sm text-blue-800">
          <li className="flex items-start gap-2">
            <span className="font-semibold">✓ Right to Access:</span>
            <span>Request a copy of your personal data</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="font-semibold">✓ Right to Rectification:</span>
            <span>Correct inaccurate or incomplete data</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="font-semibold">✓ Right to Erasure:</span>
            <span>Request deletion of your data ("right to be forgotten")</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="font-semibold">✓ Right to Data Portability:</span>
            <span>Receive your data in a machine-readable format</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="font-semibold">✓ Right to Object:</span>
            <span>Object to certain processing of your data</span>
          </li>
          <li className="flex items-start gap-2">
            <span className="font-semibold">✓ Right to Restriction:</span>
            <span>Request temporary restriction of processing</span>
          </li>
        </ul>
        <p className="text-sm text-blue-700 mt-4">
          To exercise any of these rights, contact us at:{" "}
          <a href="mailto:privacy@cloudwaste.com" className="font-semibold underline">
            privacy@cloudwaste.com
          </a>
        </p>
      </div>

      {/* Table of Contents */}
      <nav className="not-prose bg-gray-50 rounded-lg p-6 mb-8">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Table of Contents</h2>
        <ol className="space-y-2 text-sm">
          <li>
            <a href="#data-controller" className="text-blue-600 hover:underline">
              1. Data Controller
            </a>
          </li>
          <li>
            <a href="#data-collection" className="text-blue-600 hover:underline">
              2. What Data We Collect
            </a>
          </li>
          <li>
            <a href="#legal-basis" className="text-blue-600 hover:underline">
              3. Legal Basis for Processing
            </a>
          </li>
          <li>
            <a href="#data-usage" className="text-blue-600 hover:underline">
              4. How We Use Your Data
            </a>
          </li>
          <li>
            <a href="#data-sharing" className="text-blue-600 hover:underline">
              5. Data Sharing and Third Parties
            </a>
          </li>
          <li>
            <a href="#data-retention" className="text-blue-600 hover:underline">
              6. Data Retention
            </a>
          </li>
          <li>
            <a href="#data-security" className="text-blue-600 hover:underline">
              7. Data Security
            </a>
          </li>
          <li>
            <a href="#international-transfers" className="text-blue-600 hover:underline">
              8. International Data Transfers
            </a>
          </li>
          <li>
            <a href="#cookies" className="text-blue-600 hover:underline">
              9. Cookies and Tracking Technologies
            </a>
          </li>
          <li>
            <a href="#your-rights" className="text-blue-600 hover:underline">
              10. Exercising Your Rights
            </a>
          </li>
          <li>
            <a href="#children" className="text-blue-600 hover:underline">
              11. Children's Privacy
            </a>
          </li>
          <li>
            <a href="#changes" className="text-blue-600 hover:underline">
              12. Changes to This Policy
            </a>
          </li>
          <li>
            <a href="#contact" className="text-blue-600 hover:underline">
              13. Contact Us
            </a>
          </li>
        </ol>
      </nav>

      {/* 1. Data Controller */}
      <section id="data-controller" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <Database className="w-6 h-6 text-blue-600" />
          1. Data Controller
        </h2>
        <p>
          The data controller responsible for your personal data is:
        </p>
        <div className="not-prose bg-gray-50 rounded-lg p-4 mt-4">
          <p className="text-gray-900 font-semibold">CloudWaste</p>
          <p className="text-gray-600 text-sm mt-1">[YOUR COMPANY ADDRESS]</p>
          <p className="text-gray-600 text-sm">[CITY, POSTAL CODE, COUNTRY]</p>
          <p className="text-gray-600 text-sm mt-2">
            Email:{" "}
            <a href="mailto:privacy@cloudwaste.com" className="text-blue-600 hover:underline">
              privacy@cloudwaste.com
            </a>
          </p>
          <p className="text-gray-600 text-sm">
            Company Registration: <span className="font-mono">[SIRET/VAT NUMBER]</span>
          </p>
        </div>
        <p className="mt-4 text-sm text-gray-600">
          <strong>Note:</strong> If you have questions about how we process your data, please contact our Data
          Protection Officer (DPO) at the email above.
        </p>
      </section>

      {/* 2. What Data We Collect */}
      <section id="data-collection" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">2. What Data We Collect</h2>
        <p>
          We collect different types of data depending on how you interact with CloudWaste:
        </p>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">2.1 Account Information</h3>
        <ul className="space-y-2">
          <li>
            <strong>Email address</strong> (required for account creation and authentication)
          </li>
          <li>
            <strong>Full name</strong> (optional, for personalization)
          </li>
          <li>
            <strong>Hashed password</strong> (encrypted using bcrypt, we never store plaintext passwords)
          </li>
          <li>
            <strong>Account preferences</strong> (notification settings, language, theme)
          </li>
        </ul>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">2.2 Cloud Credentials (Encrypted)</h3>
        <div className="not-prose bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
          <p className="text-yellow-900 text-sm flex items-start gap-2">
            <Lock className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <span>
              <strong>Security:</strong> All cloud credentials (AWS keys, Azure service principals, GCP service
              accounts) are <strong>encrypted at rest</strong> using Fernet symmetric encryption with a master key
              stored securely outside the database. We only request <strong>read-only permissions</strong> and
              cannot perform any destructive actions on your cloud resources.
            </span>
          </p>
        </div>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">2.3 Usage Data</h3>
        <ul className="space-y-2">
          <li>
            <strong>Scan history:</strong> Cloud account scans you initiate (timestamps, regions scanned, resources
            found)
          </li>
          <li>
            <strong>Resource management:</strong> Actions you take on detected resources (ignore, mark for deletion)
          </li>
          <li>
            <strong>Cost savings:</strong> Estimated savings based on resources you optimize
          </li>
        </ul>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">2.4 ML Data (Optional, Consent-Based)</h3>
        <p>
          If you opt-in to ML data collection (fully optional), we collect <strong>anonymized</strong> data for
          improving our AI predictions:
        </p>
        <ul className="space-y-2 mt-2">
          <li>
            <strong>Resource patterns:</strong> Types of resources detected and their characteristics (anonymized)
          </li>
          <li>
            <strong>CloudWatch metrics trends:</strong> CPU, I/O, network usage patterns (no identifiable info)
          </li>
          <li>
            <strong>Optimization decisions:</strong> Your choices on what to keep/delete (anonymized)
          </li>
          <li>
            <strong>Industry/company size:</strong> If you provide it (fully optional and anonymized)
          </li>
        </ul>
        <p className="mt-4 text-sm text-gray-600">
          <strong>What we DON'T collect:</strong> AWS account IDs, resource names/IDs, tags, IP addresses, your
          company name, or any personally identifiable information in ML data.
        </p>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">2.5 Technical Data</h3>
        <ul className="space-y-2">
          <li>
            <strong>IP address:</strong> For security (rate limiting, fraud prevention)
          </li>
          <li>
            <strong>Browser type and version:</strong> For compatibility
          </li>
          <li>
            <strong>Device information:</strong> Operating system, screen resolution
          </li>
          <li>
            <strong>Cookies:</strong> See our <a href="/legal/cookies" className="text-blue-600 hover:underline">Cookie Policy</a>
          </li>
        </ul>
      </section>

      {/* 3. Legal Basis */}
      <section id="legal-basis" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">3. Legal Basis for Processing</h2>
        <p>
          Under Article 6(1) GDPR, we process your data based on the following legal grounds:
        </p>
        <div className="not-prose mt-4 space-y-4">
          <div className="border-l-4 border-blue-500 pl-4">
            <p className="font-semibold text-gray-900">
              (a) <strong>Consent</strong> (Article 6(1)(a) GDPR)
            </p>
            <p className="text-gray-600 text-sm mt-1">
              For ML data collection, marketing emails, and non-essential cookies
            </p>
          </div>
          <div className="border-l-4 border-blue-500 pl-4">
            <p className="font-semibold text-gray-900">
              (b) <strong>Contract Performance</strong> (Article 6(1)(b) GDPR)
            </p>
            <p className="text-gray-600 text-sm mt-1">
              For providing CloudWaste services (scanning, resource detection, cost analysis)
            </p>
          </div>
          <div className="border-l-4 border-blue-500 pl-4">
            <p className="font-semibold text-gray-900">
              (c) <strong>Legal Obligation</strong> (Article 6(1)(c) GDPR)
            </p>
            <p className="text-gray-600 text-sm mt-1">
              For compliance with tax, accounting, and regulatory requirements
            </p>
          </div>
          <div className="border-l-4 border-blue-500 pl-4">
            <p className="font-semibold text-gray-900">
              (f) <strong>Legitimate Interest</strong> (Article 6(1)(f) GDPR)
            </p>
            <p className="text-gray-600 text-sm mt-1">
              For security (fraud prevention, rate limiting), analytics (service improvement), and technical
              operations
            </p>
          </div>
        </div>
      </section>

      {/* 4. How We Use Your Data */}
      <section id="data-usage" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">4. How We Use Your Data</h2>
        <p>We use your personal data for the following purposes:</p>
        <ul className="space-y-3 mt-4">
          <li>
            <strong>Service Delivery:</strong> Scanning your cloud accounts, detecting orphaned resources,
            calculating cost savings
          </li>
          <li>
            <strong>Account Management:</strong> User authentication, password resets, email verification
          </li>
          <li>
            <strong>Communication:</strong> Transactional emails (scan completed, account alerts), optional
            marketing emails (if consented)
          </li>
          <li>
            <strong>Security:</strong> Rate limiting, fraud prevention, abuse detection
          </li>
          <li>
            <strong>Improvement:</strong> Analyzing usage patterns to improve features (anonymized data only)
          </li>
          <li>
            <strong>ML Training:</strong> Training AI models for better predictions (only if you opted in, fully
            anonymized)
          </li>
          <li>
            <strong>Legal Compliance:</strong> Complying with legal obligations (e.g., tax records, GDPR requests)
          </li>
        </ul>
      </section>

      {/* 5. Data Sharing */}
      <section id="data-sharing" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">5. Data Sharing and Third Parties</h2>
        <p>
          We <strong>do not sell</strong> your personal data. We only share data with trusted third parties for the
          following purposes:
        </p>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">5.1 Service Providers</h3>
        <ul className="space-y-2">
          <li>
            <strong>Hosting:</strong> [Your VPS provider / AWS / Azure] (for infrastructure)
          </li>
          <li>
            <strong>Email:</strong> [AWS SES / SendGrid / Mailgun] (for transactional emails)
          </li>
          <li>
            <strong>Analytics:</strong> [Google Analytics / Plausible] (anonymized usage analytics)
          </li>
        </ul>
        <p className="mt-4 text-sm text-gray-600">
          All service providers are GDPR-compliant and bound by Data Processing Agreements (DPAs).
        </p>

        <h3 className="text-xl font-semibold text-gray-900 mt-6 mb-3">5.2 Legal Requirements</h3>
        <p>
          We may disclose your data if required by law, court order, or government request, or to protect our legal
          rights.
        </p>
      </section>

      {/* 6. Data Retention */}
      <section id="data-retention" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">6. Data Retention</h2>
        <p>We retain your data for the following periods:</p>
        <ul className="space-y-2 mt-4">
          <li>
            <strong>Account data:</strong> Until you delete your account + 30 days (for recovery)
          </li>
          <li>
            <strong>Cloud credentials:</strong> Until you remove the cloud account from CloudWaste
          </li>
          <li>
            <strong>Scan history:</strong> 12 months (configurable in settings)
          </li>
          <li>
            <strong>ML data:</strong> 1-3 years (your choice) or until you withdraw consent
          </li>
          <li>
            <strong>Anonymized analytics:</strong> Indefinitely (cannot be linked back to you)
          </li>
          <li>
            <strong>Legal/tax records:</strong> As required by law (typically 7 years)
          </li>
        </ul>
      </section>

      {/* 7. Data Security */}
      <section id="data-security" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <Lock className="w-6 h-6 text-blue-600" />
          7. Data Security
        </h2>
        <p>
          We implement industry-standard security measures to protect your data:
        </p>
        <ul className="space-y-2 mt-4">
          <li>
            <strong>Encryption in transit:</strong> TLS 1.3 for all connections
          </li>
          <li>
            <strong>Encryption at rest:</strong> Fernet encryption for cloud credentials, bcrypt for passwords
          </li>
          <li>
            <strong>Access control:</strong> Role-based access, least-privilege principle
          </li>
          <li>
            <strong>Rate limiting:</strong> Protection against brute-force attacks
          </li>
          <li>
            <strong>Regular audits:</strong> Security reviews and vulnerability scanning
          </li>
          <li>
            <strong>Secure infrastructure:</strong> Isolated VPS, firewall rules, regular updates
          </li>
        </ul>
        <p className="mt-4 text-sm text-gray-600">
          <strong>No breach so far:</strong> We have never experienced a data breach. If one occurs, we will notify
          affected users within 72 hours as required by GDPR Article 33.
        </p>
      </section>

      {/* 8. International Transfers */}
      <section id="international-transfers" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">8. International Data Transfers</h2>
        <p>
          Your data is primarily stored in: <strong>[EU / Your server location]</strong>
        </p>
        <p className="mt-4">
          If we transfer data outside the EU/EEA, we ensure adequate protection through:
        </p>
        <ul className="space-y-2 mt-2">
          <li>
            <strong>Standard Contractual Clauses (SCCs):</strong> EU-approved data transfer contracts
          </li>
          <li>
            <strong>Adequacy Decisions:</strong> Transfers to countries recognized by the EU Commission
          </li>
        </ul>
      </section>

      {/* 9. Cookies */}
      <section id="cookies" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">9. Cookies and Tracking Technologies</h2>
        <p>
          We use cookies and similar technologies for authentication, preferences, and analytics. For detailed
          information, see our{" "}
          <a href="/legal/cookies" className="text-blue-600 hover:underline font-semibold">
            Cookie Policy
          </a>
          .
        </p>
      </section>

      {/* 10. Your Rights */}
      <section id="your-rights" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">10. Exercising Your Rights</h2>
        <p>You can exercise your GDPR rights by:</p>

        <div className="not-prose mt-6 space-y-4">
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Download className="w-5 h-5 text-blue-600 flex-shrink-0 mt-1" />
              <div>
                <p className="font-semibold text-gray-900">Export Your Data</p>
                <p className="text-gray-600 text-sm mt-1">
                  Go to <strong>Settings → Privacy → Export My Data</strong> to download your data in JSON format
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <UserX className="w-5 h-5 text-red-600 flex-shrink-0 mt-1" />
              <div>
                <p className="font-semibold text-gray-900">Delete Your Data</p>
                <p className="text-gray-600 text-sm mt-1">
                  Go to <strong>Settings → Privacy → Delete My ML Data</strong> or contact us to delete your entire
                  account
                </p>
              </div>
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Mail className="w-5 h-5 text-green-600 flex-shrink-0 mt-1" />
              <div>
                <p className="font-semibold text-gray-900">Contact Us</p>
                <p className="text-gray-600 text-sm mt-1">
                  Email{" "}
                  <a href="mailto:privacy@cloudwaste.com" className="text-blue-600 hover:underline">
                    privacy@cloudwaste.com
                  </a>{" "}
                  for any privacy-related requests
                </p>
              </div>
            </div>
          </div>
        </div>

        <p className="mt-6 text-sm text-gray-600">
          <strong>Response time:</strong> We will respond to your request within <strong>30 days</strong> as
          required by GDPR Article 12. If we need more time, we will inform you and provide a reason.
        </p>
      </section>

      {/* 11. Children's Privacy */}
      <section id="children" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">11. Children's Privacy</h2>
        <p>
          CloudWaste is not intended for children under <strong>16 years old</strong> (or the minimum age in your
          country). We do not knowingly collect data from children. If you believe we have collected data from a
          child, contact us immediately at{" "}
          <a href="mailto:privacy@cloudwaste.com" className="text-blue-600 hover:underline">
            privacy@cloudwaste.com
          </a>
          .
        </p>
      </section>

      {/* 12. Changes to This Policy */}
      <section id="changes" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">12. Changes to This Policy</h2>
        <p>
          We may update this Privacy Policy from time to time. If we make significant changes, we will notify you by
          email or a prominent notice on our website. Continued use of CloudWaste after changes constitutes
          acceptance.
        </p>
        <p className="mt-4 text-sm text-gray-600">
          <strong>Last updated:</strong> January 2025
        </p>
      </section>

      {/* 13. Contact Us */}
      <section id="contact" className="mb-12">
        <h2 className="text-2xl font-bold text-gray-900 mb-4 flex items-center gap-2">
          <Mail className="w-6 h-6 text-blue-600" />
          13. Contact Us
        </h2>
        <p>
          For any questions about this Privacy Policy or our data practices, please contact us:
        </p>
        <div className="not-prose bg-blue-50 rounded-lg p-6 mt-4">
          <p className="text-gray-900 font-semibold text-lg">CloudWaste Privacy Team</p>
          <p className="text-gray-700 mt-2">
            Email:{" "}
            <a href="mailto:privacy@cloudwaste.com" className="text-blue-600 hover:underline font-semibold">
              privacy@cloudwaste.com
            </a>
          </p>
          <p className="text-gray-700">
            Address: <span className="font-mono">[YOUR COMPANY ADDRESS]</span>
          </p>
          <p className="text-gray-700 mt-4 text-sm">
            <strong>Response time:</strong> We aim to respond within 48 hours (business days)
          </p>
        </div>

        <div className="not-prose bg-yellow-50 border border-yellow-200 rounded-lg p-4 mt-6">
          <p className="text-yellow-900 text-sm flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
            <span>
              <strong>Complaint to Supervisory Authority:</strong> You have the right to lodge a complaint with your
              local data protection authority if you believe we have violated your privacy rights. For EU residents,
              find your authority at{" "}
              <a
                href="https://edpb.europa.eu/about-edpb/board/members_en"
                target="_blank"
                rel="noopener noreferrer"
                className="underline"
              >
                edpb.europa.eu
              </a>
              .
            </span>
          </p>
        </div>
      </section>
    </div>
  );
}
