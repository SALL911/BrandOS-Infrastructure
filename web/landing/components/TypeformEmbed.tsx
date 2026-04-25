"use client";

/**
 * Typeform embed for /tools/brand-check and /about contact block.
 *
 * Form ZZYlfK7A — submissions hit /api/webhooks/typeform via Typeform's
 * own webhook infrastructure.
 *
 * Loading strategy: Next.js <Script strategy="afterInteractive"> instead of
 * useEffect-injecting the script tag. The previous useEffect approach
 * race-conditioned on /about: the embed div was already mounted before the
 * script ran, Typeform's MutationObserver missed the div, and the slot
 * stayed blank. <Script> places the tag during hydration, before the
 * embed div is interactive — observer attaches reliably.
 */

import Script from "next/script";

const FORM_ID = "ZZYlfK7A";

export function TypeformEmbed() {
  return (
    <>
      <Script
        src="https://embed.typeform.com/next/embed.js"
        strategy="afterInteractive"
      />
      <div
        data-tf-live={FORM_ID}
        data-tf-opacity="100"
        data-tf-iframe-props="title=Symcio Free Scan"
        data-tf-transitive-search-params
        data-tf-medium="snippet"
        style={{ width: "100%", height: "70vh", minHeight: 520 }}
      />
    </>
  );
}
