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
      "Live overlay — always on, unlimited games",
      "Gank suggestions refresh every 10s",
      "General gank priority (no match history)",
      "2 post-game analyses per month",
    ],
  },
  premium_monthly: {
    name: "Premium",
    price: 7.99,
    interval: "month",
    priceId: process.env.STRIPE_PRICE_PREMIUM_MONTHLY ?? "price_premium_monthly",
    features: [
      "Live overlay at full speed (5s refresh)",
      "10 post-game analyses per month",
      "Full history dashboard (last 90 days)",
      "Detailed coaching timeline per match",
    ],
  },
  premium_annual: {
    name: "Premium Annual",
    price: 59.99,
    interval: "year",
    priceId: process.env.STRIPE_PRICE_PREMIUM_ANNUAL ?? "price_premium_annual",
    features: [
      "Everything in Premium",
      "2 months free vs monthly",
    ],
  },
  pro_monthly: {
    name: "Pro",
    price: 18.99,
    interval: "month",
    priceId: process.env.STRIPE_PRICE_PRO_MONTHLY ?? "price_pro_monthly",
    features: [
      "Everything in Pro",
      "20 post-game analyses per month",
      "Multi-account support (smurfs)",
      "Trend analysis — ward scores, gank success rate over time",
      "Priority API queue (faster analysis)",
    ],
  },
} as const;

export type PlanKey = keyof typeof PLANS;
