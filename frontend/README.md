# CloudWaste Frontend

Next.js 14 frontend application for CloudWaste multi-cloud orphan resource detection platform.

---

## Tech Stack

- **Framework:** Next.js 14+ (App Router)
- **Language:** TypeScript 5+
- **UI Library:** React 18+
- **Styling:** Tailwind CSS + shadcn/ui
- **State Management:** Zustand
- **API Client:** Fetch API with custom wrapper
- **Authentication:** JWT (access + refresh tokens)
- **Testing:** Jest + React Testing Library
- **Linting:** ESLint + Prettier
- **Error Tracking:** Sentry

---

## Quick Start

### 1. Prerequisites

- **Node.js:** 20.x or higher
- **npm:** 10.x or higher
- **Backend:** Running at http://localhost:8000

### 2. Install Dependencies

```bash
cd frontend
npm install
```

### 3. Configure Environment

```bash
cp .env.example .env.local
```

Edit `.env.local`:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=CloudWaste
NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development
```

### 4. Start Development Server

```bash
npm run dev
```

Application will be available at:
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000 (must be running)

---

## Development Commands

### Run Development Server
```bash
npm run dev
```

### Build for Production
```bash
npm run build
npm start  # Run production build locally
```

### Run Tests
```bash
npm test                    # Run all tests
npm run test:watch          # Watch mode
npm run test:coverage       # With coverage report
```

### Code Quality
```bash
npm run lint                # ESLint
npm run format              # Prettier
npm run type-check          # TypeScript check
```

---

## Project Structure

```
frontend/
├── src/
│   ├── app/                        # Next.js App Router
│   │   ├── (auth)/                 # Auth pages (login, register, verify-email)
│   │   ├── (dashboard)/            # Protected dashboard pages
│   │   │   └── dashboard/
│   │   │       ├── page.tsx        # Main dashboard
│   │   │       ├── accounts/       # Cloud accounts management
│   │   │       ├── scans/          # Scan history
│   │   │       ├── resources/      # Orphan resources list
│   │   │       ├── settings/       # User settings
│   │   │       ├── impact/         # Environmental impact
│   │   │       ├── assistant/      # AI chat assistant
│   │   │       └── admin/          # Admin panel
│   │   ├── legal/                  # Legal pages (privacy, terms)
│   │   ├── onboarding/             # Onboarding wizard
│   │   ├── layout.tsx              # Root layout
│   │   ├── error.tsx               # Error page
│   │   ├── not-found.tsx           # 404 page
│   │   └── global-error.tsx        # Global error handler
│   │
│   ├── components/
│   │   ├── ui/                     # shadcn/ui primitives
│   │   ├── layout/                 # Header, Sidebar, Footer
│   │   ├── dashboard/              # Dashboard-specific components
│   │   ├── charts/                 # Chart components
│   │   ├── chat/                   # AI chat components
│   │   ├── onboarding/             # Onboarding wizard
│   │   ├── errors/                 # Error handling components
│   │   ├── legal/                  # Cookie banner, footer
│   │   ├── detection/              # Detection rules UI
│   │   └── providers/              # Context providers (Auth, Sentry)
│   │
│   ├── lib/
│   │   ├── api.ts                  # API client with fetch wrapper
│   │   ├── auth.ts                 # Authentication utilities
│   │   ├── utils.ts                # Utility functions
│   │   └── env.ts                  # Environment variable validation
│   │
│   ├── hooks/
│   │   ├── useAuth.ts              # Authentication hook
│   │   ├── useAccounts.ts          # Cloud accounts hook
│   │   ├── useScans.ts             # Scans hook
│   │   ├── useResources.ts         # Resources hook
│   │   ├── useOnboarding.ts        # Onboarding state
│   │   ├── useErrorHandler.ts      # Error handling
│   │   └── useNotifications.ts     # Toast notifications
│   │
│   ├── stores/
│   │   ├── useAuthStore.ts         # Auth state (Zustand)
│   │   ├── useAccountsStore.ts     # Cloud accounts state
│   │   ├── useScansStore.ts        # Scans state
│   │   ├── useResourcesStore.ts    # Resources state
│   │   ├── useChatStore.ts         # AI chat state
│   │   ├── useOnboardingStore.ts   # Onboarding state
│   │   └── useImpactStore.ts       # Environmental impact state
│   │
│   ├── types/
│   │   ├── index.ts                # Shared types
│   │   ├── errors.ts               # Error types
│   │   ├── onboarding.ts           # Onboarding types
│   │   └── impact.ts               # Impact types
│   │
│   └── config/
│       └── site.ts                 # Site configuration
│
├── public/                         # Static assets
│   ├── favicon.ico
│   ├── og-image.png
│   └── robots.txt
│
├── Dockerfile                      # Development Dockerfile
├── Dockerfile.prod                 # Production Dockerfile (with Sentry)
├── next.config.js                  # Next.js configuration
├── tailwind.config.ts              # Tailwind CSS configuration
├── tsconfig.json                   # TypeScript configuration
├── package.json                    # Dependencies
└── README.md                       # This file
```

---

## Architecture

### App Router (Next.js 14)

CloudWaste uses Next.js 14 **App Router** (not Pages Router):

- **Server Components** by default (async, no client-side JS)
- **Client Components** with `"use client"` directive
- **Route groups** with `(auth)` and `(dashboard)` folders
- **Layouts** for shared UI across routes
- **Loading & Error** boundaries per route

### State Management (Zustand)

Global state managed with **Zustand** stores:

```typescript
// stores/useAuthStore.ts
import { create } from 'zustand';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  login: async (email, password) => {
    const response = await api.post('/api/v1/auth/login', { email, password });
    set({ user: response.user, accessToken: response.access_token });
  },
  logout: () => set({ user: null, accessToken: null }),
}));
```

### API Client (`lib/api.ts`)

Centralized API client with:
- Automatic token refresh
- Error handling
- Request/response interceptors

```typescript
import { apiClient } from '@/lib/api';

