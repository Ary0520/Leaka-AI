import { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: [
        '/dashboard', 
        '/settings', 
        '/ci', 
        '/failures', 
        '/runs', 
        '/quarantine',
        '/applications',
        '/new',
        '/onboard',
        '/run-groups',
        '/suites',
        '/tests'
      ],
    },
    sitemap: 'https://www.leaka.live/sitemap.xml',
  }
}
