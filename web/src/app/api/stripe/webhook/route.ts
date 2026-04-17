import { headers } from "next/headers";
import { NextResponse } from "next/server";
import Stripe from "stripe";
import { stripe } from "@/lib/stripe";
import { createClient } from "@supabase/supabase-js";

// Service-role client for webhook handler — bypasses RLS
function createServiceClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!
  );
}

function planFromPriceId(priceId: string): string {
  const map: Record<string, string> = {
    [process.env.STRIPE_PRICE_PREMIUM_MONTHLY ?? "price_premium_monthly"]: "premium",
    [process.env.STRIPE_PRICE_PREMIUM_ANNUAL ?? "price_premium_annual"]: "premium",
    [process.env.STRIPE_PRICE_PRO_MONTHLY ?? "price_pro_monthly"]: "pro",
  };
  return map[priceId] ?? "premium";
}

async function handleCheckoutComplete(session: Stripe.Checkout.Session) {
  const supabase = createServiceClient();
  const userId = session.metadata?.user_id;
  if (!userId || !session.customer || !session.subscription) return;

  const newSubId = session.subscription as string;

  // If the user already has a different subscription, cancel it immediately so
  // they don't end up with two active subscriptions for the same customer.
  const { data: existing } = await supabase
    .from("subscriptions")
    .select("stripe_subscription_id")
    .eq("user_id", userId)
    .maybeSingle();

  if (existing?.stripe_subscription_id && existing.stripe_subscription_id !== newSubId) {
    try {
      await stripe.subscriptions.cancel(existing.stripe_subscription_id);
    } catch {
      // Old sub may already be cancelled — safe to ignore
    }
  }

  const subscription = await stripe.subscriptions.retrieve(newSubId);
  const priceId = subscription.items.data[0]?.price.id ?? "";
  const plan = planFromPriceId(priceId);

  const periodEnd =
    (subscription as unknown as { current_period_end?: number }).current_period_end;

  await supabase.from("subscriptions").upsert(
    {
      user_id: userId,
      stripe_customer_id: session.customer as string,
      stripe_subscription_id: newSubId,
      plan,
      status: "active",
      cancel_at_period_end: false,
      ...(periodEnd ? { current_period_end: new Date(periodEnd * 1000).toISOString() } : {}),
      updated_at: new Date().toISOString(),
    },
    { onConflict: "user_id" }
  );
}

async function handleSubscriptionUpdated(subscription: Stripe.Subscription) {
  const supabase = createServiceClient();
  const priceId = subscription.items.data[0]?.price.id ?? "";
  const plan = planFromPriceId(priceId);

  const sub = subscription as unknown as {
    current_period_end?: number;
    cancel_at_period_end?: boolean;
  };
  const periodEnd = sub.current_period_end;

  // cancel_at_period_end=true means user cancelled but still has access until period end
  let status: string;
  if (sub.cancel_at_period_end) {
    status = "cancelling";
  } else if (subscription.status === "active") {
    status = "active";
  } else {
    status = subscription.status;
  }

  await supabase
    .from("subscriptions")
    .update({
      plan,
      status,
      cancel_at_period_end: sub.cancel_at_period_end ?? false,
      ...(periodEnd ? { current_period_end: new Date(periodEnd * 1000).toISOString() } : {}),
      updated_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", subscription.id);
}

async function handleSubscriptionDeleted(subscription: Stripe.Subscription) {
  const supabase = createServiceClient();

  await supabase
    .from("subscriptions")
    .update({
      plan: "free",
      status: "cancelled",
      stripe_subscription_id: null,
      current_period_end: null,
      updated_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", subscription.id);
}

async function handlePaymentFailed(invoice: Stripe.Invoice) {
  const supabase = createServiceClient();

  if (!invoice.subscription) return;

  await supabase
    .from("subscriptions")
    .update({
      status: "past_due",
      updated_at: new Date().toISOString(),
    })
    .eq("stripe_subscription_id", invoice.subscription as string);
}

export async function POST(request: Request) {
  const body = await request.text();
  const signature = headers().get("stripe-signature");

  if (!signature) {
    return new NextResponse("Missing signature", { status: 400 });
  }

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(
      body,
      signature,
      process.env.STRIPE_WEBHOOK_SECRET!
    );
  } catch {
    return new NextResponse("Webhook signature verification failed", {
      status: 400,
    });
  }

  try {
    switch (event.type) {
      case "checkout.session.completed":
        await handleCheckoutComplete(event.data.object as Stripe.Checkout.Session);
        break;

      case "customer.subscription.updated":
        await handleSubscriptionUpdated(event.data.object as Stripe.Subscription);
        break;

      case "customer.subscription.deleted":
        await handleSubscriptionDeleted(event.data.object as Stripe.Subscription);
        break;

      case "invoice.payment_failed":
        await handlePaymentFailed(event.data.object as Stripe.Invoice);
        break;

      default:
        // Unhandled event — ignore
        break;
    }
  } catch (err) {
    console.error(`[stripe-webhook] Error handling ${event.type}:`, err);
    return new NextResponse("Internal error", { status: 500 });
  }

  return new NextResponse("ok", { status: 200 });
}