// GET request
const scans = await apiClient.get('/api/v1/scans/');

// POST request
const scan = await apiClient.post('/api/v1/scans/', {
  cloud_account_id: accountId,
  scan_type: 'full'
});
```

---

## Code Standards

### TypeScript

**NO `any` types** - Use specific types or `unknown`:

```typescript
// ✅ Good
interface CloudAccount {
  id: string;
  provider: 'aws' | 'azure' | 'gcp' | 'microsoft365';
  account_identifier: string;
}

// ❌ Bad
interface CloudAccount {
  id: any;
  provider: any;
  account_identifier: any;
}
```

### Component Structure

**Always type props with interfaces:**

```typescript
interface ResourceCardProps {
  resource: OrphanResource;
  onIgnore: (resourceId: string) => void;
  onDelete: (resourceId: string) => void;
}

export function ResourceCard({
  resource,
  onIgnore,
  onDelete
}: ResourceCardProps) {
  return (
    <div className="border rounded-lg p-4">
      <h3>{resource.resource_name}</h3>
      <p>Cost: ${resource.estimated_monthly_cost}</p>
      <button onClick={() => onIgnore(resource.id)}>Ignore</button>
      <button onClick={() => onDelete(resource.id)}>Delete</button>
    </div>
  );
}
```

### Server vs Client Components

**Server Components** (default):
```typescript
// app/dashboard/page.tsx
export default async function DashboardPage() {
  // Can fetch data directly
  const scans = await fetch('http://localhost:8000/api/v1/scans/').then(r => r.json());

  return <div>{scans.length} scans</div>;
}
```

**Client Components** (interactive):
```typescript
// components/LoginForm.tsx
'use client';

import { useState } from 'react';

export function LoginForm() {
  const [email, setEmail] = useState('');

  return (
    <form>
      <input
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
    </form>
  );
}
```

### Naming Conventions

- **Components:** `PascalCase` (e.g., `ResourceCard.tsx`)
- **Hooks:** `camelCase` with `use` prefix (e.g., `useAuth.ts`)
- **Stores:** `camelCase` with `use` prefix (e.g., `useAuthStore.ts`)
- **Utils:** `camelCase` (e.g., `formatDate.ts`)
- **Types:** `PascalCase` for interfaces/types (e.g., `User`, `CloudAccount`)

---

## Environment Variables

### Required

```bash
# API endpoint
NEXT_PUBLIC_API_URL=http://localhost:8000

# App name
NEXT_PUBLIC_APP_NAME=CloudWaste

