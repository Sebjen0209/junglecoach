import Stripe from "stripe";

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: "2024-04-10",
  typescript: true,
});

export const PLANS = {
  free: {
    name: "Free",
    price: 0,
    priceId: null,
    features: [
      "Basic gank priority (top lane only)",
      "Manual refresh",
      "Community support",
    ],
  },
  premium_monthly: {
    name: "Premium",
    price: 7.99,
    interval: "month",
    priceId: process.env.STRIPE_PRICE_PREMIUM_MONTHLY ?? "price_premium_monthly",
    features: [
      "All 3 lanes with AI reasoning",
      "Real-time overlay",
      "Auto-refresh every 5 seconds",
      "Game phase detection",
      "Priority support",
    ],
  },
  premium_annual: {
    name: "Premium Annual",
    price: 59.99,
    interval: "year",
    priceId: process.env.STRIPE_PRICE_PREMIUM_ANNUAL ?? "price_premium_annual",
    features: [
      "Everything in Premium",
      "2 months free",
      "Priority support",
    ],
  },
  pro_monthly: {
    name: "Pro",
    price: 18.99,
    interval: "month",
    priceId: process.env.STRIPE_PRICE_PRO_MONTHLY ?? "price_pro_monthly",
    features: [
      "Everything in Premium",
      "Enemy jungler prediction",
      "Win condition detector",
      "VOD review",
      "Dedicated support",
    ],
  },
} as const;

export type PlanKey = keyof typeof PLANS;
