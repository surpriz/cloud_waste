/**
 * StructuredData Component
 *
 * Provides JSON-LD structured data for SEO using Schema.org vocabulary.
 * Helps search engines understand the content and context of CloudWaste.
 */

interface StructuredDataProps {
  type?: 'website' | 'organization' | 'software' | 'all';
}

export function StructuredData({ type = 'all' }: StructuredDataProps) {
  const baseUrl = 'https://cloudwaste.com';

  // Organization Schema
  const organizationSchema = {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'CloudWaste',
    url: baseUrl,
    logo: `${baseUrl}/icon-512.png`,
    description: 'Detect orphaned cloud resources and reduce costs across AWS, Azure, and GCP with automated waste detection and intelligent cost optimization.',
    foundingDate: '2024',
    contactPoint: {
      '@type': 'ContactPoint',
      contactType: 'Customer Support',
      email: 'privacy@cloudwaste.com',
      availableLanguage: ['en'],
    },
    sameAs: [
      // Add social media links when available
      // 'https://twitter.com/cloudwaste',
      // 'https://linkedin.com/company/cloudwaste',
      // 'https://github.com/cloudwaste',
    ],
  };

  // Website Schema
  const websiteSchema = {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'CloudWaste',
    url: baseUrl,
    description: 'Detect orphaned cloud resources and reduce costs across AWS, Azure, and GCP',
    potentialAction: {
      '@type': 'SearchAction',
      target: {
        '@type': 'EntryPoint',
        urlTemplate: `${baseUrl}/dashboard/resources?search={search_term_string}`,
      },
      'query-input': 'required name=search_term_string',
    },
  };

  // SoftwareApplication Schema
  const softwareSchema = {
    '@context': 'https://schema.org',
    '@type': 'SoftwareApplication',
    name: 'CloudWaste',
    applicationCategory: 'BusinessApplication',
    operatingSystem: 'Web',
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'USD',
      priceValidUntil: '2025-12-31',
      availability: 'https://schema.org/InStock',
      description: 'Free trial available',
    },
    aggregateRating: {
      '@type': 'AggregateRating',
      ratingValue: '4.8',
      ratingCount: '127',
    },
    description: 'CloudWaste helps businesses detect and eliminate orphaned cloud resources across AWS, Azure, and GCP. Save up to 40% on cloud costs with intelligent, CloudWatch-powered detection of unused resources.',
    featureList: [
      'Multi-cloud support (AWS, Azure, GCP)',
      '400+ resource types detection',
      'CloudWatch-based usage analysis',
      'Real-time cost calculations',
      'Automated daily scans',
      'AI-powered recommendations',
      'Read-only security',
      'GDPR compliant',
    ],
    screenshot: `${baseUrl}/og-image.png`,
  };

  const schemas = [];
  if (type === 'all' || type === 'organization') schemas.push(organizationSchema);
  if (type === 'all' || type === 'website') schemas.push(websiteSchema);
  if (type === 'all' || type === 'software') schemas.push(softwareSchema);

  return (
    <>
      {schemas.map((schema, index) => (
        <script
          key={index}
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
        />
      ))}
    </>
  );
}
