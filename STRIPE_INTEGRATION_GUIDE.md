# Guide d'intégration Stripe - CutCosts

## 📋 Récapitulatif de l'implémentation

### ✅ Backend (Complété)

#### 1. Configuration
- ✅ SDK Stripe Python ajouté (`stripe==11.1.1`)
- ✅ Variables d'environnement configurées dans `.env.example`
- ✅ Configuration ajoutée dans `app/core/config.py`

#### 2. Base de données
- ✅ Modèles créés :
  - `SubscriptionPlan` - Plans d'abonnement (Free, Pro, Enterprise)
  - `UserSubscription` - Abonnements utilisateurs
- ✅ Migration Alembic créée : `add_subscription_tables.py`
- ✅ Colonne `stripe_customer_id` ajoutée au modèle `User`
- ✅ 3 plans insérés automatiquement par la migration

#### 3. Logique métier
- ✅ Service `SubscriptionService` complet :
  - Création de session Stripe Checkout
  - Création de session Customer Portal
  - Vérification des limites (scans, comptes cloud, fonctionnalités)
  - Gestion des webhooks Stripe
  - Incrémentation automatique des compteurs d'usage

#### 4. API REST
- ✅ Endpoints créés (`/api/v1/subscriptions/`) :
  - `GET /plans` - Liste des plans
  - `GET /current` - Abonnement actuel
  - `POST /create-checkout-session` - Créer session de paiement
  - `POST /create-portal-session` - Accès au portail client
  - `POST /webhooks/stripe` - Gestion des webhooks
- ✅ Schémas Pydantic pour validation

#### 5. Middleware de protection
- ✅ Dépendances FastAPI créées :
  - `check_scan_limit` - Vérifie limite de scans
  - `check_cloud_account_limit` - Vérifie limite de comptes
  - `require_ai_chat_access` - Vérifie accès AI Chat
  - `require_impact_tracking_access` - Vérifie accès Impact Tracking
  - `require_api_access` - Vérifie accès API

#### 6. Intégration
- ✅ Endpoints de scan modifiés pour vérifier les limites
- ✅ Endpoint d'ajout de compte cloud protégé
- ✅ Création automatique d'abonnement gratuit à l'inscription

### ✅ Frontend (Fondations complétées)

#### 1. Configuration
- ✅ SDK Stripe JS ajouté (`@stripe/stripe-js`)
- ✅ Variables d'environnement documentées dans `.env.example`
- ✅ Types TypeScript créés (`types/subscription.ts`)
- ✅ API Client étendu avec fonctions subscription

---

## 🚀 Étapes de configuration Stripe (À faire)

### 1. Créer un compte Stripe
1. Allez sur [https://dashboard.stripe.com/register](https://dashboard.stripe.com/register)
2. Créez un compte et activez le mode test

### 2. Créer les produits Stripe
Dans le Dashboard Stripe :

#### Plan Pro (29€/mois)
1. **Products** → **Add Product**
2. Nom : `Pro Plan`
3. Description : `Advanced features for growing teams`
4. Prix : `29 EUR / mois` (recurring)
5. Copiez le **Price ID** (commence par `price_...`)

#### Plan Enterprise (99€/mois)
1. **Products** → **Add Product**
2. Nom : `Enterprise Plan`
3. Description : `Unlimited resources and priority support`
4. Prix : `99 EUR / mois` (recurring)
5. Copiez le **Price ID** (commence par `price_...`)

### 3. Configurer les webhooks
1. **Developers** → **Webhooks** → **Add Endpoint**
2. URL : `https://votre-domaine.com/api/v1/subscriptions/webhooks/stripe`
3. Événements à écouter :
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
4. Copiez le **Webhook Secret** (commence par `whsec_...`)

### 4. Récupérer les clés API
1. **Developers** → **API Keys**
2. Copiez la **Publishable Key** (commence par `pk_test_...`)
3. Copiez la **Secret Key** (commence par `sk_test_...`)

### 5. Configurer les variables d'environnement

#### Backend (`backend/.env`)
```bash
# Stripe Payment Configuration
STRIPE_SECRET_KEY=sk_test_votre_secret_key
STRIPE_PUBLISHABLE_KEY=pk_test_votre_publishable_key
STRIPE_WEBHOOK_SECRET=whsec_votre_webhook_secret
STRIPE_PRICE_ID_PRO=price_votre_price_id_pro
STRIPE_PRICE_ID_ENTERPRISE=price_votre_price_id_enterprise
```

#### Frontend (`frontend/.env.local`)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_votre_publishable_key
```

---

## 🔧 Étapes techniques à compléter

### 1. Appliquer la migration de base de données
```bash
cd backend
# Activer l'environnement virtuel
source venv/bin/activate
# Appliquer la migration
alembic upgrade head
```

Cela créera :
- La table `subscription_plans` avec les 3 plans (Free, Pro, Enterprise)
- La table `user_subscriptions`
- La colonne `stripe_customer_id` dans `users`

### 2. Mettre à jour les Price IDs dans la base de données
Après avoir créé les produits Stripe, mettez à jour les plans :

```sql
-- Mettre à jour le plan Pro avec le Stripe Price ID
UPDATE subscription_plans
SET stripe_price_id = 'price_VOTRE_PRICE_ID_PRO'
WHERE name = 'pro';

-- Mettre à jour le plan Enterprise avec le Stripe Price ID
UPDATE subscription_plans
SET stripe_price_id = 'price_VOTRE_PRICE_ID_ENTERPRISE'
WHERE name = 'enterprise';
```

Ou utilisez Python :
```python
from app.core.database import get_db
from app.models.subscription_plan import SubscriptionPlan
from sqlalchemy import select

async def update_stripe_price_ids():
    async with get_db() as db:
        # Update Pro plan
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "pro")
        )
        pro_plan = result.scalar_one()
        pro_plan.stripe_price_id = "price_VOTRE_PRICE_ID_PRO"

        # Update Enterprise plan
        result = await db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.name == "enterprise")
        )
        enterprise_plan = result.scalar_one()
        enterprise_plan.stripe_price_id = "price_VOTRE_PRICE_ID_ENTERPRISE"

        await db.commit()
