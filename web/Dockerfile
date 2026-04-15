# ---------- Stage 1: deps ----------
FROM node:20-alpine AS deps
WORKDIR /app

COPY package.json package-lock.json* yarn.lock* ./

RUN \
  if [ -f package-lock.json ]; then npm ci; \
  elif [ -f yarn.lock ]; then yarn install --frozen-lockfile; \
  else echo "No lockfile found." && exit 1; \
  fi


# ---------- Stage 2: builder ----------
FROM node:20-alpine AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Build-time env vars (dummy values — not real secrets)
ARG NEXT_PUBLIC_SUPABASE_URL=dummy
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY=dummy
ARG NEXT_PUBLIC_API_URL=http://localhost:7429

ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build


# ---------- Stage 3: runner ----------
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

# Run as non-root user
RUN addgroup -S nodejs && adduser -S nextjs -G nodejs

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