# Sentry error tracking
NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development
```

### Optional

```bash
# Sentry auth token (for source maps upload in production)
SENTRY_AUTH_TOKEN=...
SENTRY_ORG=cloudwaste
SENTRY_PROJECT=cloudwaste-frontend
```

**⚠️ Important:** All variables starting with `NEXT_PUBLIC_` are exposed to the browser.

---

## Testing

### Test Structure

```typescript
// __tests__/components/ResourceCard.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { ResourceCard } from '@/components/dashboard/ResourceCard';

describe('ResourceCard', () => {
  const mockResource = {
    id: '1',
    resource_name: 'test-volume',
    resource_type: 'ebs_volume',
    estimated_monthly_cost: 5.0,
  };

  it('renders resource name', () => {
    render(<ResourceCard resource={mockResource} onIgnore={jest.fn()} onDelete={jest.fn()} />);
    expect(screen.getByText('test-volume')).toBeInTheDocument();
  });

  it('calls onIgnore when ignore button clicked', () => {
    const onIgnore = jest.fn();
    render(<ResourceCard resource={mockResource} onIgnore={onIgnore} onDelete={jest.fn()} />);

    fireEvent.click(screen.getByText('Ignore'));
    expect(onIgnore).toHaveBeenCalledWith('1');
  });
});
```

### Running Tests

```bash
# Run all tests
npm test

# Watch mode
npm run test:watch

# Coverage report
npm run test:coverage

# Update snapshots
npm test -- -u
```

### Coverage Requirements

- **Minimum:** 60% coverage
- **Target:** 70%+ coverage
- Generate report: `npm run test:coverage`
- View report: `open coverage/lcov-report/index.html`

---

## Common Tasks

### Adding a New Page

1. Create file in `src/app/` (e.g., `src/app/settings/page.tsx`)
2. Export default component
3. Add navigation link in `components/layout/Sidebar.tsx`

### Adding a New Component

1. Create file in `src/components/` (e.g., `src/components/dashboard/StatsCard.tsx`)
2. Define props interface
3. Export component
4. Add tests in `__tests__/components/StatsCard.test.tsx`

### Adding API Endpoint

1. Add function in `src/lib/api.ts`
2. Create custom hook in `src/hooks/` (optional)
3. Use in component

Example:
```typescript
// lib/api.ts
export async function getScans() {
  return apiClient.get<Scan[]>('/api/v1/scans/');
}

// hooks/useScans.ts
export function useScans() {
  const [scans, setScans] = useState<Scan[]>([]);

  useEffect(() => {
    getScans().then(setScans);
  }, []);

  return { scans };
}
```

### Adding Zustand Store

1. Create file in `src/stores/` (e.g., `src/stores/useNotificationsStore.ts`)
2. Define interface and create store
3. Use in components with `const { ... } = useNotificationsStore()`

---

## Troubleshooting

### "Module not found" errors

```bash
# Clear Next.js cache
rm -rf .next

# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install
```

### TypeScript errors after `npm install`

```bash
# Restart TypeScript server in VS Code
# Command Palette (Cmd+Shift+P) → "TypeScript: Restart TS Server"

# Or check tsconfig.json is correct
npm run type-check
```

### API connection errors

1. Verify backend is running at http://localhost:8000
2. Check `NEXT_PUBLIC_API_URL` in `.env.local`
3. Check CORS configuration in backend

### Sentry not capturing errors

1. Verify `NEXT_PUBLIC_SENTRY_DSN` is set
2. Check browser console for Sentry initialization logs
3. Verify Sentry is initialized in `components/providers/SentryProvider.tsx`

---

## Additional Resources

- **Next.js Documentation:** https://nextjs.org/docs
- **Tailwind CSS:** https://tailwindcss.com/docs
- **shadcn/ui:** https://ui.shadcn.com/
- **Zustand:** https://github.com/pmndrs/zustand
- **React Testing Library:** https://testing-library.com/react
- **Sentry:** https://docs.sentry.io/platforms/javascript/guides/nextjs/

- **Project Documentation:** `/README.md` (root)
- **Backend README:** `/backend/README.md`
- **Deployment Guide:** `/deployment/README.md`
- **CLAUDE.md:** Frontend context for Claude Code

---

**Version:** 1.0
**Last Updated:** 2025-01-13
**Node.js:** 20+
**Next.js:** 14+
