"use client";

/**
 * The privacy-policy link a consent form shows, or nothing at all.
 *
 * WordPress renders `the_privacy_policy_link()` from every form that collects
 * personal data, and the function's contract is the whole point: if no policy
 * page is published it returns an **empty string**, so the form shows nothing.
 * That is deliberate, and this component keeps it. A link to a page that 404s
 * while a form is asking for consent is worse than no link — it looks like the
 * disclosure is there.
 *
 * The register form's own wording ("...و حریم خصوصی فروشگاه آنلاین را مطالعه
 * کرده‌ام") promised a privacy policy while linking to nothing, which is the
 * specific thing this replaces.
 *
 * Fetched client-side and never blocking: a failed lookup must not prevent
 * registration. A visitor who cannot reach the policy endpoint still has to be
 * able to register, so the failure mode is "no link", exactly like a store with
 * no policy.
 */

import Link from "next/link";
import { useEffect, useState } from "react";

import { privacyPolicyApi, type PrivacyPolicy } from "@/lib/api/settings";

const EMPTY: PrivacyPolicy = { title: null, slug: null, url: null };

export function PrivacyPolicyNotice({ className }: { className?: string }) {
  const [policy, setPolicy] = useState<PrivacyPolicy>(EMPTY);

  useEffect(() => {
    let live = true;
    privacyPolicyApi
      .get()
      .then((p) => {
        if (live) setPolicy(p);
      })
      .catch(() => {
        // Deliberately swallowed: the absence of a link is the same outcome as a
        // store with no policy, and either way the form stays usable. Surfacing
        // an error here would put a failed lookup between a visitor and their
        // registration.
      });
    return () => {
      live = false;
    };
  }, []);

  if (!policy.url || !policy.title) return null;

  return (
    <p className={className}>
      <Link
        href={policy.url}
        className="text-primary hover:underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {policy.title}
      </Link>
    </p>
  );
}

/**
 * An inline link, for a sentence that already names the policy.
 *
 * Renders the caller's own label rather than the page title, because the label
 * has to fit the sentence ("قوانین و مقررات و حریم خصوصی را خوانده‌ام") and a
 * title like "سیاست حریم خصوصی — نسخه ۳" does not. Returns `null` with no policy
 * so the caller can drop the clause rather than leave a dangling "و".
 */
export function PrivacyPolicyLink({
  children,
  className,
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const [policy, setPolicy] = useState<PrivacyPolicy>(EMPTY);

  useEffect(() => {
    let live = true;
    privacyPolicyApi
      .get()
      .then((p) => {
        if (live) setPolicy(p);
      })
      .catch(() => {
        // See above: no policy, no link, form still usable.
      });
    return () => {
      live = false;
    };
  }, []);

  if (!policy.url) return null;

  return (
    <Link
      href={policy.url}
      className={className ?? "text-primary hover:underline"}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </Link>
  );
}

/**
 * The "و حریم خصوصی" connector, or nothing.
 *
 * Its own component rather than a conditional in the caller's sentence because
 * the sentence is Persian and the connector is part of the grammar: dropping the
 * policy link but keeping the "و" leaves "…قوانین و مقررات و فروشگاه آنلاین را
 * مطالعه کرده‌ام", which reads as the store's own name being the third thing the
 * visitor agrees to. Rendered as one unit so the connector can never outlive the
 * thing it connects.
 */
export function PrivacyClause({ label = "حریم خصوصی" }: { label?: string }) {
  const [policy, setPolicy] = useState<PrivacyPolicy>(EMPTY);

  useEffect(() => {
    let live = true;
    privacyPolicyApi
      .get()
      .then((p) => {
        if (live) setPolicy(p);
      })
      .catch(() => {
        // See above: no policy, no clause, form still usable.
      });
    return () => {
      live = false;
    };
  }, []);

  if (!policy.url) return null;

  return (
    <>
      {" و "}
      <Link
        href={policy.url}
        className="text-primary hover:underline"
        target="_blank"
        rel="noopener noreferrer"
      >
        {label}
      </Link>
    </>
  );
}