```

### 3. Installer les dépendances
```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
npm install
```

### 4. Redémarrer les services
```bash
# Avec Docker Compose
docker-compose down
docker-compose up -d --build

# Ou manuellement
# Backend
cd backend
uvicorn app.main:app --reload

# Frontend
cd frontend
npm run dev
```

---

## 🎨 Pages frontend à créer (Prochaines étapes)

### 1. Page de tarification (`/pricing`)
**Fichier** : `frontend/src/app/pricing/page.tsx`

**Fonctionnalités** :
- Afficher les 3 plans (Free, Pro, Enterprise)
- Bouton "Commencer" pour Free
- Bouton "S'abonner" pour Pro et Enterprise → Redirection vers Stripe Checkout

**Exemple de structure** :
```tsx
import { useEffect, useState } from 'react';
import { loadStripe } from '@stripe/stripe-js';
import api from '@/lib/api';

export default function PricingPage() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    async function fetchPlans() {
      const data = await api.getSubscriptionPlans();
      setPlans(data);
    }
    fetchPlans();
  }, []);

  const handleSubscribe = async (planName: string) => {
    setLoading(true);
    try {
      const session = await api.createCheckoutSession({
        plan_name: planName,
        success_url: `${window.location.origin}/payment/success`,
        cancel_url: `${window.location.origin}/pricing`,
      });

      // Redirection vers Stripe Checkout
      window.location.href = session.url;
    } catch (error) {
      console.error('Error creating checkout session:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>Choisissez votre plan</h1>
      {plans.map((plan) => (
        <div key={plan.id}>
          <h2>{plan.display_name}</h2>
          <p>{plan.description}</p>
          <p>{plan.price_monthly}€/mois</p>
          <button onClick={() => handleSubscribe(plan.name)}>
            S'abonner
          </button>
        </div>
      ))}
    </div>
  );
}
```

### 2. Page de gestion d'abonnement (`/dashboard/subscription`)
**Fichier** : `frontend/src/app/(dashboard)/dashboard/subscription/page.tsx`

**Fonctionnalités** :
- Afficher le plan actuel
- Afficher l'utilisation (scans utilisés / limite)
- Bouton "Gérer l'abonnement" → Redirection vers Stripe Customer Portal
- Bouton "Upgrade" si plan gratuit

### 3. Pages de succès/annulation
**Fichiers** :
- `frontend/src/app/payment/success/page.tsx`
- `frontend/src/app/payment/cancel/page.tsx`

### 4. Composants utilitaires
- **Badge d'abonnement** : Afficher le plan actuel dans la navbar
- **Dialog d'upgrade** : Popup quand limite atteinte
- **Indicateur d'usage** : Barre de progression pour les scans

---

## 🧪 Tests à effectuer

### 1. Test du parcours complet
1. ✅ Créer un nouveau compte → Vérifier qu'un abonnement gratuit est créé
2. ✅ Essayer de lancer 6 scans avec plan Free → Doit bloquer au 6ème
3. ✅ Essayer d'ajouter 2 comptes cloud avec plan Free → Doit bloquer au 2ème
4. ✅ S'abonner au plan Pro via Stripe Checkout (mode test)
5. ✅ Vérifier que les limites ont changé
6. ✅ Tester l'accès au portail client Stripe

### 2. Test des webhooks
Utilisez Stripe CLI pour tester les webhooks localement :
```bash
stripe listen --forward-to localhost:8000/api/v1/subscriptions/webhooks/stripe
```

### 3. Cartes de test Stripe
```
Paiement réussi : 4242 4242 4242 4242
Paiement échoué : 4000 0000 0000 0002
3D Secure : 4000 0025 0000 3155
```

---

## 📊 Plans d'abonnement configurés

| Plan | Prix | Scans/mois | Comptes cloud | Fonctionnalités |
|------|------|------------|---------------|-----------------|
| **Free** | 0€ | 5 | 1 | Détection basique |
| **Pro** | 29€ | 50 | 5 | AI Chat, Impact Tracking, Email notifications |
| **Enterprise** | 99€ | Illimité | Illimité | Tout + Support prioritaire + Accès API |

---

## 🔒 Sécurité

### ✅ Implémenté
- Vérification de signature webhook Stripe
- Clés API en variables d'environnement
- Validation stricte côté backend
- Dépendances FastAPI pour contrôle d'accès

### ⚠️ Recommandations production
- Utiliser HTTPS en production
- Passer en mode live Stripe (clés `pk_live_...` et `sk_live_...`)
- Configurer le webhook en production
- Activer Stripe Radar pour la détection de fraude

---

## 📚 Ressources

- [Documentation Stripe](https://stripe.com/docs)
- [Stripe Dashboard](https://dashboard.stripe.com)
- [Stripe CLI](https://stripe.com/docs/stripe-cli)
- [Stripe Testing Cards](https://stripe.com/docs/testing)

---

## ❓ Support

En cas de problème :
1. Vérifier les logs backend (`docker-compose logs backend`)
2. Vérifier la console Stripe Dashboard
3. Tester les webhooks avec Stripe CLI
4. Consulter la documentation Stripe

---

**Dernière mise à jour** : 26 novembre 2025
**Version** : 1.0
**Statut** : Backend complet, Frontend à finaliser
